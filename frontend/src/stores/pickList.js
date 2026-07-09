// src/stores/pickList.js
// Mirrors roll-wise-pick-list.page.ts — 8 pick types, barcode scan, offline dropdowns
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { db } from '@/db'
import { enqueue, isOnline } from '@/composables/useSync'
import {
  getWorkOrderDetails, getPurchaseOrderDetails,
  getSubcontractingOrderDetails, getBatchesForProject,
  getList, callMethod
} from '@/api/frappe'

export const PICK_TYPES = [
  'From Work Order',
  'To Work Order',
  'From Purchase Order',
  'To Subcontracting Order',
  'From Subcontracting Order',
  'From Stock Entry',
  'From Batch',
  'Manual Roll Pick'
]

export const usePickListStore = defineStore('pickList', () => {
  const selectedPickType = ref('')
  const selectedDocument = ref(null)
  const selectedDocumentName = ref('')
  const loading = ref(false)

  // Dropdown options (served from local IndexedDB)
  const workOrders = ref([])
  const purchaseOrders = ref([])
  const subcontractingOrders = ref([])
  const stockEntries = ref([])
  const batches = ref([])
  const warehouses = ref([])
  const rollNos = ref([])

  // Document details
  const documentDetails = ref(null)
  const items = ref([])

  // Barcode scan result
  const scannedBarcode = ref('')

  // ── Load dropdowns from IndexedDB cache ──────────────────────────────────
  async function loadDropdowns() {
    workOrders.value = (await db.work_orders.toArray()).map(w => ({
      label: w.id, value: w.id
    }))
    const localPOs = await db.purchase_orders.toArray()
    purchaseOrders.value = localPOs.map(p => ({ label: p.id, value: p.id }))
    const localSCOs = await db.subcontracting_orders.toArray()
    subcontractingOrders.value = localSCOs.map(s => ({ label: s.id, value: s.id }))
    const localSEs = await db.stock_entries.toArray()
    stockEntries.value = localSEs.map(s => ({ label: s.id, value: s.id }))
    const localBatches = await db.batches.toArray()
    batches.value = localBatches.map(b => ({ label: b.id, value: b.id }))
    const localWH = await db.warehouses.toArray()
    warehouses.value = localWH.map(w => ({ label: w.id, value: w.id }))
    const localRolls = await db.rolls.toArray()
    rollNos.value = localRolls.map(r => ({ label: r.roll_no, value: r.roll_no }))
  }

  // ── Load document details when a WO/PO/SCO is selected ──────────────────
  async function loadDocumentDetails(pickType, docName) {
    loading.value = true
    documentDetails.value = null
    items.value = []

    try {
      let res = null
      if (pickType.includes('Work Order')) {
        res = await getWorkOrderDetails(docName)
      } else if (pickType.includes('Purchase Order')) {
        res = await getPurchaseOrderDetails(docName)
      } else if (pickType.includes('Subcontracting')) {
        res = await getSubcontractingOrderDetails(docName)
      } else if (pickType === 'From Batch') {
        const batchRes = await getBatchesForProject(docName)
        documentDetails.value = { name: docName }
        items.value = batchRes?.data?.data || []
        return
      }

      if (res?.data?.data) {
        documentDetails.value = res.data.data
        items.value = res.data.data.items || res.data.data.required_items || []
      }
    } catch (err) {
      console.error('loadDocumentDetails error:', err)
    } finally {
      loading.value = false
    }
  }

  // ── Submit pick entry ────────────────────────────────────────────────────
  async function submitPickEntry(pickData) {
    if (isOnline.value) {
      try {
        const res = await callMethod('pranera.api.create_roll_picking_entry', pickData)
        return res?.data
      } catch (err) {
        // Fall back to queue if online call fails
        await enqueue('createRollPickingEntry', 'POST', pickData)
        throw err
      }
    } else {
      // Queue for later when offline
      await enqueue('createRollPickingEntry', 'POST', pickData)
      return { queued: true }
    }
  }

  // ── Barcode scan handler (replaces BarcodeScanner Cordova plugin) ────────
  // In PWA, we use the browser's BarcodeDetector API or a manual input fallback
  async function handleBarcodeInput(value) {
    scannedBarcode.value = value

    // Try to match against local roll nos
    const roll = await db.rolls.where('roll_no').equals(value).first()
    if (roll) {
      return { type: 'roll', data: roll }
    }
    return { type: 'unknown', value }
  }

  function reset() {
    selectedPickType.value = ''
    selectedDocument.value = null
    selectedDocumentName.value = ''
    documentDetails.value = null
    items.value = []
    scannedBarcode.value = ''
  }

  return {
    selectedPickType, selectedDocument, selectedDocumentName,
    loading, workOrders, purchaseOrders, subcontractingOrders,
    stockEntries, batches, warehouses, rollNos,
    documentDetails, items, scannedBarcode, PICK_TYPES,
    loadDropdowns, loadDocumentDetails, submitPickEntry,
    handleBarcodeInput, reset
  }
})
