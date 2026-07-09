<template>
  <div class="se-page">
    <AppHeader title="Stock Entry" active="" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="se-content">

      <!-- Purpose selector -->
      <div class="se-card">
        <div class="se-card__title">Stock Entry Type</div>
        <div class="se-purpose-btns">
          <button class="se-purpose-btn" :class="{ 'se-purpose-btn--active': purpose === 'Material Receipt' }"
            @click="setPurpose('Material Receipt')">
            <span class="se-purpose-icon">📥</span>
            <span>Material Receipt</span>
            <span class="se-purpose-sub">Incoming stock</span>
          </button>
          <button class="se-purpose-btn" :class="{ 'se-purpose-btn--active': purpose === 'Material Issue' }"
            @click="setPurpose('Material Issue')">
            <span class="se-purpose-icon">📤</span>
            <span>Material Issue</span>
            <span class="se-purpose-sub">Outgoing stock</span>
          </button>
        </div>
      </div>

      <!-- WO prefill banner -->
      <div class="se-prefill-banner" v-if="isWOPrefill">
        <span>📋</span>
        <span>Items pre-filled from Work Order required items. Enter physical qty and warehouse, then create draft.</span>
      </div>

      <!-- Header fields -->
      <div class="se-card" v-if="purpose">
        <div class="se-card__title">Header</div>
        <div class="se-field-grid">
          <div class="se-field">
            <label class="se-label">Posting Date *</label>
            <input class="se-input" v-model="form.posting_date" type="date" />
          </div>
          <div class="se-field">
            <label class="se-label">Remarks</label>
            <input class="se-input" v-model="form.remarks" placeholder="Optional" />
          </div>
        </div>
      </div>

      <!-- Items -->
      <div class="se-card" v-if="purpose">
        <div class="se-card__title" style="display:flex;justify-content:space-between;align-items:center">
          <span>Items</span>
          <button class="se-add-btn" @click="addRow" v-if="!isWOPrefill">+ Add Item</button>
        </div>

        <div v-for="(row, i) in rows" :key="i" class="se-row">
          <div class="se-row__hd">
            <span class="se-row__num">{{ i + 1 }}</span>
            <button class="se-row__del" @click="removeRow(i)" v-if="rows.length > 1">✕</button>
          </div>

          <div class="se-field-grid">
            <!-- Item Code -->
            <div class="se-field se-field--full">
              <label class="se-label">Item Code *</label>
              <div class="se-autocomplete">
                <input class="se-input" v-model="row.item_search" placeholder="Search item…"
                  :readonly="isWOPrefill"
                  :class="{ 'se-input--readonly': isWOPrefill }"
                  @input="!isWOPrefill && onItemSearch(i)" @focus="!isWOPrefill && onItemSearch(i)" @blur="closeItemDrop(i)" />
                <div class="se-dropdown" v-if="row.showDrop && row.itemOptions.length">
                  <div v-for="opt in row.itemOptions" :key="opt.name"
                    class="se-dropdown__item" @mousedown.prevent="selectItem(i, opt)">
                    <div class="se-dropdown__name">{{ opt.name }}</div>
                    <div class="se-dropdown__sub">{{ opt.item_name }}</div>
                  </div>
                </div>
              </div>
              <!-- WO qty reference -->
              <div v-if="row.required_qty !== null" class="se-wo-ref">
                <span>Required: <strong>{{ row.required_qty }}</strong></span>
                <span>Transferred: <strong>{{ row.transferred_qty }}</strong></span>
                <span>Consumed: <strong>{{ row.consumed_qty }}</strong></span>
              </div>
            </div>

            <!-- Qty -->
            <div class="se-field">
              <label class="se-label">Qty *</label>
              <input class="se-input" v-model="row.qty" type="number" step="0.001" min="0" placeholder="0.000" />
            </div>

            <!-- UOM -->
            <div class="se-field">
              <label class="se-label">UOM</label>
              <input class="se-input" v-model="row.uom" placeholder="Kgs" />
            </div>

            <!-- Warehouse -->
            <div class="se-field se-field--full">
              <label class="se-label">
                {{ purpose === 'Material Receipt' ? 'Target Warehouse *' : 'Source Warehouse *' }}
              </label>
              <div class="se-autocomplete">
                <input class="se-input" v-model="row.warehouse_search" placeholder="Search warehouse…"
                  @input="onWarehouseSearch(i)" @focus="onWarehouseSearch(i)" @blur="closeWarehouseDrop(i)" />
                <div class="se-dropdown" v-if="row.showWarehouseDrop && row.warehouseOptions.length">
                  <div v-for="wh in row.warehouseOptions" :key="wh.name"
                    class="se-dropdown__item" @mousedown.prevent="selectWarehouse(i, wh)">
                    {{ wh.name }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Batch -->
            <div class="se-field se-field--full">
              <label class="se-label">Batch No</label>
              <!-- WO prefill: show dropdown of MTM batches -->
              <select v-if="row.available_batches && row.available_batches.length"
                class="se-input" v-model="row.batch_no">
                <option value="">— Select batch —</option>
                <option v-for="b in row.available_batches" :key="b.batch_no" :value="b.batch_no">
                  {{ b.batch_no }} ({{ b.transferred_qty }} {{ row.uom }})
                </option>
              </select>
              <!-- Free search when no WO batches -->
              <div v-else class="se-autocomplete">
                <input class="se-input" v-model="row.batch_no" placeholder="Optional"
                  @input="onBatchSearch(i)" @focus="onBatchSearch(i)" @blur="closeBatchDrop(i)" />
                <div class="se-dropdown" v-if="row.showBatchDrop && row.batchOptions.length">
                  <div v-for="b in row.batchOptions" :key="b.name"
                    class="se-dropdown__item" @mousedown.prevent="selectBatch(i, b)">
                    <div class="se-dropdown__name">{{ b.name }}</div>
                    <div class="se-dropdown__sub" v-if="b.expiry_date">Exp: {{ b.expiry_date }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Cost Center -->
            <div class="se-field se-field--full">
              <label class="se-label">Cost Center</label>
              <input class="se-input" v-model="row.cost_center" placeholder="e.g. HO - PSS" />
            </div>
          </div>

          <div class="se-row__divider" v-if="i < rows.length - 1"></div>
        </div>
      </div>

      <!-- Totals -->
      <div class="se-totals" v-if="rows.length && purpose">
        <span>{{ rows.length }} item(s)</span>
        <span>Total Qty: {{ totalQty.toFixed(3) }}</span>
      </div>

      <!-- Actions -->
      <div class="se-actions" v-if="purpose">
        <button class="se-btn se-btn--ghost" @click="resetForm">✕ Clear</button>
        <button class="se-btn se-btn--primary" @click="createStockEntry" :disabled="submitting">
          <span v-if="submitting" class="se-spinner"></span>
          {{ submitting ? 'Creating…' : '💾 Create Draft' }}
        </button>
      </div>

      <div class="se-error" v-if="errorMsg">⚠ {{ errorMsg }}</div>

      <!-- Success -->
      <div class="se-success-card" v-if="createdName">
        <div class="se-success-icon">✓</div>
        <div class="se-success-title">Stock Entry Created</div>
        <div class="se-success-name">{{ createdName }}</div>
        <div class="se-success-sub">Draft — open in ERP to review and submit</div>
        <a :href="`https://erp.pranera.in/app/stock-entry/${createdName}`" target="_blank" class="se-btn se-btn--primary se-btn--full">
          Open in ERP →
        </a>
        <button class="se-btn se-btn--ghost se-btn--full" @click="resetForm" style="margin-top:8px">
          + Create Another
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { call, getList } from '@/api/frappe'

const auth  = useAuthStore()
const route = useRoute()

// Prefilled WO context (from CreateRollPage "Create Stock Entry" button)
const woContext    = ref(null)   // { items, wip_warehouse, source_warehouse }
const isWOPrefill  = ref(false)

const COMPANY = 'Pranera Services and Solutions Pvt. Ltd.,'

// ── State ─────────────────────────────────────────────────────────────────
const purpose    = ref('')
const submitting = ref(false)
const errorMsg   = ref('')
const createdName = ref('')

const form = ref({
  posting_date: new Date().toISOString().split('T')[0],
  remarks: '',
})

const defaultRow = () => ({
  item_code:        '',
  item_search:      '',
  item_name:        '',
  qty:              '',
  uom:              'Kgs',
  warehouse:        '',
  warehouse_search: '',
  batch_no:         '',
  cost_center:      'HO - PSS',
  required_qty:     null,
  available_batches: [],
  transferred_qty:  null,
  consumed_qty:     null,
  itemOptions:      [],
  warehouseOptions: [],
  batchOptions:     [],
  showDrop:         false,
  showWarehouseDrop: false,
  showBatchDrop:    false,
})

const rows = ref([defaultRow()])

const totalQty = computed(() => rows.value.reduce((s, r) => s + (parseFloat(r.qty) || 0), 0))

// ── Purpose ────────────────────────────────────────────────────────────────
function setPurpose(p) {
  purpose.value = p
  errorMsg.value = ''
  createdName.value = ''
}

// ── Rows ───────────────────────────────────────────────────────────────────
function addRow()      { rows.value.push(defaultRow()) }
function removeRow(i)  { rows.value.splice(i, 1) }

// ── Item search ────────────────────────────────────────────────────────────
const itemTimers = {}
function onItemSearch(i) {
  rows.value[i].showDrop = true
  clearTimeout(itemTimers[i])
  itemTimers[i] = setTimeout(async () => {
    const q = rows.value[i].item_search
    if (!q || q.length < 2) { rows.value[i].itemOptions = []; return }
    try {
      const res = await getList('Item', {
        filters: [['Item', 'name', 'like', `%${q}%`]],
        fields: ['name', 'item_name', 'stock_uom'],
        limit: 15,
      })
      rows.value[i].itemOptions = Array.isArray(res) ? res : (res?.data || [])
    } catch(e) { rows.value[i].itemOptions = [] }
  }, 300)
}
function closeItemDrop(i) { setTimeout(() => { rows.value[i].showDrop = false }, 200) }
function selectItem(i, opt) {
  const r = rows.value[i]
  r.item_code   = opt.name
  r.item_name   = opt.item_name
  r.item_search = opt.name
  r.uom         = opt.stock_uom || 'Kgs'
  r.showDrop    = false
  r.itemOptions = []
}

// ── Warehouse search ───────────────────────────────────────────────────────
const whTimers = {}
function onWarehouseSearch(i) {
  rows.value[i].showWarehouseDrop = true
  clearTimeout(whTimers[i])
  whTimers[i] = setTimeout(async () => {
    const q = rows.value[i].warehouse_search
    if (!q || q.length < 2) { rows.value[i].warehouseOptions = []; return }
    try {
      const res = await getList('Warehouse', {
        filters: [['Warehouse', 'name', 'like', `%${q}%`], ['Warehouse', 'is_group', '=', 0]],
        fields: ['name'],
        limit: 15,
      })
      rows.value[i].warehouseOptions = Array.isArray(res) ? res : (res?.data || [])
    } catch(e) { rows.value[i].warehouseOptions = [] }
  }, 300)
}
function closeWarehouseDrop(i) { setTimeout(() => { rows.value[i].showWarehouseDrop = false }, 200) }
function selectWarehouse(i, wh) {
  rows.value[i].warehouse        = wh.name
  rows.value[i].warehouse_search = wh.name
  rows.value[i].showWarehouseDrop = false
  rows.value[i].warehouseOptions  = []
}

// ── Batch search ───────────────────────────────────────────────────────────
const batchTimers = {}
function onBatchSearch(i) {
  rows.value[i].showBatchDrop = true
  clearTimeout(batchTimers[i])
  const item = rows.value[i].item_code
  const q    = rows.value[i].batch_no
  if (!q || q.length < 2) { rows.value[i].batchOptions = []; return }
  batchTimers[i] = setTimeout(async () => {
    try {
      const filters = [['Batch', 'name', 'like', `%${q}%`]]
      if (item) filters.push(['Batch', 'item', '=', item])
      const res = await getList('Batch', {
        filters,
        fields: ['name', 'expiry_date'],
        limit: 15,
      })
      rows.value[i].batchOptions = Array.isArray(res) ? res : (res?.data || [])
    } catch(e) { rows.value[i].batchOptions = [] }
  }, 300)
}
function closeBatchDrop(i) { setTimeout(() => { rows.value[i].showBatchDrop = false }, 200) }
function selectBatch(i, b) {
  rows.value[i].batch_no      = b.name
  rows.value[i].showBatchDrop = false
  rows.value[i].batchOptions  = []
}

// ── Validation ─────────────────────────────────────────────────────────────
function validate() {
  if (!form.value.posting_date) return 'Posting Date is required'
  for (let i = 0; i < rows.value.length; i++) {
    const r = rows.value[i]
    const n = i + 1
    if (!r.item_code)  return `Row ${n}: Item Code is required`
    if (!r.qty || parseFloat(r.qty) <= 0) return `Row ${n}: Qty must be greater than 0`
    if (!r.warehouse)  return `Row ${n}: Warehouse is required`
  }
  return null
}

// ── Create Draft ───────────────────────────────────────────────────────────
async function createStockEntry() {
  errorMsg.value   = ''
  const err = validate()
  if (err) { errorMsg.value = err; return }

  submitting.value = true
  try {
    const items = rows.value.map(r => ({
      item_code:               r.item_code,
      qty:                     parseFloat(r.qty),
      transfer_qty:            parseFloat(r.qty),
      uom:                     r.uom || 'Kgs',
      stock_uom:               r.uom || 'Kgs',
      conversion_factor:       1.0,
      s_warehouse:             purpose.value === 'Material Issue'    ? r.warehouse : null,
      t_warehouse:             purpose.value === 'Material Receipt'  ? r.warehouse : null,
      batch_no:                r.batch_no || null,
      cost_center:             r.cost_center || 'HO - PSS',
      allow_zero_valuation_rate: 1,
      use_serial_batch_fields: 1,
    }))

    const payload = {
      purpose:          purpose.value,
      stock_entry_type: purpose.value,
      company:          COMPANY,
      posting_date:     form.value.posting_date,
      posting_time:     new Date().toLocaleTimeString('en-GB'),
      remarks:          form.value.remarks || null,
      items_json:       JSON.stringify(items),
    }

    const resp = await call('knit_create_stock_entry_draft', payload)
    createdName.value = resp?.message?.name
    if (!createdName.value) throw new Error('No name returned from server')
  } catch(e) {
    errorMsg.value = e.message || 'Failed to create Stock Entry'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const wo = route.query.work_order
  if (wo) {
    try {
      isWOPrefill.value = true
      purpose.value     = 'Material Issue'
      const resp = await call('knit_get_wo_required_items', { work_order: wo })
      const data = resp?.message || {}
      woContext.value   = data

      if (data.items && data.items.length) {
        const newRows = []
        data.items.forEach(item => {
          const batches = item.batches && item.batches.length
            ? item.batches
            : [{ batch_no: '', transferred_qty: null, wip_warehouse: data.wip_warehouse || '', s_warehouse: data.source_warehouse || '' }]
          batches.forEach(b => {
            newRows.push({
              ...defaultRow(),
              item_code:         item.item_code,
              item_search:       item.item_code,
              item_name:         item.item_name || '',
              qty:               '',
              uom:               item.stock_uom || 'Kgs',
              warehouse:         b.wip_warehouse || b.s_warehouse || data.source_warehouse || '',
              warehouse_search:  b.wip_warehouse || b.s_warehouse || data.source_warehouse || '',
              batch_no:          b.batch_no || '',
              available_batches: item.batches
                ? item.batches.map(x => ({ batch_no: x.batch_no, transferred_qty: x.transferred_qty }))
                : [],
              required_qty:      item.required_qty,
              transferred_qty:   item.transferred_qty,
              consumed_qty:      item.consumed_qty,
            })
          })
        })
        rows.value = newRows
      }
    } catch(e) { console.warn('WO prefill fetch error', e) }
  }
})

function resetForm() {
  purpose.value      = ''
  createdName.value  = ''
  errorMsg.value     = ''
  rows.value         = [defaultRow()]
  form.value.remarks = ''
  form.value.posting_date = new Date().toISOString().split('T')[0]
}
</script>

<style scoped>
.se-page    { min-height:100vh; background:#f1f5f9; }
.se-content { padding:16px; max-width:800px; margin:0 auto; }

/* Card */
.se-card { background:white; border-radius:14px; padding:16px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.se-card__title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:#94a3b8; margin-bottom:12px; }

/* Purpose buttons */
.se-purpose-btns { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.se-purpose-btn  { display:flex; flex-direction:column; align-items:center; gap:4px; padding:16px 12px;
  border:2px solid #e2e8f0; border-radius:12px; background:white; cursor:pointer; font-family:inherit; transition:all 0.15s; }
.se-purpose-btn:hover { border-color:var(--app-primary,#0f6e56); background:#f0fdf4; }
.se-purpose-btn--active { border-color:var(--app-primary,#0f6e56); background:rgba(15,110,86,0.06); }
.se-purpose-btn--active span:nth-child(2) { color:var(--app-primary,#0f6e56); font-weight:700; }
.se-purpose-icon { font-size:24px; }
.se-purpose-btn span:nth-child(2) { font-size:14px; font-weight:600; color:#0f172a; }
.se-purpose-sub  { font-size:11px; color:#94a3b8; }

/* Field grid */
.se-field-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.se-field--full { grid-column:1/-1; }
@media(max-width:500px) { .se-field-grid { grid-template-columns:1fr; } .se-field--full { grid-column:1; } }
.se-field  { display:flex; flex-direction:column; gap:4px; }
.se-label  { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#94a3b8; }
.se-input  { padding:9px 12px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:13px;
  font-family:inherit; outline:none; background:white; width:100%; box-sizing:border-box; }
.se-input:focus { border-color:var(--app-primary,#0f6e56); }

/* Autocomplete */
.se-autocomplete { position:relative; }
.se-dropdown { position:absolute; top:calc(100% + 4px); left:0; right:0; background:white;
  border:1.5px solid #e2e8f0; border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,0.12);
  max-height:200px; overflow-y:auto; z-index:50; }
.se-dropdown__item { padding:9px 12px; cursor:pointer; font-size:13px; border-bottom:1px solid #f1f5f9; }
.se-dropdown__item:hover { background:#f8fafc; }
.se-dropdown__item:last-child { border-bottom:none; }
.se-dropdown__name { font-weight:600; color:#0f172a; }
.se-dropdown__sub  { font-size:11px; color:#94a3b8; margin-top:1px; }

/* Row */
.se-row__hd  { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
.se-row__num { font-size:12px; font-weight:700; color:#94a3b8; background:#f1f5f9; border-radius:50%;
  width:22px; height:22px; display:flex; align-items:center; justify-content:center; }
.se-row__del { background:#fee2e2; border:none; color:#dc2626; border-radius:6px; width:24px; height:24px;
  cursor:pointer; font-size:11px; display:flex; align-items:center; justify-content:center; }
.se-row__divider { height:1px; background:#f1f5f9; margin:14px 0; }

/* Add item */
.se-add-btn { background:rgba(15,110,86,0.08); color:var(--app-primary,#0f6e56); border:none;
  border-radius:8px; padding:6px 12px; font-size:12px; font-weight:700; cursor:pointer; font-family:inherit; }
.se-add-btn:hover { background:rgba(15,110,86,0.15); }

/* Totals */
.se-totals { display:flex; justify-content:space-between; font-size:13px; color:#64748b;
  font-weight:600; padding:8px 4px; margin-bottom:6px; }

/* Actions */
.se-actions { display:flex; gap:10px; margin-bottom:14px; }
.se-btn { padding:11px 20px; border-radius:10px; border:none; font-size:14px; font-weight:600;
  cursor:pointer; font-family:inherit; display:flex; align-items:center; gap:8px; transition:opacity 0.15s; text-decoration:none; justify-content:center; }
.se-btn:disabled { opacity:0.5; cursor:not-allowed; }
.se-btn--primary { background:var(--app-primary,#0f6e56); color:white; flex:1; }
.se-btn--ghost   { background:#f8fafc; color:#64748b; border:1.5px solid #e2e8f0; }
.se-btn--full    { width:100%; }

/* Spinner */
.se-spinner { display:inline-block; width:14px; height:14px; border:2px solid rgba(255,255,255,0.35);
  border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

/* Messages */
.se-error { background:#fef2f2; color:#dc2626; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:10px; }

/* Success */
.se-success-card { background:white; border-radius:14px; padding:24px 16px; text-align:center;
  box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.se-success-icon  { font-size:36px; color:#16a34a; margin-bottom:8px; }
.se-success-title { font-size:16px; font-weight:800; color:#0f172a; }
.se-success-name  { font-size:18px; font-weight:900; color:var(--app-primary,#0f6e56); margin:6px 0; }
.se-success-sub   { font-size:12px; color:#94a3b8; margin-bottom:16px; }
.se-wo-ref { display:flex; gap:12px; margin-top:6px; font-size:11px; color:#64748b; flex-wrap:wrap; }
.se-wo-ref strong { color:#0f172a; }
.se-input--readonly { background:#f8fafc; color:#64748b; cursor:default; }
.se-prefill-banner { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:10px 14px;
  font-size:13px; color:#15803d; display:flex; gap:8px; align-items:flex-start; margin-bottom:0; }
</style>
