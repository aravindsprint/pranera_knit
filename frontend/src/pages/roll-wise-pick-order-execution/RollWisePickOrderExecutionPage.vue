<template>
  <div class="page">
    <AppHeader title="Pick Order Execution" active="pick-execution" :username="auth.username" :designation="auth.designation" :show-back="true" />
    <div class="page-content">

      <div v-if="store.orderLoading" class="card state-msg">
        <i class="pi pi-spin pi-spinner"></i> Loading Pick Order...
      </div>

      <div v-else-if="store.orderError" class="card state-msg error">
        <i class="pi pi-exclamation-triangle"></i> {{ store.orderError }}
      </div>

      <template v-else-if="store.order">
        <!-- Order summary -->
        <div class="card">
          <div class="order-title">{{ store.order.name }}</div>
          <div class="order-sub">
            {{ store.order.pick_type }}<span v-if="store.order.document_name"> · {{ store.order.document_name }}</span><span v-if="store.order.sales_order"> · {{ store.order.sales_order }}</span>
          </div>
          <div v-if="store.order.manufactured_qty" class="hint-text" style="margin-top:6px">
            <i class="pi pi-box"></i>
            <span>Manufactured Qty: {{ fmt(store.order.manufactured_qty) }} kg</span>
          </div>
          <div class="wh-row">
            <span>{{ store.sourceWarehouse || store.order.source_warehouse }}</span>
            <i class="pi pi-arrow-right"></i>
            <span>{{ store.targetWarehouse || store.order.target_warehouse }}</span>
          </div>
          <div v-if="store.order.batch_items && store.order.batch_items.length" class="hint-text">
            <i class="pi pi-list"></i>
            <span>Planned: {{ store.order.batch_items.map(b => `${b.batch} (${fmt(b.qty)} kg)`).join(', ') }}</span>
          </div>
          <div v-if="store.order.remarks" class="hint-text">
            <i class="pi pi-comment"></i>
            <span>{{ store.order.remarks }}</span>
          </div>
        </div>

        <!-- Target / progress -->
        <div class="card">
          <label class="form-label">Target Pick Qty</label>
          <div class="progress-row">
            <span class="progress-qty" :class="{ over: store.overTolerance, ok: store.withinTolerance }">
              {{ fmt(store.totalPickedQty) }}
            </span>
            <span class="progress-target">/ {{ fmt(store.order.pick_qty) }} kg</span>
          </div>
          <div class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Tolerance band: {{ fmt(store.order.tolerance_min) }} – {{ fmt(store.order.tolerance_max) }} kg</span>
          </div>
          <div v-if="store.order.already_picked_qty" class="hint-text">
            <i class="pi pi-history"></i>
            <span>{{ fmt(store.order.already_picked_qty) }} kg already picked in prior sessions</span>
          </div>
          <div v-if="store.overTolerance" class="error-banner" style="margin-top:8px">
            <i class="pi pi-exclamation-triangle"></i> Over tolerance — remove a roll before submitting
          </div>
        </div>

        <!-- Source warehouse -->
        <div class="card">
          <label class="form-label">Source Warehouse <span class="req">*</span></label>
          <AutoComplete
            :model-value="store.sourceWarehouse"
            :options="store.warehouses"
            placeholder="Search warehouse..."
            @change="onSourceWarehouseChange"
          />
          <div class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Defaults to the assignment's warehouse — change it if the rolls are actually sitting somewhere else. Saved automatically.</span>
          </div>
          <div v-if="warehouseSaveError" class="error-banner" style="margin-top:8px">
            <i class="pi pi-exclamation-triangle"></i> {{ warehouseSaveError }}
          </div>
        </div>

        <!-- Target warehouse -->
        <div class="card">
          <label class="form-label">Target Warehouse <span class="req">*</span></label>
          <AutoComplete
            :model-value="store.targetWarehouse"
            :options="store.warehouses"
            placeholder="Search warehouse..."
            @change="onTargetWarehouseChange"
          />
          <div class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Defaults to the assignment's target — change it if the material needs to land somewhere else. Saved automatically.</span>
          </div>
        </div>

        <!-- Scan -->
        <div class="card">
          <label class="form-label">
            Scan Rolls
            <span class="req">*</span>
          </label>
          <div class="hint-text ok">
            <i class="pi pi-check-circle"></i>
            <span>{{ store.scannedRolls.length }} roll(s) scanned this session</span>
          </div>

          <div class="scan-row">
            <button
              class="btn btn-primary btn-scan btn-full"
              @click="openCameraScanner"
              :disabled="!store.sourceWarehouse"
            >
              <i class="pi pi-camera"></i>
              <span>Scan</span>
            </button>
          </div>
          <div class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Scan freely until the total lands within the tolerance band above — each roll is validated as you scan it.</span>
          </div>
          <div v-if="scanError" class="error-banner" style="margin-top:10px">
            <i class="pi pi-exclamation-triangle"></i> {{ scanError }}
          </div>
        </div>

        <!-- Scanned this session -->
        <div class="card" v-if="store.scannedRolls.length">
          <h2 class="section-title">Scanned This Session</h2>
          <div class="roll-checklist">
            <div v-for="r in store.scannedRolls" :key="r.roll_no" class="roll-row roll-row--done">
              <i class="pi pi-check-circle"></i>
              <div class="roll-row__body">
                <div class="roll-row__no">Roll {{ r.roll_no }}</div>
                <div class="roll-row__meta">{{ r.item_code }} · {{ r.batch_no }} · {{ fmt(r.qty) }} {{ r.uom }}</div>
              </div>
              <button class="btn-remove" @click="onRemoveRoll(r.roll_no)" title="Remove">
                <i class="pi pi-times"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- Already picked in prior sessions -->
        <div class="card" v-if="store.order.already_picked_rolls && store.order.already_picked_rolls.length">
          <h2 class="section-title">Already Picked (Prior Sessions)</h2>
          <div class="roll-checklist">
            <div v-for="r in store.order.already_picked_rolls" :key="r.roll_no" class="roll-row roll-row--done">
              <i class="pi pi-check-circle"></i>
              <div class="roll-row__body">
                <div class="roll-row__no">Roll {{ r.roll_no }}</div>
                <div class="roll-row__meta">{{ r.item_code }} · {{ r.batch }} · {{ fmt(r.qty) }} {{ r.uom }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Submit -->
        <div class="card">
          <label class="form-label">Posting Date <span class="req">*</span></label>
          <input v-model="postingDate" type="date" class="form-input" />

          <button
            class="btn btn-primary btn-full" style="margin-top:14px"
            @click="submit"
            :disabled="!store.withinTolerance || !store.scannedRolls.length || store.submitting"
          >
            <i v-if="store.submitting" class="pi pi-spin pi-spinner"></i>
            {{ store.submitting ? 'Submitting...' : 'Create Pick Entry' }}
          </button>
          <div v-if="submitError" class="error-banner" style="margin-top:12px">
            <i class="pi pi-exclamation-triangle"></i> {{ submitError }}
          </div>
        </div>
      </template>

      <!-- Camera scanner pop-up -->
      <transition name="modal-fade">
        <div v-if="showScannerModal" class="modal-overlay" @click.self="closeCameraScanner">
          <div class="modal-box scanner-box">
            <h3 class="modal-title">Scan Roll Barcode</h3>
            <div id="pick-order-camera-scan-region" class="camera-region"></div>
            <div v-if="cameraError" class="error-banner" style="margin-top:12px">
              <i class="pi pi-exclamation-triangle"></i> {{ cameraError }}
            </div>
            <button class="btn btn-outline btn-full" style="margin-top:14px" @click="closeCameraScanner">Cancel</button>
          </div>
        </div>
      </transition>

      <!-- Submission success pop-up -->
      <transition name="modal-fade">
        <div v-if="showSuccessModal" class="modal-overlay" @click.self="closeSuccessModal">
          <div class="modal-box">
            <i class="pi pi-check-circle modal-icon"></i>
            <h3 class="modal-title">Pick Order Completed</h3>
            <p class="modal-msg">Pick entry created successfully.</p>
            <div v-if="submittedDocNo" class="modal-docno">{{ submittedDocNo }}</div>
            <button class="btn btn-primary btn-full" @click="closeSuccessModal">OK</button>
          </div>
        </div>
      </transition>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePickOrderStore } from '@/stores/pickOrder'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'
import { Html5Qrcode } from 'html5-qrcode'
import moment from 'moment'

const auth = useAuthStore()
const store = usePickOrderStore()
const route = useRoute()
const router = useRouter()

const postingDate = ref(moment().format('YYYY-MM-DD'))
const scanError = ref('')
const submitError = ref('')
const warehouseSaveError = ref('')
const showSuccessModal = ref(false)
const submittedDocNo = ref('')

function fmt(n) {
  return (Number(n) || 0).toFixed(2)
}

async function onSourceWarehouseChange(value) {
  warehouseSaveError.value = ''
  try {
    await store.setSourceWarehouse(value)
  } catch (err) {
    warehouseSaveError.value = 'Could not save Source Warehouse: ' + err.message
  }
}

async function onTargetWarehouseChange(value) {
  warehouseSaveError.value = ''
  try {
    await store.setTargetWarehouse(value)
  } catch (err) {
    warehouseSaveError.value = 'Could not save Target Warehouse: ' + err.message
  }
}

async function onRemoveRoll(rollNo) {
  scanError.value = ''
  try {
    await store.removeScannedRoll(rollNo)
  } catch (err) {
    scanError.value = err.message
  }
}

async function loadFromRoute() {
  const name = route.query.order
  if (!name) {
    store.orderError = 'No Pick Order specified'
    return
  }
  await store.loadOrder(name)
}

onMounted(() => {
  loadFromRoute()
  store.loadWarehouses()
})
watch(() => route.query.order, loadFromRoute)
onBeforeUnmount(() => { store.reset(); stopCameraScanner() })

// ── Camera scanner — identical pattern to RollWisePickListPage.vue ─────────
const showScannerModal = ref(false)
const cameraError = ref('')
let html5QrCode = null

async function openCameraScanner() {
  cameraError.value = ''
  scanError.value = ''
  showScannerModal.value = true
  await nextTick()
  try {
    html5QrCode = new Html5Qrcode('pick-order-camera-scan-region')
    await html5QrCode.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
      onCameraScanSuccess,
      () => {} // per-frame decode misses are expected — ignore them
    )
  } catch (err) {
    cameraError.value = 'Could not access the camera: ' + (err?.message || err)
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
  cameraError.value = ''
}

async function onCameraScanSuccess(decodedText) {
  await stopCameraScanner()
  showScannerModal.value = false
  scanError.value = ''
  try {
    await store.scanRoll(decodedText)
  } catch (err) {
    scanError.value = err.message
  }
}

// ── Submit ───────────────────────────────────────────────────────────────
async function submit() {
  submitError.value = ''
  try {
    const result = await store.submitOrder(postingDate.value)
    submittedDocNo.value = result?.stock_entry || ''
    showSuccessModal.value = true
  } catch (err) {
    submitError.value = 'Error: ' + err.message
  }
}

function closeSuccessModal() {
  showSuccessModal.value = false
  router.push('/knit-app/my-pick-orders')
}
</script>

<style scoped>
.page-content { padding: 16px; max-width: 640px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.state-msg {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  color: #64748b; padding: 32px 16px; text-align: center;
}
.state-msg.error { color: #991b1b; }

.order-title { font-weight: 700; font-size: 16px; color: #0f172a; }
.order-sub { font-size: 13px; color: #475569; margin-top: 2px; }
.wh-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #334155; margin-top: 8px; }

.form-label { display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
.req { color: #dc2626; }
.form-input {
  width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px;
  font-size: 14px; box-sizing: border-box;
}

.hint-text {
  font-size: 12px; color: #64748b; margin-bottom: 8px; display: flex; align-items: flex-start; gap: 6px;
}
.hint-text i { margin-top: 1px; flex-shrink: 0; }
.hint-text span { flex: 1; min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }
.hint-text.ok { color: #0f6e56; }

.scan-row { display: flex; margin-bottom: 8px; }
.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; padding: 10px; }
.btn-full { width: 100%; padding: 12px; }
.btn-scan {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-weight: 700; min-height: 48px; font-size: 15px;
}

.error-banner {
  background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px;
}

.progress-row { display: flex; align-items: baseline; gap: 6px; }
.progress-qty { font-size: 24px; font-weight: 800; color: #0f172a; }
.progress-qty.ok { color: #16a34a; }
.progress-qty.over { color: #dc2626; }
.progress-target { font-size: 14px; color: #64748b; }

.section-title { font-size: 14px; font-weight: 700; color: #0f172a; margin: 0 0 10px; }
.roll-checklist { display: flex; flex-direction: column; gap: 8px; }
.roll-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border: 1px solid #e2e8f0; border-radius: 10px; color: #94a3b8;
}
.btn-remove {
  background: none; border: none; color: #94a3b8; cursor: pointer;
  padding: 4px 6px; flex-shrink: 0; font-size: 14px;
}
.btn-remove:hover { color: #dc2626; }
.roll-row i { font-size: 18px; flex-shrink: 0; }
.roll-row--done { border-color: #bbf7d0; background: #f0fdf4; color: #166534; }
.roll-row--done i { color: #16a34a; }
.roll-row__body { flex: 1; min-width: 0; }
.roll-row__no { font-weight: 700; font-size: 13px; color: #0f172a; }
.roll-row--done .roll-row__no { color: #166534; }
.roll-row__meta { font-size: 12px; color: #64748b; overflow-wrap: anywhere; }

/* Camera scanner + success pop-ups */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 500; padding: 20px;
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 24px; width: 100%; max-width: 360px;
  text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
}
.scanner-box { max-width: 420px; }
.camera-region {
  width: 100%; aspect-ratio: 1 / 1; border-radius: 10px; overflow: hidden;
  background: #0f172a; position: relative;
}
.camera-region :deep(video) {
  width: 100% !important; height: 100% !important; object-fit: cover !important;
  border-radius: 10px;
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
</style>
