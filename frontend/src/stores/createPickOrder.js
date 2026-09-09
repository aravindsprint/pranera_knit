import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import {
  syncWarehouses, searchWorkOrdersForPickOrder, searchSalesOrdersForPickOrder,
  searchBatchesForPickOrder, searchAssignableUsers, createPickOrder,
} from '@/api/frappe'

export const useCreatePickOrderStore = defineStore('createPickOrder', () => {
  const pickType = ref('')
  const documentName = ref('')
  const salesOrder = ref('')
  const sourceWarehouse = ref('')
  const targetWarehouse = ref('')
  const pickQty = ref(null)
  const assignedTo = ref('')
  const remarks = ref('')

  // "To Work Order" restricts to specific batches only if the supervisor
  // opts in — leave it off and the pick behaves as before (free-scan
  // target weight, any batch this Work Order produced accepted).
  const restrictToBatches = ref(false)

  // "From Batch" / "To Sales Order" (always) and "To Work Order" (when
  // restrictToBatches is on) build pick_qty from these rows instead of a
  // manually-entered target — mirrors the batch_items child table +
  // set_pick_qty_from_batch_items() on the Roll Pick Assignment doctype.
  const batchItems = ref([{ batch: '', qty: null }])

  const warehouses = ref([])
  const workOrders = ref([])
  const salesOrders = ref([])
  const batches = ref([])
  const users = ref([])

  const loadingLookups = ref(false)
  const submitting = ref(false)
  const error = ref('')

  const needsDocument = computed(() => pickType.value === 'From Work Order' || pickType.value === 'To Work Order')
  const needsSalesOrder = computed(() => pickType.value === 'To Sales Order')
  const offersBatchRestriction = computed(() => pickType.value === 'To Work Order')
  const needsBatchItems = computed(() =>
    pickType.value === 'From Batch' ||
    pickType.value === 'To Sales Order' ||
    (offersBatchRestriction.value && restrictToBatches.value)
  )

  const batchItemsTotal = computed(() =>
    batchItems.value.reduce((sum, r) => sum + (Number(r.qty) || 0), 0)
  )

  // Keep pickQty in sync with the batch rows whenever they're in play, so
  // the rest of the app (tolerance preview, canSubmit) can keep reading
  // pickQty as the single source of truth either way.
  watch(batchItemsTotal, (total) => {
    if (needsBatchItems.value) pickQty.value = total
  })
  watch(needsBatchItems, (active) => {
    if (active) pickQty.value = batchItemsTotal.value
  })

  const canSubmit = computed(() => {
    if (!pickType.value || !sourceWarehouse.value || !targetWarehouse.value || !assignedTo.value) return false
    if (needsDocument.value && !documentName.value) return false
    if (needsSalesOrder.value && !salesOrder.value) return false
    if (needsBatchItems.value) {
      const rows = batchItems.value.filter(r => r.batch && Number(r.qty) > 0)
      return rows.length > 0
    }
    return Number(pickQty.value) > 0
  })

  async function loadLookups() {
    loadingLookups.value = true
    error.value = ''
    try {
      const [wh, wo] = await Promise.all([syncWarehouses(), searchWorkOrdersForPickOrder('')])
      warehouses.value = wh
      workOrders.value = wo
    } catch (err) {
      error.value = err.message
    } finally {
      loadingLookups.value = false
    }
  }

  async function searchUsers(txt) {
    try {
      users.value = await searchAssignableUsers(txt)
    } catch (err) {
      console.warn('searchAssignableUsers failed:', err.message)
    }
  }

  async function searchSalesOrders(txt) {
    try {
      salesOrders.value = await searchSalesOrdersForPickOrder(txt)
    } catch (err) {
      console.warn('searchSalesOrdersForPickOrder failed:', err.message)
    }
  }

  async function searchBatches(txt) {
    try {
      batches.value = await searchBatchesForPickOrder(txt)
    } catch (err) {
      console.warn('searchBatchesForPickOrder failed:', err.message)
    }
  }

  function addBatchItemRow() {
    batchItems.value = [...batchItems.value, { batch: '', qty: null }]
  }

  function removeBatchItemRow(index) {
    if (batchItems.value.length === 1) {
      batchItems.value = [{ batch: '', qty: null }]
      return
    }
    batchItems.value = batchItems.value.filter((_, i) => i !== index)
  }

  async function submit() {
    error.value = ''
    if (!canSubmit.value) {
      error.value = 'Fill in all required fields'
      return null
    }
    submitting.value = true
    try {
      const payload = {
        pick_type: pickType.value,
        document_name: needsDocument.value ? documentName.value : null,
        sales_order: needsSalesOrder.value ? salesOrder.value : null,
        source_warehouse: sourceWarehouse.value,
        target_warehouse: targetWarehouse.value,
        pick_qty: needsBatchItems.value ? batchItemsTotal.value : Number(pickQty.value),
        batch_items: needsBatchItems.value
          ? batchItems.value.filter(r => r.batch && Number(r.qty) > 0).map(r => ({ batch: r.batch, qty: Number(r.qty) }))
          : null,
        assigned_to: assignedTo.value,
        remarks: remarks.value || null,
      }
      return await createPickOrder(payload)
    } catch (err) {
      error.value = err.message
      return null
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    pickType.value = ''
    documentName.value = ''
    salesOrder.value = ''
    sourceWarehouse.value = ''
    targetWarehouse.value = ''
    pickQty.value = null
    assignedTo.value = ''
    remarks.value = ''
    batchItems.value = [{ batch: '', qty: null }]
    restrictToBatches.value = false
    error.value = ''
  }

  return {
    pickType, documentName, salesOrder, sourceWarehouse, targetWarehouse, pickQty, assignedTo, remarks,
    batchItems, batchItemsTotal, restrictToBatches,
    warehouses, workOrders, salesOrders, batches, users,
    loadingLookups, submitting, error,
    needsDocument, needsSalesOrder, needsBatchItems, offersBatchRestriction, canSubmit,
    loadLookups, searchUsers, searchSalesOrders, searchBatches,
    addBatchItemRow, removeBatchItemRow,
    submit, reset,
  }
})
