import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  syncWarehouses, searchWorkOrdersForPickOrder, searchAssignableUsers, createPickOrder,
} from '@/api/frappe'

export const useCreatePickOrderStore = defineStore('createPickOrder', () => {
  const pickType = ref('')
  const documentName = ref('')
  const sourceWarehouse = ref('')
  const targetWarehouse = ref('')
  const pickQty = ref(null)
  const assignedTo = ref('')
  const remarks = ref('')

  const warehouses = ref([])
  const workOrders = ref([])
  const users = ref([])

  const loadingLookups = ref(false)
  const submitting = ref(false)
  const error = ref('')

  const needsDocument = computed(() => pickType.value === 'From Work Order' || pickType.value === 'To Work Order')
  const canSubmit = computed(() =>
    pickType.value && sourceWarehouse.value && targetWarehouse.value && assignedTo.value &&
    Number(pickQty.value) > 0 && (!needsDocument.value || documentName.value)
  )

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
        source_warehouse: sourceWarehouse.value,
        target_warehouse: targetWarehouse.value,
        pick_qty: Number(pickQty.value),
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
    sourceWarehouse.value = ''
    targetWarehouse.value = ''
    pickQty.value = null
    assignedTo.value = ''
    remarks.value = ''
    error.value = ''
  }

  return {
    pickType, documentName, sourceWarehouse, targetWarehouse, pickQty, assignedTo, remarks,
    warehouses, workOrders, users,
    loadingLookups, submitting, error,
    needsDocument, canSubmit,
    loadLookups, searchUsers, submit, reset,
  }
})
