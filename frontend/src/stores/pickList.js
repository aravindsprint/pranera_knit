// src/stores/pickList.js
// Full port of the Ionic app's roll-wise-pick-list.page.ts — 8 pick types,
// Work/Purchase/Subcontracting Order + Stock Entry + Batch + Manual Roll Pick
// document lookups, GKF-item batch-vs-roll transfer detection, Job Card roll
// filtering, required-items remaining-qty tracking, roll table, barcode
// scan parsing, and submit. Nothing from the Ionic page is skipped — only the
// transport changed (talks to ERPNext directly instead of via the Node
// middleware), and Ionic's AlertController prompts are replaced with the
// browser's window.prompt/alert (this is a PWA, not Ionic).
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { db } from '@/db'
import { enqueue, isOnline } from '@/composables/useSync'
import {
  getWorkOrderDetails, getPurchaseOrderDetails,
  getSubcontractingOrderDetails, getStockEntryDetails,
  getBatchesForProject, getBatchDetails,
  getRollsForBatch, getRollsForJobCard, getJobCardsForWorkOrder,
  findRollByRollNo, getRecentRolls,
  callMethod
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

// Which pick types show which fields — mirrors Ionic's showFieldByPickType()
const FIELD_VISIBILITY = {
  document: ['From Work Order', 'To Work Order', 'From Purchase Order',
             'To Subcontracting Order', 'From Subcontracting Order', 'From Stock Entry', 'From Batch'],
  project: ['From Work Order', 'To Work Order', 'From Purchase Order',
            'To Subcontracting Order', 'From Subcontracting Order'],
  jobCard: ['From Work Order', 'To Work Order'],
  targetWarehouse: PICK_TYPES,
  sourceWarehouse: PICK_TYPES,
  fromWorkOrder: ['To Subcontracting Order'],
  fromSubcontracting: ['To Subcontracting Order'],
  batchNo: ['From Work Order', 'To Work Order', 'From Purchase Order',
            'To Subcontracting Order', 'From Subcontracting Order', 'From Stock Entry'],
  rollNo: PICK_TYPES,
}

function docLabelFor(pickType) {
  if (pickType?.includes('Work Order')) return 'Work Order'
  if (pickType?.includes('Purchase Order')) return 'Purchase Order'
  if (pickType?.includes('Subcontracting')) return 'Subcontracting Order'
  if (pickType === 'From Stock Entry') return 'Stock Entry'
  if (pickType === 'From Batch') return 'Batch'
  return 'Document'
}

export const usePickListStore = defineStore('pickList', () => {
  // ── Core selections ───────────────────────────────────────────────────
  const selectedPickType     = ref('')
  const selectedDocumentName = ref('')
  const selectedProject      = ref('')
  const selectedTargetWarehouse = ref('')
  const selectedSourceWarehouse = ref('')
  const selectedBatchName    = ref('')
  const selectedJobCardName  = ref('')
  const selectedFromWorkOrder      = ref('')
  const selectedFromSubcontracting = ref('')

  // ── GKF item detection (item codes starting "GKF" transfer by whole
  //    batch instead of individual roll — mirrors isGKFProduction) ────────
  const isGKFProduction = ref(false)
  const productionItem  = ref('')
  const batchItemCode   = ref('')

  const loading    = ref(false)
  const submitting = ref(false)

  // ── Dropdown options (name-only lists, served from IndexedDB cache) ────
  const workOrders            = ref([])
  const purchaseOrders        = ref([])
  const subcontractingOrders  = ref([])
  const stockEntries          = ref([])
  const warehouses            = ref([])

  // ── Live-loaded, context-scoped option lists ────────────────────────────
  const batches  = ref([])   // batches for the selected project/work order (or job card)
  const rollNos  = ref([])   // rolls for the selected batch (or job card+batch)
  const jobCards = ref([])   // job cards for the selected work order

  // ── Job Card → batch/roll filtering state (mirrors jobCardRollMap etc.) ─
  const jobCardBatches = ref([])          // batch names available under the selected job card
  let jobCardRollMap   = new Map()        // batch -> [roll_no, ...]
  let allRollsForJobCard = []             // flat list of roll_nos under the job card (for barcode validation)

  // ── Tables ────────────────────────────────────────────────────────────
  const requiredItemsTable  = ref([])     // [{item_code, required_qty, transferred_qty/supplied_qty, stock_uom, picked_qty}]
  const rollWiseReportTable = ref([])     // [{roll_no, item_code, warehouse, batch_no, qty, uom}]
  const totalPickedQty = ref(0)
  const totalWeight     = ref(0)

  const docLabel = computed(() => docLabelFor(selectedPickType.value))

  const currentDocOptions = computed(() => {
    const t = selectedPickType.value
    if (t?.includes('Work Order')) return workOrders.value
    if (t?.includes('Purchase Order')) return purchaseOrders.value
    if (t?.includes('Subcontracting')) return subcontractingOrders.value
    if (t === 'From Stock Entry') return stockEntries.value
    if (t === 'From Batch') return batches.value.length ? batches.value : []
    return []
  })

  function showField(fieldName) {
    return (FIELD_VISIBILITY[fieldName] || []).includes(selectedPickType.value)
  }
  const showRequiredQtyColumn   = () => selectedPickType.value === 'To Work Order' || selectedPickType.value === 'To Subcontracting Order'
  const showTransferredQtyColumn = () => selectedPickType.value === 'To Work Order'
  const showSuppliedQtyColumn    = () => selectedPickType.value === 'To Subcontracting Order'
  const showStockUomColumn       = () => selectedPickType.value === 'To Work Order'

  // ── Load name-only dropdown lists from IndexedDB cache ──────────────────
  async function loadDropdowns() {
    workOrders.value = (await db.work_orders.toArray()).map(w => ({ label: w.id, value: w.id }))
    purchaseOrders.value = (await db.purchase_orders.toArray()).map(p => ({ label: p.id, value: p.id }))
    subcontractingOrders.value = (await db.subcontracting_orders.toArray()).map(s => ({ label: s.id, value: s.id }))
    stockEntries.value = (await db.stock_entries.toArray()).map(s => ({ label: s.id, value: s.id }))
    warehouses.value = (await db.warehouses.toArray()).map(w => ({ label: w.id, value: w.id }))
  }

  // ── Reset everything when the pick type changes ─────────────────────────
  function onPickTypeChange() {
    selectedDocumentName.value = ''
    selectedProject.value = ''
    selectedTargetWarehouse.value = ''
    selectedSourceWarehouse.value = ''
    selectedBatchName.value = ''
    selectedJobCardName.value = ''
    selectedFromWorkOrder.value = ''
    selectedFromSubcontracting.value = ''
    isGKFProduction.value = false
    productionItem.value = ''
    batchItemCode.value = ''
    requiredItemsTable.value = []
    rollWiseReportTable.value = []
    totalPickedQty.value = 0
    totalWeight.value = 0
    batches.value = []
    rollNos.value = []
    jobCards.value = []
    jobCardBatches.value = []
    jobCardRollMap = new Map()
    allRollsForJobCard = []

    if (selectedPickType.value === 'Manual Roll Pick') loadRecentRolls()
  }

  // ── Document selected: dispatch to the right detail loader ──────────────
  async function onDocumentSelect() {
    const name = selectedDocumentName.value
    if (!name) return

    // New document → clear anything scoped to the previous one
    selectedJobCardName.value = ''
    jobCards.value = []
    jobCardBatches.value = []
    jobCardRollMap = new Map()
    allRollsForJobCard = []

    loading.value = true
    try {
      const t = selectedPickType.value
      if (t === 'From Work Order' || t === 'To Work Order') await fetchWorkOrderDetails(name)
      else if (t === 'From Purchase Order') await fetchPurchaseOrderDetails(name)
      else if (t === 'To Subcontracting Order' || t === 'From Subcontracting Order') await fetchSubcontractingOrderDetails(name)
      else if (t === 'From Stock Entry') await fetchStockEntryDetails(name)
      else if (t === 'From Batch') await fetchBatchDetails(name)
    } catch (err) {
      console.error('onDocumentSelect error:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkOrderDetails(workOrderName) {
    const data = await getWorkOrderDetails(workOrderName)
    selectedProject.value = data.project || ''
    productionItem.value  = data.production_item || ''
    isGKFProduction.value = (productionItem.value || '').toUpperCase().startsWith('GKF')

    if (selectedPickType.value === 'From Work Order') {
      selectedSourceWarehouse.value = data.fg_warehouse || ''
      selectedTargetWarehouse.value = ''
    }

    if (selectedPickType.value === 'To Work Order') {
      if (data.wip_warehouse) selectedTargetWarehouse.value = data.wip_warehouse
      const rmItems = data.required_items || []
      requiredItemsTable.value = rmItems.map(item => ({
        item_code: item.item_code,
        stock_uom: item.stock_uom,
        required_qty: item.required_qty || 0,
        transferred_qty: item.transferred_qty || 0,
        picked_qty: (item.required_qty || 0) - (item.transferred_qty || 0)
      }))
    }

    await loadBatchesForProject(selectedProject.value, workOrderName)
    await loadJobCardsForWorkOrder(workOrderName)
  }

  async function fetchPurchaseOrderDetails(poName) {
    const data = await getPurchaseOrderDetails(poName)
    selectedProject.value = data.project || ''
    requiredItemsTable.value = (data.items || []).map(item => ({
      item_code: item.item_code,
      picked_qty: item.qty || 0
    }))
    await loadBatchesForProject(selectedProject.value, null)
  }

  async function fetchSubcontractingOrderDetails(scoName) {
    const data = await getSubcontractingOrderDetails(scoName)
    selectedProject.value = (data.items && data.items[0] && data.items[0].project) || ''
    if (data.supplier_warehouse) selectedTargetWarehouse.value = data.supplier_warehouse

    if (selectedPickType.value === 'To Subcontracting Order') {
      requiredItemsTable.value = (data.supplied_items || []).map(item => ({
        item_code: item.rm_item_code,
        required_qty: item.required_qty || 0,
        supplied_qty: item.supplied_qty || 0,
        picked_qty: (item.required_qty || 0) - (item.supplied_qty || 0)
      }))
    } else {
      requiredItemsTable.value = (data.items || []).map(item => ({
        item_code: item.item_code,
        picked_qty: item.qty || 0
      }))
    }
    await loadBatchesForProject(selectedProject.value, null)
  }

  async function fetchStockEntryDetails(seName) {
    const data = await getStockEntryDetails(seName)
    const items = data.items || []
    requiredItemsTable.value = items.map(item => ({
      item_code: item.item_code,
      picked_qty: item.qty || 0
    }))
    const batchSet = new Set()
    items.forEach(item => { if (item.batch_no) batchSet.add(String(item.batch_no)) })
    batches.value = Array.from(batchSet).map(b => ({ label: b, value: b }))
  }

  async function fetchBatchDetails(batchName) {
    selectedBatchName.value = batchName
    const rolls = await getRollsForBatch(batchName)
    rollNos.value = rolls.filter(r => r.roll_no).map(r => ({ label: r.roll_no, value: r.roll_no }))
    if (rolls.length && rolls[0].item_code) {
      requiredItemsTable.value = [{ item_code: rolls[0].item_code, picked_qty: 0 }]
    }
  }

  async function loadBatchesForProject(project, workOrder) {
    if (!project) return
    try {
      const rows = await getBatchesForProject(project, (isGKFProduction.value || selectedPickType.value === 'To Work Order') ? null : workOrder)
      batches.value = rows.map(b => ({ label: b.batch_id || b.name, value: b.batch_id || b.name }))
    } catch (err) {
      console.warn('loadBatchesForProject failed:', err.message)
      batches.value = []
    }
  }

  // ── Job Card selection: scopes the batch/roll dropdowns to that card ────
  async function loadJobCardsForWorkOrder(workOrderName) {
    if (!workOrderName) return
    try {
      const rows = await getJobCardsForWorkOrder(workOrderName)
      jobCards.value = rows.map(jc => ({ label: jc.name, value: jc.name }))
    } catch (err) {
      console.warn('loadJobCardsForWorkOrder failed:', err.message)
      jobCards.value = []
    }
  }

  async function onJobCardSelect() {
    const jobCardName = selectedJobCardName.value
    selectedBatchName.value = ''
    rollNos.value = []
    jobCardBatches.value = []
    jobCardRollMap = new Map()
    allRollsForJobCard = []
    if (!jobCardName) return

    loading.value = true
    try {
      const rows = await getRollsForJobCard(jobCardName)
      jobCardRollMap = new Map()
      allRollsForJobCard = []
      for (const roll of rows) {
        const batch = roll.batch_no
        const rollNo = roll.roll_no
        if (!batch || !rollNo) continue
        if (!jobCardRollMap.has(batch)) jobCardRollMap.set(batch, [])
        jobCardRollMap.get(batch).push(rollNo)
        allRollsForJobCard.push(rollNo)
      }
      jobCardBatches.value = Array.from(jobCardRollMap.keys())
      batches.value = jobCardBatches.value.map(b => ({ label: b, value: b }))

      if (jobCardBatches.value.length === 1) {
        selectedBatchName.value = jobCardBatches.value[0]
        applyJobCardRollFilter(selectedBatchName.value)
      }
    } catch (err) {
      console.warn('loadRollsForJobCard failed:', err.message)
      rollNos.value = []
    } finally {
      loading.value = false
    }
  }

  function onJobCardClear() {
    selectedJobCardName.value = ''
    jobCardBatches.value = []
    jobCardRollMap = new Map()
    allRollsForJobCard = []
    selectedBatchName.value = ''
    rollNos.value = []
    // Restore the full project/work-order batch list
    if (selectedDocumentName.value && selectedProject.value) {
      loadBatchesForProject(selectedProject.value, selectedDocumentName.value)
    }
  }

  function applyJobCardRollFilter(batchName) {
    const rolls = jobCardRollMap.get(batchName) || []
    rollNos.value = rolls.map(r => ({ label: r, value: r }))
  }

  // ── Batch selected: load its rolls (GKF batches, Job-Card-filtered, or
  //    ordinary live lookup) ───────────────────────────────────────────────
  async function onBatchSelect() {
    const batchName = selectedBatchName.value
    if (!batchName) return

    // GKF item under "To Work Order": the whole batch is transferred as one
    // unit — the "roll" dropdown offers only the batch itself, and picking
    // it prompts for a quantity instead of scanning individual rolls.
    if (isGKFProduction.value && selectedPickType.value === 'To Work Order') {
      try {
        const doc = await getBatchDetails(batchName)
        batchItemCode.value = doc.item_code || doc.item
        rollNos.value = [{ label: batchName, value: batchName }]
      } catch (err) {
        console.error('getBatchDetails failed:', err)
      }
      return
    }

    // Job Card filter active — use the pre-built roll map, no network call.
    if (selectedJobCardName.value && jobCardRollMap.size > 0) {
      applyJobCardRollFilter(batchName)
      return
    }

    // Default — live lookup of rolls for this batch.
    try {
      const rolls = await getRollsForBatch(batchName)
      const uniqueRolls = new Map()
      rolls.filter(r => r.roll_no).forEach(r => {
        if (!uniqueRolls.has(r.roll_no)) uniqueRolls.set(r.roll_no, { label: r.roll_no, value: r.roll_no })
      })
      rollNos.value = Array.from(uniqueRolls.values())
    } catch (err) {
      console.warn('onBatchSelect getRollsForBatch failed:', err.message)
      rollNos.value = []
    }
  }

  // ── Roll No selected ─────────────────────────────────────────────────────
  async function onRollNoSelect(rollNo) {
    if (!rollNo) return
    if (isGKFProduction.value && selectedPickType.value === 'To Work Order') {
      await promptForBatchQuantity(rollNo) // rollNo === the batch name here
    } else {
      await fetchRollDetails(rollNo)
    }
  }

  async function fetchRollDetails(rollNo) {
    if (selectedJobCardName.value && allRollsForJobCard.length && !allRollsForJobCard.includes(rollNo)) {
      throw new Error(`Roll ${rollNo} does not belong to Job Card ${selectedJobCardName.value}`)
    }

    const roll = await findRollByRollNo(rollNo)
    if (!roll) throw new Error(`Roll not found: ${rollNo}`)

    const qty = (roll.stock_uom || '').toLowerCase() === 'pcs' ? (roll.total_qty || 0) : (roll.roll_weight || 0)
    const rollData = {
      roll_no: roll.roll_no || rollNo,
      item_code: roll.item_code,
      warehouse: selectedSourceWarehouse.value || '',
      batch_no: roll.batch,
      qty,
      uom: roll.stock_uom || 'Kgs'
    }

    if (rollWiseReportTable.value.some(r => r.roll_no === rollData.roll_no)) {
      throw new Error('This roll has already been added.')
    }

    rollWiseReportTable.value.push(rollData)
    updatePickedQuantities()
    calculateTotals()
    return rollData
  }

  async function promptForBatchQuantity(batchNo) {
    const input = window.prompt(`Enter quantity for batch ${batchNo} (${batchItemCode.value}), in Kgs:`)
    if (input === null) return // cancelled
    const qty = parseFloat(input)
    if (isNaN(qty) || qty <= 0) throw new Error('Please enter a valid quantity')

    const entry = {
      roll_no: batchNo,
      item_code: batchItemCode.value,
      warehouse: selectedSourceWarehouse.value || '',
      batch_no: batchNo,
      qty,
      uom: 'Kgs'
    }
    if (rollWiseReportTable.value.some(r => r.roll_no === entry.roll_no)) {
      throw new Error('This batch has already been added.')
    }
    rollWiseReportTable.value.push(entry)
    updatePickedQuantities()
    calculateTotals()
  }

  // ── Barcode / manual roll-no input — parses "item_code#batch#roll_no"
  //    (same delimiter format the Ionic app's QR codes use), falling back
  //    to treating the raw text as a roll number. ─────────────────────────
  async function handleBarcodeInput(value) {
    const parts = String(value).split('#')
    const rollNo = parts.length >= 3 ? parts[2] : value
    await onRollNoSelect(rollNo)
    return { type: 'roll', roll_no: rollNo }
  }

  // ── Manual Roll Pick: preload recent rolls so the dropdown isn't empty ──
  async function loadRecentRolls() {
    try {
      const rolls = await getRecentRolls()
      rollNos.value = rolls.filter(r => r.roll_no).map(r => ({ label: r.roll_no, value: r.roll_no }))
    } catch (err) {
      console.warn('loadRecentRolls failed:', err.message)
      rollNos.value = []
    }
  }

  // ── Required-items remaining-qty tracking — reduces (not adds to) the
  //    displayed remaining quantity as rolls are picked, mirrors
  //    updatePickedQuantities() exactly. ───────────────────────────────────
  function updatePickedQuantities() {
    requiredItemsTable.value.forEach(reqItem => {
      let totalPicked = 0
      rollWiseReportTable.value.forEach(roll => {
        if (roll.item_code === reqItem.item_code) totalPicked += Number(roll.qty) || 0
      })

      if (selectedPickType.value === 'To Work Order') {
        const required = Number(reqItem.required_qty) || 0
        const transferred = Number(reqItem.transferred_qty) || 0
        reqItem.picked_qty = Math.max(0, required - transferred - totalPicked)
      } else if (selectedPickType.value === 'To Subcontracting Order') {
        const required = Number(reqItem.required_qty) || 0
        const supplied = Number(reqItem.supplied_qty) || 0
        reqItem.picked_qty = Math.max(0, required - supplied - totalPicked)
      } else {
        const initialQty = Number(reqItem.required_qty) || Number(reqItem.picked_qty) || 0
        reqItem.picked_qty = Math.max(0, initialQty - totalPicked)
      }
    })
  }

  function calculateTotals() {
    totalPickedQty.value = requiredItemsTable.value.reduce((sum, i) => sum + (Number(i.picked_qty) || 0), 0)
    totalWeight.value = rollWiseReportTable.value.reduce((sum, i) => sum + (Number(i.qty) || 0), 0)
  }

  function removeRoll(index) {
    rollWiseReportTable.value.splice(index, 1)
    updatePickedQuantities()
    calculateTotals()
  }

  // ── Validation — mirrors validateFormByPickType() ────────────────────────
  function validateFormByPickType() {
    const t = selectedPickType.value
    if (['From Work Order', 'To Work Order', 'From Purchase Order',
         'To Subcontracting Order', 'From Subcontracting Order', 'From Stock Entry'].includes(t)) {
      if (!selectedDocumentName.value) return `Please select a ${docLabel.value}`
    }
    if (t === 'From Batch' && !selectedBatchName.value) return 'Please select a Batch'
    if (!selectedTargetWarehouse.value || !selectedSourceWarehouse.value) {
      return 'Please select both Target and Source Warehouse'
    }
    return null
  }

  // ── Submit ────────────────────────────────────────────────────────────
  async function submitPickEntry(postingDate) {
    if (!rollWiseReportTable.value.length) throw new Error('Please add at least one roll to the report table')
    const validationError = validateFormByPickType()
    if (validationError) throw new Error(validationError)

    const payload = {
      posting_date: postingDate,
      pick_type: selectedPickType.value,
      document: selectedDocumentName.value,
      project: selectedProject.value,
      target_warehouse: selectedTargetWarehouse.value,
      source_warehouse: selectedSourceWarehouse.value,
      from_work_order: selectedFromWorkOrder.value,
      from_subcontracting: selectedFromSubcontracting.value,
      batch_no: selectedBatchName.value,
      rolls: rollWiseReportTable.value.map(roll => ({
        roll_no: roll.roll_no,
        item_code: roll.item_code,
        warehouse: roll.warehouse,
        batch_no: roll.batch_no,
        qty: roll.qty,
        uom: roll.uom
      })),
      // Plain-mapped (not the raw reactive ref) so this is always a clonable
      // array of plain objects — same reasoning as `rolls` above.
      required_items: requiredItemsTable.value.map(item => ({
        item_code: item.item_code,
        required_qty: item.required_qty,
        transferred_qty: item.transferred_qty,
        supplied_qty: item.supplied_qty,
        stock_uom: item.stock_uom,
        picked_qty: item.picked_qty
      }))
    }

    submitting.value = true
    try {
      if (isOnline.value) {
        try {
          const res = await callMethod('pranera_knit.api.knit.create_roll_picking_entry', payload)
          return res?.message || res?.data
        } catch (err) {
          // Queue for offline retry, but never let a queuing failure mask
          // the real error from the server — that's the one the user
          // actually needs to see (e.g. an ERPNext validation message).
          try {
            await enqueue('createRollPickingEntry', 'POST', payload)
          } catch (queueErr) {
            console.error('Failed to queue pick entry for offline retry:', queueErr)
          }
          throw err
        }
      } else {
        await enqueue('createRollPickingEntry', 'POST', payload)
        return { queued: true }
      }
    } finally {
      submitting.value = false
    }
  }

  function reset() {
    selectedPickType.value = ''
    onPickTypeChange()
  }

  return {
    PICK_TYPES,
    selectedPickType, selectedDocumentName, selectedProject,
    selectedTargetWarehouse, selectedSourceWarehouse,
    selectedBatchName, selectedJobCardName,
    selectedFromWorkOrder, selectedFromSubcontracting,
    isGKFProduction, productionItem, batchItemCode,
    loading, submitting,
    workOrders, purchaseOrders, subcontractingOrders, stockEntries, warehouses,
    batches, rollNos, jobCards, jobCardBatches,
    requiredItemsTable, rollWiseReportTable, totalPickedQty, totalWeight,
    docLabel, currentDocOptions,
    showField, showRequiredQtyColumn, showTransferredQtyColumn,
    showSuppliedQtyColumn, showStockUomColumn,
    loadDropdowns, onPickTypeChange, onDocumentSelect,
    onJobCardSelect, onJobCardClear, onBatchSelect, onRollNoSelect,
    handleBarcodeInput, removeRoll, submitPickEntry, reset
  }
})
