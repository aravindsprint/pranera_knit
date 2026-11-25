import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import {
  getOutwardRequestItems, saveOutwardRequest, getOutwardRequest, listOutwardRequests,
  getBuildings, searchWorkOrdersForOutward, searchPurchaseOrdersForOutward,
  getOutwardPickDefaults, createOutwardRollPickAssignment, syncWarehouses, searchAssignableUsers,
  getOutwardRequestConfig, approveOutwardSameDay, rejectOutwardSameDay, getOutwardDayKgs,
  getOutwardSummary,
} from '@/api/frappe'

function todayISO() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function addDaysISO(iso, n) {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d + n)
  const pad = (v) => String(v).padStart(2, '0')
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`
}

// Minutes past midnight of a server "YYYY-MM-DD HH:MM:SS" / "HH:MM" string.
function toMinutes(t) {
  const hm = String(t || '').split(' ').pop().split(':')
  return Number(hm[0]) * 60 + Number(hm[1] || 0)
}

// Stable per-row keys so duplicating / removing rows never shifts one row's
// batch dropdown state onto another row.
let keySeq = 0
const nextKey = () => `r${++keySeq}`

export const useOutwardRequestStore = defineStore('outwardRequest', () => {
  // ── List ────────────────────────────────────────────────────────────────
  const requests = ref([])
  // '' | stage:not_assigned | stage:assigned | stage:picked | stage:completed | OVERDUE | AWAITING_APPROVAL
  const listFilter = ref('')
  const summary = ref(null)         // get_outward_summary: pending per UOM, stage counts, overdue
  const listSearch = ref('')
  const loadingList = ref(false)

  // ── Form ────────────────────────────────────────────────────────────────
  const name = ref('')              // set once saved / when opening an existing one
  const date = ref(todayISO())
  // From is pre-filled with NAP (server: DEFAULT_FROM_BUILDING) on every
  // new request; it can still be changed.
  const DEFAULT_FROM_BUILDING = 'NAP'
  const defaultFromBuilding = () => config.value?.default_from_building || DEFAULT_FROM_BUILDING
  const fromBuilding = ref(DEFAULT_FROM_BUILDING)
  const toBuilding = ref('')
  const sourceType = ref('Work Order')   // 'Work Order' | 'Purchase Order'
  const workOrder = ref('')
  const purchaseOrder = ref('')
  const items = ref([])
  const receipts = ref([])          // Subcontracting Receipts the PO items came from
  const meta = ref(null)            // created_by_name, created_on, status, request_status, assignments
  const originalDate = ref('')      // the saved date, so editing an old request isn't blocked

  // ── Same-day cut-off (server clock, Outward Request Settings) ───────────
  const config = ref(null)
  const configAt = ref(0)           // Date.now() when config was fetched
  const clock = ref(Date.now())     // ticks every minute so the cut-off flips live
  let clockTimer = null
  const deciding = ref(false)

  const buildings = ref([])
  const workOrders = ref([])
  const purchaseOrders = ref([])

  const fetching = ref(false)
  const saving = ref(false)
  const error = ref('')
  const fetchedFor = ref('')        // which document the current items came from
  // Set when the fetched Work Order already has an Outward Request — only
  // one is allowed per Work Order, so the form can't be saved.
  const existingRequest = ref('')
  // Work Order requests: { item_code: required qty } from its Required Items.
  const requiredQtyByItem = ref({})

  // Server time now = server time at fetch + time elapsed on this device.
  const serverMinutesNow = computed(() => {
    if (!config.value) return null
    return toMinutes(config.value.now) + Math.floor((clock.value - configAt.value) / 60000)
  })
  const afterCutoff = computed(() =>
    !!config.value && serverMinutesNow.value >= toMinutes(config.value.cutoff_time)
  )
  const minDate = computed(() => config.value?.today || todayISO())
  // Deadline: the cut-off time (11:30 PM) on the day BEFORE the request date.
  const defaultDate = computed(() => addDaysISO(minDate.value, afterCutoff.value ? 2 : 1))
  const dateChanged = computed(() => !name.value || date.value !== originalDate.value)
  const dateInPast = computed(() => dateChanged.value && !!date.value && date.value < minDate.value)
  const isLate = computed(() =>
    !!date.value && (date.value <= minDate.value ||
      (date.value === addDaysISO(minDate.value, 1) && afterCutoff.value))
  )
  const lateNeedsApproval = computed(() =>
    dateChanged.value && !!config.value?.require_approval && isLate.value
  )

  // Daily Kgs limit (collar / cuff are in Pcs, so only Kgs rows count here;
  // the server also excludes collar / cuff item groups).
  const dailyKgsLimit = computed(() => Number(config.value?.daily_kgs_limit || 0))
  const dayBookedKgs = ref(0)
  const myKgs = computed(() => items.value
    .filter(r => String(r.stock_uom || '').toLowerCase() === 'kgs')
    .reduce((t, r) => t + (Number(r.qty) || 0), 0))
  const dayTotalKgs = computed(() => dayBookedKgs.value + myKgs.value)
  const overLimit = computed(() =>
    dailyKgsLimit.value > 0 && myKgs.value > 0 && dayTotalKgs.value > dailyKgsLimit.value
  )
  async function loadDayKgs() {
    if (!date.value) { dayBookedKgs.value = 0; return }
    try {
      const d = await getOutwardDayKgs(date.value, name.value || undefined)
      dayBookedKgs.value = Number(d?.booked || 0)
    } catch { dayBookedKgs.value = 0 }
  }
  watch(() => [date.value, name.value], loadDayKgs)

  const needsApproval = computed(() => lateNeedsApproval.value || overLimit.value)
  const isApprover = computed(() => !!config.value?.is_approver)
  const approverNames = computed(() =>
    (config.value?.approvers || []).map(a => a.full_name || a.user).join(', ')
  )

  const documentName = computed(() =>
    sourceType.value === 'Work Order' ? workOrder.value : purchaseOrder.value
  )
  const isEditable = computed(() => !meta.value || meta.value.request_status === 'Pending')
  const totalsByUom = computed(() => {
    const t = {}
    for (const r of items.value) {
      const u = r.stock_uom || '—'
      t[u] = (t[u] || 0) + (Number(r.qty) || 0)
    }
    return t
  })
  // What this request takes from each (batch, warehouse), summed over its
  // rows — compared against that pair's free qty (stock − other requests).
  const takenByKey = computed(() => {
    const t = {}
    for (const r of items.value) {
      if (!r.batch || !r.warehouse) continue
      const k = `${r.batch}|${r.warehouse}`
      t[k] = (t[k] || 0) + (Number(r.qty) || 0)
    }
    return t
  })
  function rowAllocation(r) {
    if (!r.batch || !r.warehouse || !r.stock_info) return null
    const taken = takenByKey.value[`${r.batch}|${r.warehouse}`] || 0
    const free = Number(r.stock_info.available_qty) || 0
    return { taken, free, short: Math.round((taken - free) * 1000) / 1000 }
  }
  const overAllocated = computed(() =>
    items.value.filter(r => { const a = rowAllocation(r); return a && a.short > 0.001 })
  )
  // Only NAP% warehouses may be used (server: outward_request_events.WAREHOUSE_PREFIX).
  const WAREHOUSE_PREFIX = 'NAP'
  const isAllowedWarehouse = (w) => !w || String(w).toUpperCase().startsWith(WAREHOUSE_PREFIX)
  const badWarehouseRows = computed(() => items.value.filter(r => !isAllowedWarehouse(r.warehouse)))

  // Work Order requests: an item may be left out (partial send from NAP),
  // but an item that's on the request must total its Required Qty — summed
  // over its rows, since one item can be split across batches.
  const enteredByItem = computed(() => {
    const t = {}
    for (const r of items.value) t[r.item_code] = (t[r.item_code] || 0) + (Number(r.qty) || 0)
    return t
  })
  function itemQtyCheck(itemCode) {
    if (sourceType.value !== 'Work Order') return null
    const required = requiredQtyByItem.value[itemCode]
    const entered = Math.round((enteredByItem.value[itemCode] || 0) * 1000) / 1000
    if (required === undefined) return { entered, required: null, ok: false }
    return { entered, required, ok: Math.abs(entered - required) <= 0.001 }
  }
  const qtyMismatches = computed(() => {
    if (sourceType.value !== 'Work Order' || !Object.keys(requiredQtyByItem.value).length) return []
    const uom = {}
    for (const r of items.value) if (!(r.item_code in uom)) uom[r.item_code] = r.stock_uom || ''
    return Object.keys(enteredByItem.value)
      .map(code => ({ item_code: code, stock_uom: uom[code], ...itemQtyCheck(code) }))
      .filter(c => !c.ok)
  })

  const sameBuilding = computed(() => !!fromBuilding.value && fromBuilding.value === toBuilding.value)
  const canSave = computed(() =>
    isEditable.value && !!date.value && !dateInPast.value && !!fromBuilding.value && !!toBuilding.value &&
    !sameBuilding.value && !!documentName.value && !existingRequest.value &&
    items.value.length > 0 &&
    items.value.every(r => r.item_code && Number(r.qty) > 0 && (!r.batch || r.warehouse)) &&
    !overAllocated.value.length && !badWarehouseRows.value.length && !qtyMismatches.value.length
  )
  const buildingOptions = computed(() =>
    buildings.value.map(b => ({
      value: b.name,
      label: [b.building_name || b.name, b.building_code, b.city].filter(Boolean).join(' · ')
    }))
  )

  async function loadList() {
    loadingList.value = true
    error.value = ''
    try {
      const f = listFilter.value
      const [rows, sum] = await Promise.all([
        listOutwardRequests({
          sameDayApproval: f === 'AWAITING_APPROVAL' ? 'Pending' : '',
          stage: f.startsWith('stage:') ? f.slice(6) : '',
          overdue: f === 'OVERDUE',
          txt: listSearch.value,
        }),
        getOutwardSummary().catch(() => summary.value),
      ])
      requests.value = rows
      summary.value = sum
    } catch (e) {
      error.value = e.message
    } finally {
      loadingList.value = false
    }
  }

  async function loadConfig() {
    try {
      config.value = await getOutwardRequestConfig()
      configAt.value = Date.now()
      clock.value = configAt.value
      clearInterval(clockTimer)
      clockTimer = setInterval(() => { clock.value = Date.now() }, 60000)
      // A new, untouched form gets the cut-off-aware default date.
      if (!name.value && (!date.value || date.value < defaultDate.value)) date.value = defaultDate.value
      if (!name.value && !fromBuilding.value) fromBuilding.value = defaultFromBuilding()
    } catch { /* the server still enforces the rules on save */ }
  }

  async function loadLookups() {
    loadConfig()
    try {
      const [b, wo, po] = await Promise.all([
        getBuildings(), searchWorkOrdersForOutward(''), searchPurchaseOrdersForOutward('')
      ])
      buildings.value = b
      workOrders.value = wo
      purchaseOrders.value = po
    } catch (e) {
      error.value = e.message
    }
  }

  async function searchWorkOrders(txt) {
    try { workOrders.value = await searchWorkOrdersForOutward(txt) } catch { /* keep last list */ }
  }
  async function searchPurchaseOrders(txt) {
    try { purchaseOrders.value = await searchPurchaseOrdersForOutward(txt) } catch { /* keep last list */ }
  }

  function setSourceType(type) {
    if (sourceType.value === type) return
    sourceType.value = type
    workOrder.value = ''
    purchaseOrder.value = ''
    clearItems()
  }

  function clearItems() {
    items.value = []
    receipts.value = []
    fetchedFor.value = ''
    existingRequest.value = ''
    requiredQtyByItem.value = {}
  }

  // A row's batch must sit in a warehouse of the From building, so changing
  // From clears picks that are now in another building.
  function setFromBuilding(b) {
    fromBuilding.value = b || ''
    if (!b) return
    for (const r of items.value) {
      if (r.warehouse && r.building && r.building !== b) {
        r.batch = ''; r.warehouse = ''; r.building = ''; r.stock_info = null
      }
    }
  }

  // The batch dropdown picked a (batch, warehouse) option (or cleared it).
  function onBatchPicked(row, option) {
    row.building = option?.building || ''
    row.stock_info = option ? {
      stock_qty: option.stock_qty, reserved_qty: option.reserved_qty,
      available_qty: option.available_qty, unallocated_qty: option.unallocated_qty,
      reservations: option.reservations, unallocated_reservations: option.unallocated_reservations,
    } : null
  }

  async function fetchItems() {
    if (!documentName.value) return
    fetching.value = true
    error.value = ''
    try {
      const res = await getOutwardRequestItems({
        ...(sourceType.value === 'Work Order'
          ? { workOrder: workOrder.value }
          : { purchaseOrder: purchaseOrder.value }),
        fromBuilding: fromBuilding.value, name: name.value,
      })
      items.value = (res.items || []).map(r => ({ ...r, stock_info: r.stock_info || null, _key: nextKey() }))
      receipts.value = res.receipts || []
      existingRequest.value = res.existing_request || ''
      requiredQtyByItem.value = res.required_qty_by_item || {}
      fetchedFor.value = documentName.value
    } catch (e) {
      clearItems()
      error.value = e.message
    } finally {
      fetching.value = false
    }
  }

  function removeItem(i) { items.value.splice(i, 1) }

  // Copy of row i inserted right below it — e.g. to split one item's qty
  // across two batches.
  function duplicateItem(i) {
    const row = items.value[i]
    if (row) items.value.splice(i + 1, 0, { ...row, _key: nextKey() })
  }

  async function save() {
    if (!canSave.value) return null
    saving.value = true
    error.value = ''
    try {
      const doc = await saveOutwardRequest({
        name: name.value || undefined,
        date: date.value,
        from_building: fromBuilding.value,
        to_building: toBuilding.value,
        work_order: sourceType.value === 'Work Order' ? workOrder.value : undefined,
        purchase_order: sourceType.value === 'Purchase Order' ? purchaseOrder.value : undefined,
        items: items.value.map(r => ({
          item_code: r.item_code, batch: r.batch || null, warehouse: r.warehouse || null,
          qty: Number(r.qty), stock_uom: r.stock_uom
        })),
      })
      applyDoc(doc)
      return doc
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      saving.value = false
    }
  }

  async function open(docName) {
    reset()
    fetching.value = true
    try {
      applyDoc(await getOutwardRequest(docName))
    } catch (e) {
      error.value = e.message
    } finally {
      fetching.value = false
    }
  }

  function applyDoc(doc) {
    name.value = doc.name
    date.value = doc.date
    originalDate.value = doc.date
    fromBuilding.value = doc.from_building || ''
    toBuilding.value = doc.to_building
    sourceType.value = doc.purchase_order ? 'Purchase Order' : 'Work Order'
    workOrder.value = doc.work_order || ''
    purchaseOrder.value = doc.purchase_order || ''
    fetchedFor.value = doc.purchase_order || doc.work_order || ''
    existingRequest.value = ''
    requiredQtyByItem.value = doc.required_qty_by_item || {}
    items.value = (doc.items || []).map(r => ({
      _key: nextKey(),
      item_code: r.item_code, batch: r.batch || '', warehouse: r.warehouse || '', building: r.building || '',
      qty: r.qty, stock_uom: r.stock_uom || '', stock_info: r.stock_info || null,
    }))
    meta.value = {
      created_by: doc.created_by,
      created_by_name: doc.created_by_name || doc.created_by,
      created_on: doc.created_on,
      status: doc.status || '',
      request_status: doc.request_status || 'Pending',
      assignments: doc.roll_pick_assignments || [],
      vehicles: doc.vehicle_gate_entries || [],
      same_day_approval: doc.same_day_approval || '',
      approval_requested_on: doc.approval_requested_on,
      approved_by_name: doc.approved_by_name || doc.approved_by || '',
      approved_on: doc.approved_on,
      approval_remarks: doc.approval_remarks || '',
      approval_reason: doc.approval_reason || '',
      can_approve: !!doc.can_approve,
      progress: doc.progress || { by_uom: [], lines: [] },
      age_days: doc.age_days || 0,
    }
  }

  async function decideApproval(approve, remarks) {
    if (!name.value) return null
    deciding.value = true
    error.value = ''
    try {
      const doc = approve
        ? await approveOutwardSameDay(name.value, remarks)
        : await rejectOutwardSameDay(name.value, remarks)
      applyDoc(doc)
      return doc
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      deciding.value = false
    }
  }

  function reset() {
    name.value = ''
    fromBuilding.value = defaultFromBuilding()
    date.value = config.value ? defaultDate.value : todayISO()
    originalDate.value = ''
    toBuilding.value = ''
    sourceType.value = 'Work Order'
    workOrder.value = ''
    purchaseOrder.value = ''
    meta.value = null
    error.value = ''
    pickPlan.value = null
    pickError.value = ''
    clearItems()
  }

  // ── Create Roll Pick Assignment from this request ──────────────────────
  const pickPlan = ref(null)          // server-built defaults (get_pick_assignment_defaults)
  const pickForm = ref({})
  const warehouses = ref([])
  const users = ref([])
  const creatingPick = ref(false)
  const pickError = ref('')

  const canCreatePick = computed(() =>
    !!name.value && meta.value?.request_status === 'Pending' &&
    !['Pending', 'Rejected'].includes(meta.value?.same_day_approval)
  )
  const pickFormValid = computed(() => {
    const f = pickForm.value, p = pickPlan.value
    if (!p || !f.sourceWarehouse || !f.targetWarehouse || !f.assignedTo) return false
    if (p.pick_type === 'To Work Order') return p.batch_items.length > 0 || Number(f.pickQty) > 0
    return !!f.subcontractingOrder && p.batch_items.length > 0
  })

  async function startPick() {
    pickError.value = ''
    pickPlan.value = null
    try {
      const [plan, wh, us] = await Promise.all([
        getOutwardPickDefaults(name.value),
        warehouses.value.length ? warehouses.value : syncWarehouses(),
        users.value.length ? users.value : searchAssignableUsers(''),
      ])
      warehouses.value = wh
      users.value = us
      pickPlan.value = plan
      pickForm.value = {
        sourceWarehouse: plan.default_source_warehouse || '',
        targetWarehouse: plan.default_target_warehouse || '',
        subcontractingOrder: plan.subcontracting_orders[0]?.name || '',
        pickQty: plan.pick_type === 'To Work Order' ? plan.pick_qty : null,
        assignedTo: '',
        remarks: '',
      }
    } catch (e) {
      pickError.value = e.message
    }
  }

  function onSubcontractingOrderChange() {
    const sco = pickPlan.value?.subcontracting_orders.find(s => s.name === pickForm.value.subcontractingOrder)
    if (sco?.supplier_warehouse) pickForm.value.targetWarehouse = sco.supplier_warehouse
  }

  async function searchUsers(txt) {
    try { users.value = await searchAssignableUsers(txt) } catch { /* keep last list */ }
  }

  async function createPick() {
    if (!pickFormValid.value) return null
    creatingPick.value = true
    pickError.value = ''
    try {
      const f = pickForm.value
      const res = await createOutwardRollPickAssignment({
        name: name.value,
        source_warehouse: f.sourceWarehouse,
        target_warehouse: f.targetWarehouse,
        assigned_to: f.assignedTo,
        subcontracting_order: pickPlan.value.pick_type === 'To Subcontracting Order' ? f.subcontractingOrder : undefined,
        pick_qty: pickPlan.value.pick_type === 'To Work Order' && !pickPlan.value.batch_items.length ? Number(f.pickQty) : undefined,
        remarks: f.remarks || undefined,
      })
      applyDoc(res.outward_request)
      pickPlan.value = null
      return res.name
    } catch (e) {
      pickError.value = e.message
      return null
    } finally {
      creatingPick.value = false
    }
  }

  function cancelPick() {
    pickPlan.value = null
    pickError.value = ''
  }

  return {
    pickPlan, pickForm, warehouses, users, creatingPick, pickError, canCreatePick, pickFormValid,
    startPick, onSubcontractingOrderChange, searchUsers, createPick, cancelPick,
    requests, listFilter, listSearch, loadingList, summary,
    name, date, fromBuilding, toBuilding, sourceType, workOrder, purchaseOrder, items, receipts, meta,
    buildings, workOrders, purchaseOrders, buildingOptions,
    fetching, saving, error, fetchedFor,
    documentName, isEditable, totalsByUom, canSave, existingRequest, sameBuilding,
    rowAllocation, overAllocated, setFromBuilding, onBatchPicked,
    requiredQtyByItem, itemQtyCheck, qtyMismatches, badWarehouseRows, isAllowedWarehouse,
    config, afterCutoff, minDate, defaultDate, dateInPast, needsApproval, isApprover, approverNames,
    isLate, lateNeedsApproval, dailyKgsLimit, dayBookedKgs, myKgs, dayTotalKgs, overLimit, loadDayKgs,
    deciding, decideApproval, loadConfig,
    loadList, loadLookups, searchWorkOrders, searchPurchaseOrders,
    setSourceType, clearItems, fetchItems, removeItem, duplicateItem, save, open, reset,
  }
})
