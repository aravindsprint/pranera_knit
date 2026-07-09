<template>
  <div class="page">
    <AppHeader title="Roll-wise Pick List" active="pick-list" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="page-content">
      <!-- Pick Type selector -->
      <div class="card">
        <label class="form-label">Pick Type</label>
        <select v-model="store.selectedPickType" class="form-input" @change="onPickTypeChange">
          <option value="">Select pick type</option>
          <option v-for="pt in PICK_TYPES" :key="pt" :value="pt">{{ pt }}</option>
        </select>
      </div>

      <!-- Document selector based on pick type -->
      <div class="card" v-if="store.selectedPickType">
        <label class="form-label">{{ docLabel }}</label>
        <input
          v-model="store.selectedDocumentName"
          list="doc-list"
          class="form-input"
          :placeholder="`Search ${docLabel}...`"
          @change="onDocumentSelect"
        />
        <datalist id="doc-list">
          <option v-for="opt in currentDocOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </datalist>
      </div>

      <!-- Barcode scanner (text input fallback for PWA) -->
      <div class="card" v-if="store.selectedPickType">
        <label class="form-label">Scan Barcode / Roll No</label>
        <div style="display:flex;gap:8px">
          <input
            v-model="barcodeInput"
            type="text"
            class="form-input"
            placeholder="Scan or type roll no"
            @keyup.enter="onBarcodeInput"
          />
          <button class="btn btn-outline" @click="onBarcodeInput">
            <i class="pi pi-qrcode"></i>
          </button>
        </div>
        <div v-if="scannedResult" class="scan-result">
          <i class="pi pi-check-circle" style="color:#0f6e56"></i>
          Found: <strong>{{ scannedResult.roll_no || scannedResult.value }}</strong>
        </div>
      </div>

      <!-- Document details & items -->
      <div class="card" v-if="store.documentDetails">
        <h2 class="section-title">{{ store.selectedDocumentName }}</h2>
        <div v-for="item in store.items" :key="item.name || item.item_code" class="item-row">
          <div>
            <div class="item-code">{{ item.item_code }}</div>
            <div class="item-name">{{ item.item_name }}</div>
          </div>
          <div class="item-qty">
            <span>{{ item.qty || item.required_qty }}</span>
            <span style="font-size:10px;color:#94a3b8">{{ item.stock_uom }}</span>
          </div>
        </div>
        <div v-if="!store.items.length" style="color:#94a3b8;font-size:13px;text-align:center;padding:16px">
          No items found
        </div>
      </div>

      <!-- Submit -->
      <div class="card" v-if="store.selectedDocumentName">
        <div class="form-group">
          <label class="form-label">Source Warehouse</label>
          <input v-model="sourceWarehouse" list="wh-list" class="form-input" placeholder="Search warehouse..." />
          <datalist id="wh-list">
            <option v-for="wh in store.warehouses" :key="wh.value" :value="wh.value" />
          </datalist>
        </div>
        <div class="form-group">
          <label class="form-label">Target Warehouse</label>
          <input v-model="targetWarehouse" list="wh-list2" class="form-input" placeholder="Search warehouse..." />
          <datalist id="wh-list2">
            <option v-for="wh in store.warehouses" :key="wh.value" :value="wh.value" />
          </datalist>
        </div>

        <button class="btn btn-primary btn-full" @click="submit" :disabled="submitting">
          <i v-if="submitting" class="pi pi-spin pi-spinner"></i>
          {{ submitting ? 'Submitting...' : 'Create Pick Entry' }}
        </button>

        <div v-if="successMsg" class="success-banner" style="margin-top:12px">
          <i class="pi pi-check-circle"></i> {{ successMsg }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePickListStore, PICK_TYPES } from '@/stores/pickList'
import moment from 'moment'
const auth = useAuthStore()

const router = useRouter()
const store = usePickListStore()

const barcodeInput = ref('')
const scannedResult = ref(null)
const sourceWarehouse = ref('')
const targetWarehouse = ref('')
const submitting = ref(false)
const successMsg = ref('')

onMounted(() => store.loadDropdowns())

const docLabel = computed(() => {
  const t = store.selectedPickType
  if (t?.includes('Work Order')) return 'Work Order'
  if (t?.includes('Purchase Order')) return 'Purchase Order'
  if (t?.includes('Subcontracting')) return 'Subcontracting Order'
  if (t === 'From Stock Entry') return 'Stock Entry'
  if (t === 'From Batch') return 'Batch'
  return 'Document'
})

const currentDocOptions = computed(() => {
  const t = store.selectedPickType
  if (t?.includes('Work Order')) return store.workOrders
  if (t?.includes('Purchase Order')) return store.purchaseOrders
  if (t?.includes('Subcontracting')) return store.subcontractingOrders
  if (t === 'From Stock Entry') return store.stockEntries
  if (t === 'From Batch') return store.batches
  return store.rollNos
})

function onPickTypeChange() {
  store.documentDetails = null
  store.selectedDocumentName = ''
  scannedResult.value = null
}

function onDocumentSelect() {
  if (store.selectedDocumentName) {
    store.loadDocumentDetails(store.selectedPickType, store.selectedDocumentName)
  }
}

async function onBarcodeInput() {
  if (!barcodeInput.value) return
  scannedResult.value = await store.handleBarcodeInput(barcodeInput.value)
  barcodeInput.value = ''
}

async function submit() {
  submitting.value = true
  successMsg.value = ''
  try {
    const result = await store.submitPickEntry({
      pick_type: store.selectedPickType,
      document_name: store.selectedDocumentName,
      source_warehouse: sourceWarehouse.value,
      target_warehouse: targetWarehouse.value,
      items: store.items,
      scanned_roll: scannedResult.value?.data?.roll_no || null,
      date: moment().format('YYYY-MM-DD')
    })
    successMsg.value = result.queued
      ? 'Saved offline — will sync when online'
      : 'Pick entry created successfully'
    store.reset()
    sourceWarehouse.value = ''
    targetWarehouse.value = ''
    scannedResult.value = null
  } catch (err) {
    alert('Error: ' + err.message)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.icon-btn { background: rgba(255,255,255,0.2); border: none; color: white; width: 36px; height: 36px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.section-title { font-size: 15px; font-weight: 700; margin-bottom: 12px; }
.item-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.item-code { font-size: 13px; font-weight: 600; }
.item-name { font-size: 11px; color: #64748b; }
.item-qty  { text-align: right; font-size: 14px; font-weight: 700; color: #0f6e56; display: flex; flex-direction: column; align-items: flex-end; }
.scan-result { margin-top: 8px; font-size: 13px; color: #1e293b; display: flex; align-items: center; gap: 6px; }
.success-banner { background: #dcfce7; color: #166534; padding: 10px; border-radius: 8px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 6px; }
</style>
