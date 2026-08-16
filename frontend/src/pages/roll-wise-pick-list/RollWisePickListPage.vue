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
          Rolls filtered by: <strong>{{ store.selectedJobCardName }}</strong>
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
          <i class="pi pi-filter"></i> Showing {{ store.jobCardBatches.length }} batch(es) for job card: <strong>{{ store.selectedJobCardName }}</strong>
        </div>
        <AutoComplete
          v-model="store.selectedBatchName"
          :options="store.batches"
          placeholder="Select Batch"
          @change="onBatchChange"
        />
      </div>

      <!-- Roll No / Barcode -->
      <div class="card" v-if="store.showField('rollNo')">
        <label class="form-label">
          {{ store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Batch' : 'Roll No' }}
          <span class="req">*</span>
        </label>

        <div v-if="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName" class="hint-text warn">
          <i class="pi pi-info-circle"></i> Please select a batch first
        </div>
        <div v-else-if="store.selectedBatchName && store.rollNos.length && store.selectedJobCardName" class="hint-text ok">
          <i class="pi pi-check-circle"></i> {{ store.rollNos.length }} roll(s) — filtered by Job Card: <strong>{{ store.selectedJobCardName }}</strong> / Batch: <strong>{{ store.selectedBatchName }}</strong>
        </div>
        <div v-else-if="store.selectedBatchName && store.rollNos.length" class="hint-text ok">
          <i class="pi pi-check-circle"></i> {{ store.rollNos.length }} roll(s) available for batch: {{ store.selectedBatchName }}
        </div>
        <div v-else-if="store.selectedBatchName && !store.rollNos.length" class="hint-text warn">
          <i class="pi pi-exclamation-triangle"></i> No rolls found for this selection
        </div>

        <AutoComplete
          v-model="rollNoInput"
          :options="store.rollNos"
          :placeholder="store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Select Batch' : 'Type or Select Roll No'"
          :disabled="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName"
          @change="onRollNoChange"
        />

        <!-- Barcode scanner fallback — a keyboard-wedge scanner (or manual
             typing) types "item_code#batch#roll_no" here and hits Enter;
             mirrors the Ionic app's camera-scan QR format. -->
        <div style="display:flex;gap:8px;margin-top:8px">
          <input
            v-model="barcodeInput"
            type="text"
            class="form-input"
            placeholder="Scan or type roll no / barcode"
            :disabled="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName"
            @keyup.enter="onBarcodeInput"
          />
          <button
            class="btn btn-outline"
            @click="onBarcodeInput"
            :disabled="(store.selectedPickType === 'From Work Order' || store.selectedPickType === 'To Work Order') && !store.selectedBatchName"
          >
            <i class="pi pi-qrcode"></i>
          </button>
        </div>
      </div>

      <!-- Roll Wise Report table -->
      <div class="card" v-if="store.rollWiseReportTable.length">
        <h2 class="section-title">Roll Wise Report</h2>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ store.isGKFProduction && store.selectedPickType === 'To Work Order' ? 'Batch' : 'Roll No' }}</th>
                <th>Item Code</th>
                <th>Warehouse</th>
                <th>Batch No</th>
                <th>Qty</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(roll, i) in store.rollWiseReportTable" :key="roll.roll_no">
                <td>{{ roll.roll_no }}</td>
                <td>{{ roll.item_code }}</td>
                <td>{{ roll.warehouse }}</td>
                <td>{{ roll.batch_no }}</td>
                <td>{{ fmt(roll.qty) }}</td>
                <td>
                  <button class="row-remove" @click="store.removeRoll(i)">
                    <i class="pi pi-trash"></i>
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

        <div v-if="successMsg" class="success-banner" style="margin-top:12px">
          <i class="pi pi-check-circle"></i> {{ successMsg }}
        </div>
        <div v-if="errorMsg" class="error-banner" style="margin-top:12px">
          <i class="pi pi-exclamation-triangle"></i> {{ errorMsg }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'
import { ref, onMounted } from 'vue'
import { usePickListStore } from '@/stores/pickList'
import { isOnline, syncLookupTables } from '@/composables/useSync'
import moment from 'moment'

const auth = useAuthStore()
const store = usePickListStore()

const rollNoInput = ref('')
const barcodeInput = ref('')
const postingDate = ref(moment().format('YYYY-MM-DD'))
const successMsg = ref('')
const errorMsg = ref('')

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
  rollNoInput.value = ''
  barcodeInput.value = ''
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

async function onRollNoChange() {
  errorMsg.value = ''
  const rollNo = rollNoInput.value
  if (!rollNo) return
  try {
    await store.onRollNoSelect(rollNo)
  } catch (err) {
    errorMsg.value = err.message
  } finally {
    rollNoInput.value = ''
  }
}

async function onBarcodeInput() {
  const value = barcodeInput.value
  if (!value) return
  errorMsg.value = ''
  try {
    await store.handleBarcodeInput(value)
  } catch (err) {
    errorMsg.value = err.message
  } finally {
    barcodeInput.value = ''
  }
}

async function submit() {
  successMsg.value = ''
  errorMsg.value = ''
  try {
    const result = await store.submitPickEntry(postingDate.value)
    successMsg.value = result?.queued
      ? 'Saved offline — will sync when online'
      : `Pick entry created successfully${result?.stock_entry ? ` (Stock Entry: ${result.stock_entry})` : ''}`
    store.reset()
    rollNoInput.value = ''
    barcodeInput.value = ''
    postingDate.value = moment().format('YYYY-MM-DD')
  } catch (err) {
    errorMsg.value = 'Error: ' + err.message
  }
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
  font-size: 12px; color: #64748b; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.hint-text.warn { color: #b45309; }
.hint-text.ok { color: #0f6e56; }
.job-card-badge {
  margin-top: 8px; background: #f0fdf4; color: #166534; padding: 6px 10px;
  border-radius: 8px; font-size: 12px; display: flex; align-items: center; gap: 6px;
}
.badge-clear {
  margin-left: auto; background: none; border: none; color: #166534; cursor: pointer;
  display: flex; align-items: center;
}
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.data-table thead th { color: #64748b; font-weight: 600; font-size: 11px; text-transform: uppercase; }
.data-table tfoot td { border-top: 1.5px solid #e2e8f0; border-bottom: none; }
.data-table td.highlight { color: #0f6e56; font-weight: 700; }
.row-remove { background: none; border: none; color: #dc2626; cursor: pointer; display: flex; align-items: center; }
.success-banner {
  background: #dcfce7; color: #166534; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.error-banner {
  background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
</style>
