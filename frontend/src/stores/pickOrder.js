import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getMyPickOrders, getPickOrderDetail, scanPickOrderRoll, callMethod
} from '@/api/frappe'

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

  // Source Warehouse is chosen dynamically at execution time — defaults to
  // whatever the supervisor set on the Order, but the worker can change it
  // if the rolls are actually sitting somewhere else. Every scan is
  // validated against whichever value is currently selected here.
  const sourceWarehouse = ref('')

  // Rolls scanned THIS session — not written to the DB until final submit
  // (same pattern as the ordinary Roll Wise Pick List flow).
  const scannedRolls = ref([])

  const sessionQty = computed(() => scannedRolls.value.reduce((sum, r) => sum + (Number(r.qty) || 0), 0))
  const totalPickedQty = computed(() => (order.value?.already_picked_qty || 0) + sessionQty.value)
  const withinTolerance = computed(() => {
    if (!order.value) return false
    return totalPickedQty.value >= order.value.tolerance_min && totalPickedQty.value <= order.value.tolerance_max
  })
  const overTolerance = computed(() => !!order.value && totalPickedQty.value > order.value.tolerance_max)

  async function loadOrder(name) {
    orderLoading.value = true
    orderError.value = ''
    order.value = null
    scannedRolls.value = []
    try {
      order.value = await getPickOrderDetail(name)
      sourceWarehouse.value = order.value.source_warehouse || ''
    } catch (err) {
      orderError.value = err.message
    } finally {
      orderLoading.value = false
    }
  }

  // Scans one roll: accepts the same composite barcode format used
  // elsewhere in the app ("item_code#batch#roll_no", falling back to the
  // raw value if it isn't in that shape), extracts the roll number, then
  // validates it server-side (warehouse match against the currently
  // selected sourceWarehouse, project match for "To Work Order" picks,
  // and dedupe against prior sessions). Also blocks an obvious duplicate
  // within this same session before even calling the server.
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

  function removeScannedRoll(rollNo) {
    scannedRolls.value = scannedRolls.value.filter(r => r.roll_no !== rollNo)
  }

  async function submitOrder(postingDate) {
    if (!order.value) throw new Error('No Pick Order loaded')
    if (!sourceWarehouse.value) throw new Error('Select a Source Warehouse first')
    if (!scannedRolls.value.length) throw new Error('Scan at least one roll before submitting')
    if (!withinTolerance.value) {
      throw new Error(
        `Total picked (${totalPickedQty.value.toFixed(2)}) is outside the \u00b13% tolerance ` +
        `for the target (${order.value.pick_qty.toFixed(2)})`
      )
    }

    submitting.value = true
    try {
      const payload = {
        pick_type: order.value.pick_type,
        document: order.value.document_name,
        project: order.value.project,
        target_warehouse: order.value.target_warehouse,
        source_warehouse: sourceWarehouse.value,
        posting_date: postingDate,
        roll_pick_assignment: order.value.name,
        rolls: scannedRolls.value.map(r => ({
          roll_no: r.roll_no,
          item_code: r.item_code,
          warehouse: r.warehouse,
          batch_no: r.batch_no,
          qty: r.qty,
          uom: r.uom,
        })),
      }
      const res = await callMethod('pranera_knit.api.knit.create_roll_picking_entry', payload)
      return res.message
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    order.value = null
    orderError.value = ''
    scannedRolls.value = []
    sourceWarehouse.value = ''
  }

  return {
    myOrders, listLoading, listError, loadMyOrders,
    order, orderLoading, orderError, submitting,
    sourceWarehouse, scannedRolls,
    sessionQty, totalPickedQty, withinTolerance, overTolerance,
    loadOrder, scanRoll, removeScannedRoll, submitOrder, reset,
  }
})
