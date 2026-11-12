import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getOutwardRequestItems, saveOutwardRequest, getOutwardRequest, listOutwardRequests,
  getBuildings, searchWorkOrdersForOutward, searchPurchaseOrdersForOutward,
  getOutwardPickDefaults, createOutwardRollPickAssignment, syncWarehouses, searchAssignableUsers,
  getOutwardRequestConfig, approveOutwardSameDay, rejectOutwardSameDay,
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
  const listFilter = ref('')        // '' | Pending | Processing | Completed | AWAITING_APPROVAL
  const listSearch = ref('')
  const loadingList = ref(false)

  // ── Form ────────────────────────────────────────────────────────────────
  const name = ref('')              // set once saved / when opening an existing one
  const date = ref(todayISO())
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

  // Server time now = server time at fetch + time elapsed on this device.
  const serverMinutesNow = computed(() => {
    if (!config.value) return null
    return toMinutes(config.value.now) + Math.floor((clock.value - configAt.value) / 60000)
  })
  const afterCutoff = computed(() =>
    !!config.value && serverMinutesNow.value >= toMinutes(config.value.cutoff_time)
  )
  const minDate = computed(() => config.value?.today || todayISO())
  const defaultDate = computed(() =>
    afterCutoff.value ? addDaysISO(minDate.value, 1) : minDate.value
  )
  const dateChanged = computed(() => !name.value || date.value !== originalDate.value)
  const dateInPast = computed(() => dateChanged.value && !!date.value && date.value < minDate.value)
  const needsApproval = computed(() =>
    dateChanged.value && !!config.value?.require_approval &&
    date.value === minDate.value && afterCutoff.value
  )
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
  const canSave = computed(() =>
    isEditable.value && !!date.value && !dateInPast.value && !!toBuilding.value && !!documentName.value &&
    items.value.length > 0 &&
    items.value.every(r => r.item_code && Number(r.qty) > 0)
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
      const awaiting = listFilter.value === 'AWAITING_APPROVAL'
      requests.value = await listOutwardRequests({
        requestStatus: awaiting ? '' : listFilter.value,
        sameDayApproval: awaiting ? 'Pending' : '',
        txt: listSearch.value,
      })
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
  }

  async function fetchItems() {
    if (!documentName.value) return
    fetching.value = true
    error.value = ''
    try {
      const res = await getOutwardRequestItems(
        sourceType.value === 'Work Order'
          ? { workOrder: workOrder.value }
          : { purchaseOrder: purchaseOrder.value }
      )
      items.value = (res.items || []).map(r => ({ ...r, _key: nextKey() }))
      receipts.value = res.receipts || []
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
        to_building: toBuilding.value,
        work_order: sourceType.value === 'Work Order' ? workOrder.value : undefined,
        purchase_order: sourceType.value === 'Purchase Order' ? purchaseOrder.value : undefined,
        items: items.value.map(r => ({
          item_code: r.item_code, batch: r.batch || null, qty: Number(r.qty), stock_uom: r.stock_uom
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
    toBuilding.value = doc.to_building
    sourceType.value = doc.purchase_order ? 'Purchase Order' : 'Work Order'
    workOrder.value = doc.work_order || ''
    purchaseOrder.value = doc.purchase_order || ''
    fetchedFor.value = doc.purchase_order || doc.work_order || ''
    items.value = (doc.items || []).map(r => ({
      _key: nextKey(),
      item_code: r.item_code, batch: r.batch || '', qty: r.qty, stock_uom: r.stock_uom || ''
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
      can_approve: !!doc.can_approve,
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
    requests, listFilter, listSearch, loadingList,
    name, date, toBuilding, sourceType, workOrder, purchaseOrder, items, receipts, meta,
    buildings, workOrders, purchaseOrders, buildingOptions,
    fetching, saving, error, fetchedFor,
    documentName, isEditable, totalsByUom, canSave,
    config, afterCutoff, minDate, defaultDate, dateInPast, needsApproval, isApprover, approverNames,
    deciding, decideApproval, loadConfig,
    loadList, loadLookups, searchWorkOrders, searchPurchaseOrders,
    setSourceType, clearItems, fetchItems, removeItem, duplicateItem, save, open, reset,
  }
})
