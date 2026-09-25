import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getMyPickOrders, getPickOrderDetail, scanPickOrderRoll, removeScannedRoll as apiRemoveScannedRoll,
  updatePickOrderExecution, submitPickOrder,
} from '@/api/frappe'
import { db } from '@/db'

export const usePickOrderStore = defineStore('pickOrder', () => {
  // ── "My Pick Orders" list ────────────────────────────────────────────────
  const myOrders = ref([])
  const listLoading = ref(false)
  const listError = ref('')

  async function loadMyOrders() {
    listLoading.value = true
    listError.value = ''
    try {
      myOrders.value = await getMyPickOrders()
    } catch (err) {
      listError.value = err.message
    } finally {
      listLoading.value = false
    }
  }

  // ── One order's execution state ──────────────────────────────────────────
  const order = ref(null)       // full detail from get_pick_order_detail
  const orderLoading = ref(false)
  const orderError = ref('')
  const submitting = ref(false)

  // Source/Target Warehouse are chosen dynamically at execution time —
  // default to whatever's persisted on the Assignment (execution_* fields,
  // themselves defaulting to the supervisor's original source_warehouse /
  // target_warehouse), but the worker can change either if the rolls are
  // actually sitting somewhere else or need to land somewhere else. Every
  // scan is validated against whichever Source Warehouse is currently
  // selected. Changes are persisted server-side (see setSourceWarehouse /
  // setTargetWarehouse below) so a resumed session — different device,
  // next shift, after a refresh — shows the same choice.
  const sourceWarehouse = ref('')
  const targetWarehouse = ref('')

  // Full Warehouse list for the Source/Target AutoComplete dropdowns — read
  // from the same offline-synced Dexie table (@/db, populated by useSync)
  // that Roll-wise Pick List's warehouse AutoComplete already uses, so this
  // page matches that one exactly (same list, same offline availability)
  // instead of a separate live API call.
  const warehouses = ref([])
  const warehousesLoading = ref(false)

  async function loadWarehouses() {
    if (warehouses.value.length) return
    warehousesLoading.value = true
    try {
      warehouses.value = (await db.warehouses.toArray()).map(w => ({ label: w.id, value: w.id }))
    } catch (err) {
      // Non-fatal — the dropdown just falls back to showing only the
      // currently-selected value as an option.
      console.warn('Failed to load warehouses:', err)
    } finally {
      warehousesLoading.value = false
    }
  }

  // Rolls scanned against this Assignment and not yet submitted. Persisted
  // server-side as soon as each one is scanned (see scan_pick_order_roll) —
  // this is loaded straight from the server on loadOrder, not held only in
  // this browser tab, so closing the app mid-session loses nothing.
  const scannedRolls = ref([])

  // Per-UOM progress — pairs each target from order.pick_qty_summary
  // (Kgs, Pcs, whatever UOMs the batch items carry) with this session's
  // scanned rolls of that same UOM plus whatever was already picked in a
  // prior session. A Kgs target and a Pcs target are unrelated
  // quantities — see get_pick_qty_targets_by_uom in knit.py — so each is
  // tracked and tolerance-checked independently rather than blended into
  // one combined number.
  const uomProgress = computed(() => {
    if (!order.value) return []
    const sessionByUom = {}
    for (const r of scannedRolls.value) {
      const uom = r.uom || 'Kgs'
      sessionByUom[uom] = (sessionByUom[uom] || 0) + (Number(r.qty) || 0)
    }
    return (order.value.pick_qty_summary || []).map(target => {
      const sessionQtyForUom = sessionByUom[target.uom] || 0
      const totalPicked = (target.already_picked_qty || 0) + sessionQtyForUom
      return {
        uom: target.uom,
        targetQty: target.total_qty,
        toleranceMin: target.tolerance_min,
        toleranceMax: target.tolerance_max,
        alreadyPickedQty: target.already_picked_qty || 0,
        sessionQty: sessionQtyForUom,
        totalPicked,
        withinTolerance: totalPicked >= target.tolerance_min && totalPicked <= target.tolerance_max,
        overTolerance: totalPicked > target.tolerance_max,
      }
    })
  })

  // Submission requires every UOM group to independently land within
  // tolerance — a Kgs group sitting fine while Pcs is still short (or
  // over) means the pick isn't actually done yet.
  const withinTolerance = computed(() =>
    uomProgress.value.length > 0 && uomProgress.value.every(u => u.withinTolerance)
  )
  const overTolerance = computed(() => uomProgress.value.some(u => u.overTolerance))

  async function loadOrder(name) {
    orderLoading.value = true
    orderError.value = ''
    order.value = null
    scannedRolls.value = []
    try {
      order.value = await getPickOrderDetail(name)
      sourceWarehouse.value = order.value.execution_source_warehouse || order.value.source_warehouse || ''
      targetWarehouse.value = order.value.execution_target_warehouse || order.value.target_warehouse || ''
      scannedRolls.value = order.value.scanned_rolls || []
    } catch (err) {
      orderError.value = err.message
    } finally {
      orderLoading.value = false
    }
  }

  // Persist a changed Source/Target Warehouse choice. Fire-and-forget from
  // the UI's perspective (the input already shows the new value locally),
  // but awaited here so callers can surface a save error if it happens.
  async function setSourceWarehouse(value) {
    sourceWarehouse.value = value
    if (!order.value) return
    await updatePickOrderExecution(order.value.name, { sourceWarehouse: value })
  }

  async function setTargetWarehouse(value) {
    targetWarehouse.value = value
    if (!order.value) return
    await updatePickOrderExecution(order.value.name, { targetWarehouse: value })
  }

  // Scans one roll: accepts the same composite barcode format used
  // elsewhere in the app ("item_code#batch#roll_no", falling back to the
  // raw value if it isn't in that shape), extracts the roll number, then
  // validates + persists it server-side (warehouse match against the
  // currently selected sourceWarehouse, project match for "To Work Order"
  // picks, and dedupe against both prior submitted sessions and this
  // in-progress one). Also blocks an obvious duplicate within this local
  // list before even calling the server.
  async function scanRoll(scannedValue) {
    if (!order.value) throw new Error('No Pick Order loaded')
    if (!sourceWarehouse.value) throw new Error('Select a Source Warehouse first')

    const parts = String(scannedValue).split('#')
    const rollNo = parts.length >= 3 ? parts[2] : scannedValue

    if (scannedRolls.value.some(r => r.roll_no === rollNo)) {
      throw new Error(`Roll ${rollNo} has already been scanned this session`)
    }

    const result = await scanPickOrderRoll(order.value.name, rollNo, sourceWarehouse.value)
    scannedRolls.value = [...scannedRolls.value, result]
    return result
  }

  async function removeScannedRoll(rollNo) {
    if (!order.value) return
    await apiRemoveScannedRoll(order.value.name, rollNo)
    scannedRolls.value = scannedRolls.value.filter(r => r.roll_no !== rollNo)
  }

  async function submitOrder(postingDate, submitStockEntry = true) {
    if (!order.value) throw new Error('No Pick Order loaded')
    if (!scannedRolls.value.length) throw new Error('Scan at least one roll before submitting')
    if (!withinTolerance.value) {
      const offenders = uomProgress.value.filter(u => !u.withinTolerance)
      const detail = offenders
        .map(u => `${u.uom}: picked ${u.totalPicked.toFixed(2)}, target ${u.targetQty.toFixed(2)}`)
        .join('; ')
      throw new Error(
        `Outside the \u00b13% tolerance for ${offenders.length > 1 ? 'these UOMs' : 'this UOM'} — ${detail}`
      )
    }

    submitting.value = true
    try {
      // Rolls, Source Warehouse and Target Warehouse are NOT sent from
      // here — the server builds the pick entry from whatever's already
      // persisted against this Assignment (scanned_rolls,
      // execution_source_warehouse, execution_target_warehouse), so the
      // source of truth is always the saved scan session, not this tab's
      // in-memory state.
      const res = await submitPickOrder(order.value.name, postingDate, submitStockEntry)
      return res
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    order.value = null
    orderError.value = ''
    scannedRolls.value = []
    sourceWarehouse.value = ''
    targetWarehouse.value = ''
  }

  return {
    myOrders, listLoading, listError, loadMyOrders,
    order, orderLoading, orderError, submitting,
    sourceWarehouse, targetWarehouse, warehouses, warehousesLoading, loadWarehouses,
    scannedRolls,
    uomProgress, withinTolerance, overTolerance,
    loadOrder, setSourceWarehouse, setTargetWarehouse,
    scanRoll, removeScannedRoll, submitOrder, reset,
  }
})
