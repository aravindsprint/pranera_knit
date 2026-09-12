<template>
  <div class="cro-page">
    <AppHeader
      title="Create Rolls"
      active="create-rolls"
      :username="auth.username"
      :designation="auth.designation"
      :show-back="true"
    />

    <div class="cro-content">

      <!-- Tabs -->
      <div class="cro-tabs">
        <button class="cro-tab" :class="{ 'cro-tab--active': tab === 'cut' }" @click="setTab('cut')">
          ✂️ Cut Rolls
        </button>
        <button class="cro-tab" :class="{ 'cro-tab--active': tab === 'po' }" @click="setTab('po')">
          📥 Purchase Order
        </button>
        <button class="cro-tab" :class="{ 'cro-tab--active': tab === 'so' }" @click="setTab('so')">
          🤝 Subcontract Order
        </button>
      </div>

      <!-- ══════════════════════ CUT ROLLS ══════════════════════ -->
      <template v-if="tab === 'cut'">
        <div class="card">
          <div class="cro-card__title">Select Roll to Cut</div>
          <div class="form-group">
            <label class="form-label">Roll No / Item *</label>
            <div class="cro-autocomplete">
              <input
                class="form-input"
                v-model="cut.search"
                placeholder="Search roll no, item code or commercial name…"
                autocomplete="off"
                @input="onCutRollSearch"
                @focus="onCutRollSearch"
                @blur="cut.showDrop = false"
              />
              <div class="cro-dropdown" v-if="cut.showDrop">
                <div v-if="cut.searching" class="cro-dropdown__empty">Searching…</div>
                <template v-else-if="cut.options.length">
                  <div
                    v-for="r in cut.options"
                    :key="r.name"
                    class="cro-dropdown__item"
                    @mousedown.prevent="selectCutRoll(r)"
                  >
                    <div class="cro-dropdown__name">{{ r.name }}</div>
                    <div class="cro-dropdown__sub">
                      {{ r.item_code || '—' }}<span v-if="r.commercial_name"> · {{ r.commercial_name }}</span>
                    </div>
                  </div>
                </template>
                <div v-else-if="cut.search.trim()" class="cro-dropdown__empty">No matching rolls</div>
              </div>
            </div>
          </div>

          <div v-if="cut.selected" class="cro-detail-card">
            <div class="cro-detail-row"><span>Item Code</span><strong>{{ cut.selected.item_code || '—' }}</strong></div>
            <div class="cro-detail-row" v-if="cut.selected.commercial_name"><span>Commercial Name</span><strong>{{ cut.selected.commercial_name }}</strong></div>
            <div class="cro-detail-row" v-if="cut.selected.color"><span>Color</span><strong>{{ cut.selected.color }}</strong></div>
            <div class="cro-detail-row" v-if="cut.selected.width"><span>Width</span><strong>{{ cut.selected.width }}</strong></div>
            <div class="cro-detail-row" v-if="cut.selected.batch"><span>Batch</span><strong>{{ cut.selected.batch }}</strong></div>
            <div class="cro-detail-row">
              <span>Available {{ cutIsPcs ? 'Qty' : 'Weight' }}</span>
              <strong>{{ cutAvailable }} {{ cutIsPcs ? 'pcs' : 'kg' }}</strong>
            </div>
          </div>
        </div>

        <div class="card" v-if="cut.selected">
          <div class="cro-card__title">Cut Details</div>

          <div class="form-group">
            <label class="form-label">Qty to Cut ({{ cutIsPcs ? 'pcs' : 'kg' }}) *</label>
            <input
              class="form-input"
              type="number"
              :step="cutIsPcs ? 1 : 0.001"
              min="0"
              v-model="cut.qty"
              placeholder="0"
            />
            <div class="cro-hint" v-if="cut.qty !== ''">
              Remaining on source roll after cut: <strong>{{ cutRemainingPreview }} {{ cutIsPcs ? 'pcs' : 'kg' }}</strong>
            </div>
          </div>

          <div class="cro-field-grid">
            <div class="form-group">
              <label class="form-label">Knit Machine No</label>
              <select class="form-input" v-model="cut.machineNo">
                <option value="">— Same as source —</option>
                <option v-for="m in KNIT_MACHINES" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Shift No</label>
              <select class="form-input" v-model="cut.shiftNo">
                <option value="">— Same as source —</option>
                <option v-for="s in SHIFT_OPTIONS" :key="s" :value="s">{{ s }}</option>
              </select>
            </div>
          </div>

          <div class="alert alert-error" v-if="cut.error">⚠ {{ cut.error }}</div>

          <button class="btn btn-primary btn-full btn-lg" :disabled="!canSubmitCut || cut.submitting" @click="submitCut">
            <span v-if="cut.submitting" class="cro-spinner"></span>
            {{ cut.submitting ? 'Cutting…' : '✂ Cut Roll' }}
          </button>
        </div>
      </template>

      <!-- ══════════════════ PURCHASE ORDER / SUBCONTRACT ORDER ══════════════════ -->
      <template v-if="tab === 'po' || tab === 'so'">
        <div class="card">
          <div class="cro-card__title">{{ tab === 'po' ? 'Purchase Order' : 'Subcontracting Order' }}</div>

          <div class="form-group">
            <label class="form-label">{{ tab === 'po' ? 'Purchase Order' : 'Subcontracting Order' }} *</label>
            <AutoComplete
              v-model="order.selected"
              :options="orderOptions"
              :placeholder="`Search ${tab === 'po' ? 'Purchase Order' : 'Subcontracting Order'}…`"
              @change="onOrderChange"
            />
          </div>

          <div class="form-group" v-if="order.selected">
            <label class="form-label">Item Code *</label>
            <AutoComplete
              v-model="order.itemCode"
              :options="itemOptions"
              placeholder="Select Item"
              @change="onOrderItemChange"
            />
          </div>
        </div>

        <div class="card" v-if="order.item">
          <div class="cro-card__title">Item Details</div>
          <div class="cro-field-grid">
            <div class="form-group">
              <label class="form-label">Content</label>
              <input class="form-input" :value="order.item.item_name || ''" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Commercial Name</label>
              <input class="form-input" :value="order.item.commercial_name || ''" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Color</label>
              <input class="form-input" :value="order.item.color || ''" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Fabric/CC Width</label>
              <input class="form-input" :value="order.item.width || ''" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Stock UOM</label>
              <input class="form-input" :value="order.item.stock_uom || ''" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Project</label>
              <input class="form-input" :value="order.item.project || ''" readonly />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Batch No</label>
            <AutoComplete
              v-model="order.batch"
              :options="batchOptions"
              placeholder="Select Batch (optional)"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Actual Width</label>
            <input class="form-input" v-model="order.actualWidth" placeholder="Measured width" />
          </div>

          <div class="cro-field-grid">
            <div class="form-group">
              <label class="form-label">Roll Weight (kg)</label>
              <input class="form-input" type="number" step="0.001" min="0" v-model="order.rollWeight" placeholder="0.000" />
            </div>
            <div class="form-group">
              <label class="form-label">Roll Qty</label>
              <input class="form-input" type="number" step="1" min="0" v-model="order.rollQty" placeholder="0" />
            </div>
            <div class="form-group">
              <label class="form-label">Mistake Qty</label>
              <input class="form-input" type="number" step="1" min="0" v-model="order.mistakeQty" placeholder="0" />
            </div>
            <div class="form-group">
              <label class="form-label">Ok Qty</label>
              <input class="form-input" type="number" step="1" v-model="order.okQty" placeholder="0" />
            </div>
          </div>

          <div class="form-group" v-if="avgWeightPerPcs">
            <label class="form-label">Avg Weight Pcs</label>
            <input class="form-input" :value="avgWeightPerPcs" readonly />
          </div>

          <div class="alert alert-error" v-if="order.error">⚠ {{ order.error }}</div>

          <button class="btn btn-primary btn-full btn-lg" :disabled="order.submitting" @click="submitOrder">
            <span v-if="order.submitting" class="cro-spinner"></span>
            {{ order.submitting ? 'Creating…' : '+ Create Roll' }}
          </button>
        </div>
      </template>

      <!-- ══════════════════════ RESULT / PRINT ══════════════════════ -->
      <div class="card cro-result" v-if="result">
        <div class="cro-result__icon">✅</div>
        <div class="cro-result__title">Roll Created</div>
        <div class="cro-result__rollno">{{ result.name }}</div>
        <div class="cro-result__sub">
          {{ result.item_code || '—' }}<span v-if="result.commercial_name"> · {{ result.commercial_name }}</span>
        </div>
        <button class="btn btn-outline btn-full" style="margin-top:12px" @click="generatePrint">🖨 Generate Print</button>
        <button class="btn btn-ghost btn-full" style="margin-top:8px" @click="result = null">+ Create Another</button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'
import QRCode from 'qrcode'
import {
  getDoc,
  syncPurchaseOrders,
  syncSubcontractingOrders,
  getPOItems,
  getSOItems,
  getBatchesForItemCode,
  cutRoll,
  createPOSORoll,
  searchRollsForCut
} from '@/api/frappe'

const auth = useAuthStore()

// The Roll doctype's "Knitting Machine No" is a fixed Select field on ERP —
// mirrored here verbatim so the dropdown matches erp.pranera.in exactly.
const KNIT_MACHINES = [
  'CK01L','CK01R','CK02L','CK02R','CK03L','CK03R','CK04L','CK04R','CK05L','CK05R',
  'CK06L','CK06R','CK07L','CK07R','CK08L','CK08R','CK09L','CK09R','CK10L','CK10R',
  'CK11L','CK11R','CK12L','CK12R','CK13L','CK13R','CK14L','CK14R','CK15L','CK15R',
  'CK16L','CK16R','CK17L','CK17R','CK18L','CK18R','CK19L','CK19R','CK20L','CK20R',
  'CK21L','CK21R','CK22L','CK22R',
  'SJ01','SJ02','SJ03','SJ04','SJ05','SJ06','SJ07','SJ08','SJ09','SJ10','SJ11','SJ12','SJ13','SJ14',
  'IL01','IL02','IL03','IL04','Direct',
  'FK01/6014/PL/KH','FK02/6014/PL/KH','FK03/6014/PL/KH','FK04/6014/PL/KH','FK05/6014/PL/KH',
  'FK06/6014/PL/KH','FK07/6014/PL/KH','FK08/6014/PL/KH','FK09/8014/PL/KH','FK10/8014/PL/KH',
  'FK11/4014/SJ/KH','FK11A/4016/SJ/KH','FK12/4014/SJ/KH','FK12A/4016/SJ/KH','FK13/6014/SJ/KH',
  'FK14/6014/SJ/KH','FK15/6014/SJ/KH','FK16/6014/SJ/KH','FK17/6014/SJ/KH','FK18/6014/SJ/KH',
  'FK19/6014/SJ/KH','FK20/6014/SJ/KH','FK21/6014/SJ/KH','FK22/6014/SJ/KH',
  'IL01/3428/FK','IL02/3432/FK','IL03/3028/FK','IL04/3028/FK',
  'SJ01/2828/PL','SJ02/2624/TR','SJ03/2624/TR','SJ04/2828/FK','SJ05/2828/FK','SJ06/2828/FK',
  'SJ07/2828/UT','SJ08/3028/UT','SJ09/3224/UT','SJ10/3428/UT','SJ11/3432/JG','SJ12/3026/JG',
  'SJ13/3026/JG','SJ14/3428/FK','SJ15/3428/FK','SM01/MM10S-2.2','Sub Contracting'
]
const SHIFT_OPTIONS = ['1', '2']

const tab = ref('cut')
const result = ref(null)

function setTab(t) {
  tab.value = t
  result.value = null
  resetCutForm()
  resetOrderForm()
}

// ══════════════════════════ CUT ROLLS ══════════════════════════════════════
const cut = reactive({
  search: '', options: [], showDrop: false, searching: false,
  selected: null, qty: '', machineNo: '', shiftNo: '',
  submitting: false, error: ''
})

function resetCutForm() {
  cut.search = ''; cut.options = []; cut.showDrop = false; cut.searching = false
  cut.selected = null; cut.qty = ''; cut.machineNo = ''; cut.shiftNo = ''
  cut.submitting = false; cut.error = ''
}

let cutSearchTimer = null
function onCutRollSearch() {
  cut.showDrop = true
  clearTimeout(cutSearchTimer)
  const txt = cut.search.trim()
  if (!txt) { cut.options = []; return }
  cutSearchTimer = setTimeout(async () => {
    cut.searching = true
    try {
      cut.options = await searchRollsForCut(txt)
    } catch (e) {
      console.warn('Roll search failed:', e.message)
      cut.options = []
    } finally {
      cut.searching = false
    }
  }, 250)
}

function selectCutRoll(r) {
  cut.selected = r
  cut.search = r.name
  cut.showDrop = false
  cut.qty = ''
  cut.error = ''
}

const cutIsPcs = computed(() => (cut.selected?.stock_uom || '').trim().toLowerCase() === 'pcs')
const cutAvailable = computed(() => {
  if (!cut.selected) return 0
  return cutIsPcs.value ? Number(cut.selected.total_qty || 0) : Number(cut.selected.roll_weight || 0)
})
const cutRemainingPreview = computed(() => {
  const q = Number(cut.qty || 0)
  const remaining = Math.max(0, cutAvailable.value - q)
  return cutIsPcs.value ? Math.round(remaining) : remaining.toFixed(3)
})
const canSubmitCut = computed(() => {
  if (!cut.selected) return false
  const q = Number(cut.qty)
  return q > 0 && q <= cutAvailable.value
})

async function submitCut() {
  cut.error = ''
  const q = Number(cut.qty)
  if (!(q > 0)) { cut.error = 'Enter a qty greater than 0'; return }
  if (q > cutAvailable.value) {
    cut.error = `Qty exceeds available ${cutIsPcs.value ? 'qty' : 'weight'} of ${cutAvailable.value}`
    return
  }
  cut.submitting = true
  try {
    const resp = await cutRoll({
      source_roll: cut.selected.name,
      qty: q,
      knit_machine_no: cut.machineNo,
      knit_shift_no: cut.shiftNo
    })
    const roll = await getDoc('Roll', resp.name)
    result.value = roll
    resetCutForm()
  } catch (e) {
    cut.error = e.message || 'Failed to cut roll'
  } finally {
    cut.submitting = false
  }
}

// ══════════════════════ PURCHASE ORDER / SUBCONTRACT ORDER ═════════════════
const poOrders = ref([])
const soOrders = ref([])

const order = reactive({
  selected: '', items: [], itemCode: '', item: null,
  batch: '', actualWidth: '', rollWeight: '', rollQty: '', mistakeQty: '', okQty: '',
  submitting: false, error: ''
})
const batchOptions = ref([])

function resetOrderForm() {
  order.selected = ''; order.items = []; order.itemCode = ''; order.item = null
  order.batch = ''; order.actualWidth = ''; order.rollWeight = ''; order.rollQty = ''
  order.mistakeQty = ''; order.okQty = ''; order.submitting = false; order.error = ''
  batchOptions.value = []
}

const orderOptions = computed(() => {
  const list = tab.value === 'po' ? poOrders.value : soOrders.value
  return list.map(o => ({ label: o.supplier ? `${o.name} · ${o.supplier}` : o.name, value: o.name }))
})

const itemOptions = computed(() =>
  order.items.map(i => ({ label: i.item_name ? `${i.item_code} · ${i.item_name}` : i.item_code, value: i.item_code }))
)

async function onOrderChange(val) {
  order.itemCode = ''
  order.item = null
  order.items = []
  order.batch = ''
  batchOptions.value = []
  if (!val) return
  try {
    order.items = tab.value === 'po' ? await getPOItems(val) : await getSOItems(val)
  } catch (e) {
    order.error = e.message || 'Failed to load items for this order'
  }
}

async function onOrderItemChange(val) {
  order.item = order.items.find(i => i.item_code === val) || null
  order.batch = ''
  batchOptions.value = []
  if (!val) return
  try {
    const rows = await getBatchesForItemCode(val)
    batchOptions.value = rows.map(b => ({ label: b.batch_id || b.name, value: b.name }))
  } catch (e) {
    console.warn('Batch fetch failed:', e.message)
  }
}

// Ok Qty auto-fills from Roll Qty − Mistake Qty, but stays a plain editable
// field so the operator can override it afterwards (matches the legacy
// Ionic report's behaviour).
watch([() => order.rollQty, () => order.mistakeQty], ([qty, mistake]) => {
  if (qty === '' || qty === null) return
  order.okQty = Math.max(0, Number(qty || 0) - Number(mistake || 0))
})

const avgWeightPerPcs = computed(() => {
  const w = Number(order.rollWeight || 0)
  const q = Number(order.rollQty || 0)
  if (!w || !q) return ''
  return (w / q).toFixed(4)
})

async function submitOrder() {
  order.error = ''
  if (!order.selected) {
    order.error = `Select a ${tab.value === 'po' ? 'Purchase Order' : 'Subcontracting Order'} first`
    return
  }
  if (!order.itemCode) { order.error = 'Select an Item'; return }

  const rollWeight = Number(order.rollWeight || 0)
  const rollQty = Number(order.rollQty || 0)
  const isPcs = (order.item?.stock_uom || '').trim().toLowerCase() === 'pcs'

  if (isPcs && !(rollQty > 0)) { order.error = 'Enter Roll Qty'; return }
  if (!isPcs && !(rollWeight > 0)) { order.error = 'Enter Roll Weight'; return }

  order.submitting = true
  try {
    const payload = {
      purchase_order: tab.value === 'po' ? order.selected : '',
      subcontracting_order: tab.value === 'so' ? order.selected : '',
      item_code: order.itemCode,
      item_name: order.item?.item_name || '',
      commercial_name: order.item?.commercial_name || '',
      color: order.item?.color || '',
      width: order.item?.width || '',
      actual_width: order.actualWidth || '',
      project: order.item?.project || '',
      stock_uom: order.item?.stock_uom || '',
      batch: order.batch || '',
      roll_weight: rollWeight,
      total_qty: rollQty,
      mistake_qty: Number(order.mistakeQty || 0),
      ok_qty: Number(order.okQty || 0),
      avg_weight_per_pcs: Number(avgWeightPerPcs.value || 0)
    }
    const resp = await createPOSORoll(payload)
    const roll = await getDoc('Roll', resp.name)
    result.value = roll
    resetOrderForm()
  } catch (e) {
    order.error = e.message || 'Failed to create roll'
  } finally {
    order.submitting = false
  }
}

onMounted(async () => {
  try { poOrders.value = await syncPurchaseOrders() } catch (e) { console.warn('PO sync failed:', e.message) }
  try { soOrders.value = await syncSubcontractingOrders() } catch (e) { console.warn('SO sync failed:', e.message) }
})

// ══════════════════════ PRINT STICKER ══════════════════════════════════════
// Ported verbatim (same markup/print flow) from RollsPage.vue's printSticker()
// so a roll created here prints exactly like the "🖨 Print Sticker" button on
// /knit-app/rolls.
async function generatePrint() {
  const roll = result.value
  if (!roll) return
  const w = window.open('', '_blank')
  if (!w) { alert('Allow pop-ups to print.'); return }

  const weight = Number(roll.roll_weight ?? 0).toFixed(3)
  const totalQtyRaw = roll.total_qty
  const mistakeQtyRaw = roll.mistake_qty
  const totalQty = (totalQtyRaw !== null && totalQtyRaw !== undefined && Number(totalQtyRaw) > 0) ? Number(totalQtyRaw) : null
  const mistakeQty = (mistakeQtyRaw !== null && mistakeQtyRaw !== undefined && Number(mistakeQtyRaw) > 0) ? Number(mistakeQtyRaw) : null
  const qty = totalQty
  const refNo = roll.work_order || roll.purchase_order || roll.subcontracting_order || ''
  const qrData = `${roll.item_code}#${refNo}#${roll.name}`
  const batchRow = roll.batch ? `<tr><td>${roll.batch}</td></tr>` : ''
  const itemCode = roll.item_code || ''
  const itemFontSize = itemCode.length > 28 ? '6.5pt' : (itemCode.length > 20 ? '7.5pt' : '8.5pt')
  const weightLine = `${weight} kg${qty !== null ? ` · Qty: ${qty}` : ''}${mistakeQty !== null ? ` · Mistake: ${mistakeQty}` : ''}`
  const weightFontSize = weightLine.length > 26 ? '6.5pt' : (weightLine.length > 20 ? '7.5pt' : '8.5pt')
  let qrImg = ''
  try {
    qrImg = await QRCode.toDataURL(qrData, { width: 200, margin: 1 })
  } catch (e) { console.error('QR generation failed:', e) }
  const qrCell = qrImg ? `<img src="${qrImg}" style="width:24mm;height:24mm" alt="QR"/>` : ''

  w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Roll Sticker</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:100%; height:100%; }
  body { font-family:Arial,sans-serif; display:flex; flex-direction:column;
         align-items:center; justify-content:center; min-height:100vh; }
  .sticker { width:50mm; min-height:65mm; border:1px solid #000; display:flex;
             margin:2mm auto 0; flex-direction:column; flex-shrink:0; }
  .qr-cell { display:flex; align-items:center; justify-content:center; padding:2mm;
             border-bottom:1px solid #000; flex:0 0 auto; }
  table { width:calc(100% - 0.5cm); margin-left:0.5cm; border-collapse:collapse; flex:1; }
  td { padding:1.1mm 3mm; border-bottom:1px solid #000; font-size:8.5pt; font-weight:800;
       font-family:Arial,Helvetica,sans-serif; color:#000; line-height:1.15;
       text-rendering:optimizeLegibility; -webkit-font-smoothing:antialiased;
       word-break:break-word; white-space:normal; overflow-wrap:break-word; }
  td.item-code { font-size:${itemFontSize}; }
  td.weight-line { font-size:${weightFontSize}; white-space:nowrap; }
  tr:last-child td { border-bottom:none; padding-bottom:1.5mm; }
  .noprint { text-align:center; padding:10px; }
  .noprint button { padding:7px 18px; margin:0 4px; border-radius:5px; border:none;
    cursor:pointer; font-size:12px; font-weight:600; }
  .btn-p { background:#000; color:#fff; }
  .btn-c { background:#eee; color:#333; }
  @media print {
    .noprint { display:none; }
    html, body { width:100%; height:75mm; max-height:75mm; margin:0; padding:0; overflow:hidden; }
    body { display:block; }
    .sticker { margin:2mm auto 0; max-height:73mm; overflow:hidden; }
    @page { size:60mm 75mm; margin:0; }
  }
</style>
</head><body>
<div class="sticker">
  <div class="qr-cell">${qrCell}</div>
  <table>
    <tr><td class="item-code">${itemCode}</td></tr>
    <tr><td>${roll.commercial_name || ''}</td></tr>
    <tr><td>${refNo}</td></tr>
    <tr><td>${roll.name}</td></tr>
    <tr><td class="weight-line">${weightLine}</td></tr>
    ${batchRow}
  </table>
</div>
<div class="noprint">
  <button class="btn-p" onclick="window.print()">🖨 Print</button>
  <button class="btn-c" onclick="window.close()">Close</button>
</div>
</body></html>`)
  w.document.close()
}
</script>

<style scoped>
.cro-page    { min-height:100vh; background:var(--slate-50,#f1f5f9); }
.cro-content { padding:16px; max-width:800px; margin:0 auto; }

/* Tabs */
.cro-tabs { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:14px; }
.cro-tab {
  padding:12px 8px; border:2px solid var(--slate-200,#e2e8f0); border-radius:12px;
  background:white; cursor:pointer; font-family:inherit; font-size:12.5px; font-weight:700;
  color:var(--slate-700,#334155); transition:all 0.15s;
}
.cro-tab:hover { border-color:var(--app-primary,#0f6e56); }
.cro-tab--active {
  border-color:var(--app-primary,#0f6e56); background:rgba(15,110,86,0.08);
  color:var(--app-primary,#0f6e56);
}

.cro-card__title {
  font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em;
  color:var(--slate-400,#94a3b8); margin-bottom:12px;
}

.cro-field-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
@media (max-width:500px) { .cro-field-grid { grid-template-columns:1fr; } }

/* Autocomplete (Cut Rolls source-roll picker) */
.cro-autocomplete { position:relative; }
.cro-dropdown {
  position:absolute; top:calc(100% + 4px); left:0; right:0; background:white;
  border:1.5px solid var(--slate-200,#e2e8f0); border-radius:10px;
  box-shadow:var(--shadow-lg,0 10px 30px rgba(0,0,0,0.12));
  max-height:220px; overflow-y:auto; z-index:50;
}
.cro-dropdown__item { padding:10px 12px; cursor:pointer; font-size:13px; border-bottom:1px solid var(--slate-100,#f1f5f9); }
.cro-dropdown__item:hover { background:var(--slate-50,#f8fafc); }
.cro-dropdown__item:last-child { border-bottom:none; }
.cro-dropdown__name { font-weight:700; color:var(--slate-900,#0f172a); }
.cro-dropdown__sub  { font-size:11px; color:var(--slate-400,#94a3b8); margin-top:1px; }
.cro-dropdown__empty { padding:12px; font-size:13px; color:var(--slate-400,#94a3b8); text-align:center; }

/* Selected-roll detail card */
.cro-detail-card { border:1.5px solid var(--slate-200,#e2e8f0); border-radius:10px; overflow:hidden; margin-top:12px; }
.cro-detail-row { display:flex; justify-content:space-between; padding:8px 12px; border-bottom:1px solid var(--slate-100,#f1f5f9); font-size:13px; }
.cro-detail-row:last-child { border-bottom:none; }
.cro-detail-row span { color:var(--slate-500,#64748b); font-size:11px; }
.cro-detail-row strong { color:var(--slate-900,#0f172a); font-weight:700; }

.cro-hint { font-size:12px; color:var(--slate-500,#64748b); margin-top:6px; }

/* Result / print */
.cro-result { text-align:center; padding:24px 16px; }
.cro-result__icon { font-size:36px; margin-bottom:4px; }
.cro-result__title { font-size:15px; font-weight:800; color:var(--slate-900,#0f172a); }
.cro-result__rollno { font-size:20px; font-weight:900; color:var(--app-primary,#0f6e56); margin:6px 0 2px; }
.cro-result__sub { font-size:12px; color:var(--slate-400,#94a3b8); }

/* Spinner */
.cro-spinner {
  display:inline-block; width:14px; height:14px; border:2px solid rgba(255,255,255,0.35);
  border-top-color:white; border-radius:50%; animation:cro-spin 0.7s linear infinite;
}
@keyframes cro-spin { to { transform:rotate(360deg); } }
</style>
