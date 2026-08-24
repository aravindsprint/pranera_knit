<template>
  <div class="page">
    <AppHeader title="Roll-wise Pick List" active="pick-list" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="page-content">
      <div v-if="!isOnline" class="offline-banner">🔌 Offline — pick entries will be queued until you're back online</div>

      <!-- Pick Type selector -->
      <div class="card">
        <label class="form-label">Pick Type <span class="req">*</span></label>
        <AutoComplete
          v-model="store.selectedPickType"
          :options="store.PICK_TYPES"
          placeholder="Select pick type"
          @change="onPickTypeChange"
        />
      </div>

      <!-- Document selector based on pick type -->
      <div class="card" v-if="store.showField('document')">
        <label class="form-label">{{ store.docLabel }} <span class="req">*</span></label>
        <AutoComplete
          v-model="store.selectedDocumentName"
          :options="store.currentDocOptions"
          :placeholder="`Search ${store.docLabel}...`"
          @change="onDocumentSelect"
        />
      </div>

      <!-- Project (read-only, auto-filled from the selected document) -->
      <div class="card" v-if="store.showField('project') && store.selectedProject">
        <label class="form-label">Project</label>
        <input class="form-input" :value="store.selectedProject" readonly />
      </div>

      <!-- Production item + GKF info banner -->
      <div class="card" v-if="store.productionItem && (store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order')">
        <label class="form-label">Production Item</label>
        <input class="form-input" :value="store.productionItem" readonly />
        <div v-if="store.isGKFProduction" class="info-banner">
          <i class="pi pi-info-circle"></i>
          <span v-if="store.selectedPickType === 'To Work Order'">
            <strong>GKF Item:</strong> transfer is done by batch, not individual rolls
          </span>
          <span v-else>
            <strong>GKF Item:</strong> transfer is done by individual rolls
          </span>
        </div>
      </div>

      <!-- Job Card (optional roll filter, only for Work Order pick types) -->
      <div class="card" v-if="store.showField('jobCard') && store.selectedDocumentName">
        <label class="form-label">Job Card</label>
        <div v-if="!store.jobCards.length" class="hint-text">No job cards found for this work order</div>
        <AutoComplete
          v-else
          v-model="store.selectedJobCardName"
          :options="store.jobCards"
          placeholder="Select Job Card (Optional)"
          @change="onJobCardChange"
        />
        <div v-if="store.selectedJobCardName" class="job-card-badge">
          <i class="pi pi-filter"></i>
          <span class="job-card-badge__text">Rolls filtered by: <strong>{{ store.selectedJobCardName }}</strong></span>
          <button class="badge-clear" @click="onJobCardClear">
            <i class="pi pi-times-circle"></i>
          </button>
        </div>
      </div>

      <!-- Target / Source Warehouse -->
      <div class="card" v-if="store.showField('targetWarehouse') || store.showField('sourceWarehouse')">
        <div class="form-group" v-if="store.showField('targetWarehouse')">
          <label class="form-label">Target Warehouse <span class="req">*</span></label>
          <AutoComplete v-model="store.selectedTargetWarehouse" :options="store.warehouses" placeholder="Search warehouse..." />
        </div>
        <div class="form-group" v-if="store.showField('sourceWarehouse')">
          <label class="form-label">Source Warehouse <span class="req">*</span></label>
          <AutoComplete v-model="store.selectedSourceWarehouse" :options="store.warehouses" placeholder="Search warehouse..." />
        </div>
      </div>

      <!-- From Work Order / From Subcontracting Order (Subcontracting pick type only) -->
      <div class="card" v-if="store.showField('fromWorkOrder') || store.showField('fromSubcontracting')">
        <div class="form-group" v-if="store.showField('fromWorkOrder')">
          <label class="form-label">From Work Order</label>
          <AutoComplete v-model="store.selectedFromWorkOrder" :options="store.workOrders" placeholder="Select From Work Order (Optional)" />
        </div>
        <div class="form-group" v-if="store.showField('fromSubcontracting')">
          <label class="form-label">From Subcontracting Order</label>
          <AutoComplete v-model="store.selectedFromSubcontracting" :options="store.subcontractingOrders" placeholder="Select From Subcontracting Order (Optional)" />
        </div>
      </div>

      <!-- Required Items table (hidden for "From Work Order" and "From Batch") -->
      <div class="card" v-if="store.requiredItemsTable.length && store.selectedPickType !== 'From Work Order' && store.selectedPickType !== 'From Batch'">
        <h2 class="section-title">Required Items</h2>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Item Code</th>
                <th v-if="store.showRequiredQtyColumn()">Required Qty</th>
                <th v-if="store.showTransferredQtyColumn()">Transferred Qty</th>
                <th v-if="store.showSuppliedQtyColumn()">Supplied Qty</th>
                <th v-if="store.showStockUomColumn()">UOM</th>
                <th>Remaining Qty</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in store.requiredItemsTable" :key="item.item_code">
                <td>{{ item.item_code }}</td>
                <td v-if="store.showRequiredQtyColumn()">{{ fmt(item.required_qty) }}</td>
                <td v-if="store.showTransferredQtyColumn()">{{ fmt(item.transferred_qty) }}</td>
                <td v-if="store.showSuppliedQtyColumn()">{{ fmt(item.supplied_qty) }}</td>
                <td v-if="store.showStockUomColumn()">{{ item.stock_uom }}</td>
                <td :class="{ highlight: item.picked_qty > 0 }">{{ fmt(item.picked_qty) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td><strong>Total</strong></td>
                <td v-if="store.showRequiredQtyColumn()"></td>
                <td v-if="store.showTransferredQtyColumn()"></td>
                <td v-if="store.showSuppliedQtyColumn()"></td>
                <td v-if="store.showStockUomColumn()"></td>
                <td><strong>{{ fmt(store.totalPickedQty) }}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Batch selector -->
      <div class="card" v-if="store.showField('batchNo')">
        <label class="form-label">Batch No <span class="req">*</span></label>
        <div v-if="store.selectedJobCardName && !store.jobCardBatches.length" class="hint-text warn">
          <i class="pi pi-exclamation-triangle"></i> No batches found for job card: {{ store.selectedJobCardName }}
        </div>
        <div v-else-if="store.selectedJobCardName && store.jobCardBatches.length" class="hint-text">
          <i class="pi pi-filter"></i>
          <span>Showing {{ store.jobCardBatches.length }} batch(es) for job card: <strong>{{ store.selectedJobCardName }}</strong></span>
        </div>
        <AutoComplete
          v-model="store.selectedBatchName"
          :options="store.batches"
          placeholder="Select Batch"
          @change="onBatchChange"
        />
      </div>

      <!-- Roll No / Barcode — scan-only entry, no manual "Type or Select" option -->
      <div class="card" v-if="store.showField('rollNo')">
        <label class="form-label">
          {{ store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Batch' : 'Roll No' }}
          <span class="req">*</span>
        </label>

        <div v-if="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName" class="hint-text warn">
          <i class="pi pi-info-circle"></i> Please select a batch first
        </div>
        <div v-else-if="store.selectedBatchName && store.rollNos.length && store.selectedJobCardName" class="hint-text ok">
          <i class="pi pi-check-circle"></i>
          <span>{{ store.rollNos.length }} roll(s) — filtered by Job Card: <strong>{{ store.selectedJobCardName }}</strong> / Batch: <strong>{{ store.selectedBatchName }}</strong></span>
        </div>
        <div v-else-if="store.selectedBatchName && store.rollNos.length" class="hint-text ok">
          <i class="pi pi-check-circle"></i>
          <span>{{ store.rollNos.length }} roll(s) available for batch: <strong>{{ store.selectedBatchName }}</strong></span>
        </div>
        <div v-else-if="store.selectedBatchName && !store.rollNos.length" class="hint-text warn">
          <i class="pi pi-exclamation-triangle"></i> No rolls found for this selection
        </div>

        <!-- Camera scan only — no manual typing, no hardware-wedge text field.
             The Scan button opens the device camera to read the roll's QR/barcode. -->
        <div class="scan-row">
          <button
            class="btn btn-primary btn-scan btn-full"
            @click="openCameraScanner"
            :disabled="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName"
          >
            <i class="pi pi-camera"></i>
            <span>Scan</span>
          </button>
        </div>
        <div class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span>Tap <strong>Scan</strong> to open your camera and scan the roll's barcode</span>
        </div>
      </div>

      <!-- Camera scanner pop-up -->
      <transition name="modal-fade">
        <div v-if="showScannerModal" class="modal-overlay" @click.self="closeCameraScanner">
          <div class="modal-box scanner-box">
            <h3 class="modal-title">Scan Roll Barcode</h3>
            <div id="camera-scan-region" class="camera-region"></div>
            <div v-if="scannerError" class="error-banner" style="margin-top:12px">
              <i class="pi pi-exclamation-triangle"></i> {{ scannerError }}
            </div>
            <button class="btn btn-outline btn-full" style="margin-top:14px" @click="closeCameraScanner">Cancel</button>
          </div>
        </div>
      </transition>

      <!-- Roll Wise Report table — becomes a stacked card list on phones so
           nothing gets squeezed into an unreadable, horizontally-scrolled row -->
      <div class="card" v-if="store.rollWiseReportTable.length">
        <h2 class="section-title">Roll Wise Report</h2>
        <div class="table-wrap">
          <table class="data-table responsive-table">
            <thead>
              <tr>
                <th>{{ store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Batch' : 'Roll No' }}</th>
                <th>Item Code</th>
                <th>Warehouse</th>
                <th>Batch No</th>
                <th>Qty</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(roll, i) in store.rollWiseReportTable" :key="roll.roll_no">
                <td :data-label="store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Batch' : 'Roll No'">{{ roll.roll_no }}</td>
                <td data-label="Item Code">{{ roll.item_code }}</td>
                <td data-label="Warehouse">{{ roll.warehouse }}</td>
                <td data-label="Batch No">{{ roll.batch_no }}</td>
                <td data-label="Qty">{{ fmt(roll.qty) }}</td>
                <td class="cell-action" data-label="Action">
                  <button class="row-remove" @click="store.removeRoll(i)">
                    <i class="pi pi-trash"></i>
                    <span class="row-remove-label">Remove</span>
                  </button>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="4"><strong>Total Weight</strong></td>
                <td><strong>{{ fmt(store.totalWeight) }}</strong></td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Submit -->
      <div class="card" v-if="store.selectedPickType">
        <div class="form-group">
          <label class="form-label">Posting Date <span class="req">*</span></label>
          <input v-model="postingDate" type="date" class="form-input" />
        </div>

        <button class="btn btn-primary btn-full" @click="submit" :disabled="store.submitting || !store.rollWiseReportTable.length">
          <i v-if="store.submitting" class="pi pi-spin pi-spinner"></i>
          {{ store.submitting ? 'Submitting...' : 'Create Pick Entry' }}
        </button>

        <div v-if="errorMsg" class="error-banner" style="margin-top:12px">
          <i class="pi pi-exclamation-triangle"></i> {{ errorMsg }}
        </div>
      </div>
    </div>

    <!-- Submission success pop-up -->
    <transition name="modal-fade">
      <div v-if="showSuccessModal" class="modal-overlay" @click.self="closeSuccessModal">
        <div class="modal-box">
          <i class="pi pi-check-circle modal-icon"></i>
          <h3 class="modal-title">Pick Entry Submitted</h3>
          <p class="modal-msg">{{ successMsg }}</p>
          <div v-if="submittedDocNo" class="modal-docno">{{ submittedDocNo }}</div>
          <button class="btn btn-primary btn-full" @click="closeSuccessModal">OK</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { onMounted } from 'vue'
import { usePickListStore } from '@/stores/pickList'
import { isOnline, syncLookupTables } from '@/composables/useSync'
import { Html5Qrcode } from 'html5-qrcode'
import moment from 'moment'

const auth = useAuthStore()
const store = usePickListStore()

const postingDate = ref(moment().format('YYYY-MM-DD'))
const successMsg = ref('')
const errorMsg = ref('')
const showSuccessModal = ref(false)
const submittedDocNo = ref('')

// ── Camera barcode/QR scanner ────────────────────────────────────────────
const showScannerModal = ref(false)
const scannerError = ref('')
let html5QrCode = null

onMounted(async () => {
  // Load whatever's cached immediately so the page isn't blank...
  await store.loadDropdowns()
  // ...then pull a fresh sync if we're online, so newly created/edited
  // documents (work orders, POs, etc.) show up without waiting for the
  // background 10s sync timer. Reload dropdowns again once it lands.
  if (isOnline.value) {
    await syncLookupTables()
    await store.loadDropdowns()
  }
})

function fmt(v) {
  const n = Number(v || 0)
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function onPickTypeChange() {
  store.onPickTypeChange()
  successMsg.value = ''
  errorMsg.value = ''
}

async function onDocumentSelect() {
  errorMsg.value = ''
  if (!store.selectedDocumentName) return
  try {
    await store.onDocumentSelect()
  } catch (err) {
    errorMsg.value = 'Failed to load document details: ' + err.message
  }
}

async function onJobCardChange() {
  errorMsg.value = ''
  try {
    await store.onJobCardSelect()
  } catch (err) {
    errorMsg.value = err.message
  }
}

function onJobCardClear() {
  store.onJobCardClear()
}

async function onBatchChange() {
  errorMsg.value = ''
  try {
    await store.onBatchSelect()
  } catch (err) {
    errorMsg.value = err.message
  }
}

// ── Camera scanner ────────────────────────────────────────────────────────
async function openCameraScanner() {
  scannerError.value = ''
  showScannerModal.value = true
  await nextTick()
  try {
    html5QrCode = new Html5Qrcode('camera-scan-region')
    await html5QrCode.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
      onCameraScanSuccess,
      () => {} // per-frame decode misses are expected — ignore them
    )
  } catch (err) {
    scannerError.value = 'Could not access the camera: ' + (err?.message || err)
  }
}

async function stopCameraScanner() {
  if (!html5QrCode) return
  try {
    if (html5QrCode.isScanning) await html5QrCode.stop()
    html5QrCode.clear()
  } catch (err) {
    console.warn('Failed to stop camera scanner:', err)
  }
  html5QrCode = null
}

async function closeCameraScanner() {
  await stopCameraScanner()
  showScannerModal.value = false
  scannerError.value = ''
}

async function onCameraScanSuccess(decodedText) {
  await stopCameraScanner()
  showScannerModal.value = false
  errorMsg.value = ''
  try {
    await store.handleBarcodeInput(decodedText)
  } catch (err) {
    errorMsg.value = err.message
  }
}

onBeforeUnmount(() => {
  stopCameraScanner()
})

async function submit() {
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const result = await store.submitPickEntry(postingDate.value)
    submittedDocNo.value = result?.stock_entry || ''
    successMsg.value = result?.queued
      ? 'Saved offline — will sync when online.'
      : 'Pick entry created successfully.'
    showSuccessModal.value = true
    store.reset()
    postingDate.value = moment().format('YYYY-MM-DD')
  } catch (err) {
    errorMsg.value = 'Error: ' + err.message
  }
}

function closeSuccessModal() {
  showSuccessModal.value = false
  successMsg.value = ''
  submittedDocNo.value = ''
}
</script>

<style scoped>
.offline-banner {
  background: #fef3c7; color: #92400e; padding: 10px 14px; border-radius: 8px;
  font-size: 13px; margin-bottom: 12px; text-align: center;
}
.req { color: #dc2626; }
.form-group + .form-group { margin-top: 12px; }
.section-title { font-size: 15px; font-weight: 700; margin-bottom: 12px; }
.info-banner {
  margin-top: 8px; background: #eff6ff; color: #1d4ed8; padding: 8px 12px;
  border-radius: 8px; font-size: 12px; display: flex; align-items: center; gap: 6px;
}
.hint-text {
  font-size: 12px; color: #64748b; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 6px;
}
.hint-text i { margin-top: 1px; flex-shrink: 0; }
.hint-text span { flex: 1; min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }
.hint-text.warn { color: #b45309; }
.hint-text.ok { color: #0f6e56; }
.job-card-badge {
  margin-top: 8px; background: #f0fdf4; color: #166534; padding: 6px 10px;
  border-radius: 8px; font-size: 12px; display: flex; align-items: flex-start; gap: 6px;
}
.job-card-badge > i { margin-top: 1px; flex-shrink: 0; }
.job-card-badge__text { flex: 1; min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }
.badge-clear {
  margin-left: auto; background: none; border: none; color: #166534; cursor: pointer;
  display: flex; align-items: center; align-self: center; flex-shrink: 0;
}
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.data-table thead th { color: #64748b; font-weight: 600; font-size: 11px; text-transform: uppercase; }
.data-table tfoot td { border-top: 1.5px solid #e2e8f0; border-bottom: none; }
.data-table td.highlight { color: #0f6e56; font-weight: 700; }
.row-remove {
  background: none; border: 1px solid #fecaca; color: #dc2626; cursor: pointer;
  display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 8px;
  font-size: 12px; font-weight: 600; white-space: nowrap;
}
.row-remove:hover { background: #fef2f2; }
.row-remove-label { display: inline; }
.error-banner {
  background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}

/* Scan button — full-width, generous touch target */
.scan-row { display: flex; }
.btn-scan {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  white-space: nowrap; padding: 0 18px; font-weight: 700; min-height: 48px; font-size: 15px;
}

/* ── Mobile cleanup (phones) ─────────────────────────────────────────────── */
@media (max-width: 480px) {
  .btn-scan { min-height: 46px; font-size: 16px; }

  /* Roll Wise Report: turn the table into a stacked card list instead of a
     horizontally-scrolled table so nothing gets cut off or squeezed */
  .responsive-table thead { display: none; }
  .responsive-table, .responsive-table tbody, .responsive-table tr, .responsive-table td {
    display: block; width: 100%;
  }
  .responsive-table tbody tr {
    border: 1px solid var(--slate-200, #e2e8f0);
    border-radius: 10px;
    margin-bottom: 10px;
    padding: 6px 12px;
  }
  .responsive-table td {
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px; padding: 7px 0; border-bottom: 1px solid #f1f5f9; white-space: normal; text-align: right;
  }
  .responsive-table td:last-child { border-bottom: none; }
  .responsive-table td::before {
    content: attr(data-label); font-weight: 600; color: #64748b;
    font-size: 11px; text-transform: uppercase; text-align: left; flex-shrink: 0;
  }
  .responsive-table td.cell-action { justify-content: flex-end; }
  .responsive-table td.cell-action::before { content: none; }
  .responsive-table .row-remove { min-height: 36px; }
  .responsive-table tfoot { display: block; }
  .responsive-table tfoot tr { display: flex; justify-content: space-between; padding: 10px 4px 2px; }
  .responsive-table tfoot td { display: none; }
  .responsive-table tfoot td:nth-child(1),
  .responsive-table tfoot td:nth-child(2) { display: block; border: none; padding: 0; }
}

/* Submission success pop-up */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 500; padding: 20px;
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 24px; width: 100%; max-width: 360px;
  text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
}
.modal-icon { font-size: 40px; color: #16a34a; margin-bottom: 10px; display: block; }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 8px; color: #0f172a; }
.modal-msg { font-size: 13px; color: #475569; margin: 0 0 14px; }
.modal-docno {
  font-size: 15px; font-weight: 700; color: #0f6e56; background: #f0fdf4;
  border-radius: 8px; padding: 10px 14px; margin-bottom: 18px; word-break: break-all;
}
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }

/* Camera scanner pop-up */
.scanner-box { max-width: 420px; }
.camera-region {
  width: 100%; aspect-ratio: 1 / 1; border-radius: 10px; overflow: hidden;
  background: #0f172a; position: relative;
}
/* html5-qrcode sets its own inline width/height/object-fit on the <video> —
   !important is needed so the box actually gets filled edge-to-edge instead
   of leaving background showing through as a letterbox bar. */
.camera-region :deep(video) {
  width: 100% !important; height: 100% !important; object-fit: cover !important;
  border-radius: 10px;
}
</style>
