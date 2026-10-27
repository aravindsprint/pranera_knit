<template>
  <div class="page">
    <AppHeader title="Stock" active="stock" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="page-content">
      <!-- ── Pick a warehouse: scan or select ── -->
      <div class="card">
        <button class="btn btn-primary btn-full btn-scan" @click="openScanner">
          <i class="pi pi-qrcode"></i> Scan QR Code
        </button>
        <div class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span>Scan a warehouse / bin label, or a roll sticker to jump to where that roll is.</span>
        </div>

        <div class="divider"><span>or select warehouse</span></div>

        <div class="wh-row">
          <AutoComplete
            v-model="warehouse" :options="warehouseOptions"
            placeholder="Search warehouse..." @update:modelValue="onWarehousePicked"
          />
          <button class="btn btn-outline" :disabled="!warehouse || loading" title="Refresh" @click="load">
            <i class="pi" :class="loading ? 'pi-spin pi-spinner' : 'pi-refresh'"></i>
          </button>
        </div>

        <div v-if="error" class="error-banner" style="margin-top:12px">
          <i class="pi pi-exclamation-triangle"></i> {{ error }}
        </div>
      </div>

      <!-- ── Results ── -->
      <div v-if="loadedFor" class="card card--table">
        <div class="table-head">
          <div>
            <div class="table-title">{{ loadedFor }}</div>
            <div class="muted small">
              {{ filtered.length.toLocaleString() }} of {{ rows.length.toLocaleString() }} rows
              · {{ rollCount.toLocaleString() }} rolls
            </div>
          </div>
          <button v-if="anyFilter" class="btn-link" @click="clearFilters">
            <i class="pi pi-filter-slash"></i> Clear filters
          </button>
        </div>

        <div class="totals">
          <span class="totals__label">Shown</span>
          <span v-for="(qty, uom) in filteredTotals" :key="uom" class="total-chip">
            {{ fmtQty(qty) }} <small>{{ uom || '—' }}</small>
          </span>
        </div>
        <div v-if="Object.keys(ledgerTotals).length" class="totals totals--ledger">
          <span class="totals__label">Ledger stock</span>
          <span v-for="(qty, uom) in ledgerTotals" :key="uom" class="total-chip total-chip--ledger">
            {{ fmtQty(qty) }} <small>{{ uom || '—' }}</small>
          </span>
          <span v-if="flaggedBatches" class="muted small">
            · {{ flaggedBatches }} batch{{ flaggedBatches > 1 ? 'es have' : ' has' }} more rolls recorded here than in stock
          </span>
        </div>

        <div class="table-wrap">
          <table class="stock-table">
            <thead>
              <tr>
                <th v-for="c in COLUMNS" :key="c.key" :class="{ num: c.num }" @click="toggleSort(c.key)">
                  <span class="th-label">
                    {{ c.label }}
                    <i v-if="sortKey === c.key" class="pi" :class="sortDir === 1 ? 'pi-sort-amount-up-alt' : 'pi-sort-amount-down'"></i>
                  </span>
                </th>
              </tr>
              <tr class="filter-row">
                <th v-for="c in COLUMNS" :key="c.key">
                  <select v-if="c.key === 'stock_uom'" v-model="filters.stock_uom" class="f-input">
                    <option value="">All</option>
                    <option v-for="u in uoms" :key="u" :value="u">{{ u || '—' }}</option>
                  </select>
                  <input
                    v-else v-model="filters[c.key]" class="f-input" :class="{ num: c.num }"
                    :placeholder="c.num ? '>10, <5, 1-20' : 'Filter'"
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(r, i) in visible" :key="r.roll_no || `${r.item_code}|${r.batch}|${i}`"
                :class="{ 'row--batch': !r.roll_no && r.batch, 'row--flag': r.over_rolled, 'row--hit': highlight && r.roll_no === highlight }"
              >
                <td class="mono code"><template v-for="(seg, j) in segs(r.item_code)" :key="j"><wbr v-if="j" />{{ seg }}</template></td>
                <td>{{ r.commercial_name }}</td>
                <td class="mono code"><template v-if="r.batch"><template v-for="(seg, j) in segs(r.batch)" :key="j"><wbr v-if="j" />{{ seg }}</template></template><template v-else>—</template></td>
                <td class="mono">
                  <template v-if="r.roll_no">{{ r.roll_no }}</template>
                  <span v-else-if="r.batch" class="tag" title="Ledger stock not matched to a roll recorded in this warehouse">no roll</span>
                  <template v-else>—</template>
                  <i v-if="r.over_rolled" class="pi pi-exclamation-circle flag-icon"
                     :title="`Rolls recorded here exceed ledger stock for this batch by ${fmtQty(r.over_rolled)}`"></i>
                </td>
                <td class="num strong">{{ fmtQty(r.qty) }}</td>
                <td>{{ r.stock_uom }}</td>
              </tr>
              <tr v-if="!filtered.length">
                <td :colspan="COLUMNS.length" class="empty">{{ rows.length ? 'No rows match these filters.' : 'No stock in this warehouse.' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <button v-if="filtered.length > limit" class="btn btn-outline btn-full" style="margin-top:12px" @click="limit += PAGE">
          Show more ({{ (filtered.length - limit).toLocaleString() }} left)
        </button>

        <div class="legend">
          <span><span class="swatch swatch--batch"></span> no roll — ledger stock with no roll recorded here</span>
          <span><i class="pi pi-exclamation-circle flag-icon"></i> rolls recorded here exceed ledger stock</span>
        </div>
      </div>

      <div v-else-if="!loading" class="empty empty--page">
        <i class="pi pi-box"></i>
        <span>Scan a QR code or select a warehouse to see its stock.</span>
      </div>
      <div v-else class="empty empty--page"><i class="pi pi-spin pi-spinner"></i> Loading stock...</div>
    </div>

    <!-- Camera scanner -->
    <transition name="modal-fade">
      <div v-if="showScanner" class="modal-overlay" @click.self="closeScanner">
        <div class="modal-box scanner-box">
          <h3 class="modal-title">Scan QR Code</h3>
          <div id="stock-scan-region" class="camera-region"></div>
          <div v-if="scannerError" class="error-banner" style="margin-top:12px">
            <i class="pi pi-exclamation-triangle"></i> {{ scannerError }}
          </div>
          <button class="btn btn-outline btn-full" style="margin-top:14px" @click="closeScanner">Cancel</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'
import { useAuthStore } from '@/stores/auth'
import { syncWarehouses, getWarehouseStock, resolveStockScan } from '@/api/frappe'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'

const COLUMNS = [
  { key: 'item_code', label: 'Item Code' },
  { key: 'commercial_name', label: 'Commercial Name' },
  { key: 'batch', label: 'Batch' },
  { key: 'roll_no', label: 'Roll No' },
  { key: 'qty', label: 'Qty', num: true },
  { key: 'stock_uom', label: 'UOM' },
]
const PAGE = 200

const auth = useAuthStore()

const warehouses = ref([])
const warehouse = ref('')
const loadedFor = ref('')
const rows = ref([])
const ledgerTotals = ref({})
const loading = ref(false)
const error = ref('')
const highlight = ref('')
const limit = ref(PAGE)

const filters = reactive({ item_code: '', commercial_name: '', batch: '', roll_no: '', qty: '', stock_uom: '' })
const sortKey = ref('')
const sortDir = ref(1)

const warehouseOptions = computed(() =>
  warehouses.value.map(w => ({ value: w.name, label: w.name }))
)

onMounted(async () => {
  try { warehouses.value = await syncWarehouses() } catch (e) { error.value = e.message }
})

function onWarehousePicked(val) {
  if (val && val !== loadedFor.value) {
    highlight.value = ''
    clearFilters()
    load()
  }
}

async function load() {
  if (!warehouse.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await getWarehouseStock(warehouse.value)
    rows.value = res.rows || []
    ledgerTotals.value = res.ledger_totals || {}
    loadedFor.value = res.warehouse
    limit.value = PAGE
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ── Filtering / sorting ───────────────────────────────────────────────────
function qtyMatches(qty, expr) {
  const e = expr.replace(/\s/g, '')
  if (!e) return true
  let m
  if ((m = e.match(/^(>=|<=|>|<|=)(-?\d*\.?\d+)$/))) {
    const n = Number(m[2])
    return { '>': qty > n, '<': qty < n, '>=': qty >= n, '<=': qty <= n, '=': Math.abs(qty - n) < 1e-6 }[m[1]]
  }
  if ((m = e.match(/^(-?\d*\.?\d+)-(-?\d*\.?\d+)$/))) return qty >= Number(m[1]) && qty <= Number(m[2])
  return String(qty).includes(e)
}

const filtered = computed(() => {
  const f = Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, String(v).trim().toLowerCase()]))
  let out = rows.value.filter(r =>
    (!f.item_code || (r.item_code || '').toLowerCase().includes(f.item_code)) &&
    (!f.commercial_name || (r.commercial_name || '').toLowerCase().includes(f.commercial_name)) &&
    (!f.batch || (r.batch || '').toLowerCase().includes(f.batch)) &&
    (!f.roll_no || (r.roll_no || '').toLowerCase().includes(f.roll_no)) &&
    (!filters.stock_uom || r.stock_uom === filters.stock_uom) &&
    qtyMatches(Number(r.qty) || 0, f.qty)
  )
  if (sortKey.value) {
    const k = sortKey.value, d = sortDir.value
    out = [...out].sort((a, b) => {
      const x = a[k], y = b[k]
      if (k === 'qty') return ((Number(x) || 0) - (Number(y) || 0)) * d
      return String(x || '').localeCompare(String(y || ''), undefined, { numeric: true }) * d
    })
  }
  return out
})
const visible = computed(() => filtered.value.slice(0, limit.value))
const rollCount = computed(() => filtered.value.filter(r => r.roll_no).length)
const uoms = computed(() => [...new Set(rows.value.map(r => r.stock_uom))].sort())
const filteredTotals = computed(() => {
  const t = {}
  for (const r of filtered.value) t[r.stock_uom] = (t[r.stock_uom] || 0) + (Number(r.qty) || 0)
  return t
})
const flaggedBatches = computed(() =>
  new Set(rows.value.filter(r => r.over_rolled).map(r => `${r.item_code}|${r.batch}`)).size
)
const anyFilter = computed(() => Object.values(filters).some(v => String(v).trim()))

watch(filters, () => { limit.value = PAGE })

function toggleSort(key) {
  if (sortKey.value !== key) { sortKey.value = key; sortDir.value = key === 'qty' ? -1 : 1 }
  else if (sortDir.value === (key === 'qty' ? -1 : 1)) sortDir.value = -sortDir.value
  else sortKey.value = ''
}
function clearFilters() {
  for (const k of Object.keys(filters)) filters[k] = ''
}

// ── QR scanning ───────────────────────────────────────────────────────────
const showScanner = ref(false)
const scannerError = ref('')
let qr = null

async function openScanner() {
  scannerError.value = ''
  showScanner.value = true
  await nextTick()
  try {
    qr = new Html5Qrcode('stock-scan-region')
    await qr.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
      onScan,
      () => {}
    )
  } catch (err) {
    scannerError.value = 'Could not access the camera: ' + (err?.message || err)
  }
}
async function stopScanner() {
  if (!qr) return
  try {
    if (qr.isScanning) await qr.stop()
    qr.clear()
  } catch (err) {
    console.warn('Failed to stop scanner:', err)
  }
  qr = null
}
async function closeScanner() {
  await stopScanner()
  showScanner.value = false
}

async function onScan(text) {
  await closeScanner()
  error.value = ''
  try {
    const res = await resolveStockScan(text)
    clearFilters()
    highlight.value = ''
    if (res.type === 'warehouse') {
      warehouse.value = res.warehouse
      await load()
      return
    }
    // Roll sticker / batch: open the roll's recorded warehouse when known,
    // otherwise filter the warehouse already on screen.
    if (res.warehouse && res.warehouse !== loadedFor.value) {
      warehouse.value = res.warehouse
      await load()
    }
    if (!loadedFor.value) {
      error.value = `${res.roll_no || res.batch} has no recorded warehouse — select one to search in.`
      return
    }
    if (res.roll_no && rows.value.some(r => r.roll_no === res.roll_no)) {
      filters.roll_no = res.roll_no
      highlight.value = res.roll_no
    } else if (res.batch) {
      filters.batch = res.batch
    }
  } catch (e) {
    error.value = e.message
  }
}

onBeforeUnmount(stopScanner)

// Split codes after each "/" and join with <wbr> so GKF11355/GREIGE/28OW
// wraps only at its separators (and copied text stays unchanged).
function segs(code) {
  return String(code || '').split(/(?<=\/)/)
}
function fmtQty(n) {
  return (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 3 })
}
</script>

<style scoped>
.page-content { padding: 16px; max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); min-width: 0; }
.card--table { padding: 14px; }
.muted { color: #64748b; }
.small { font-size: 12px; }

.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; padding: 0 14px; }
.btn-outline:disabled { border-color: #cbd5e1; color: #94a3b8; cursor: not-allowed; }
.btn-full { width: 100%; padding: 12px; }
.btn-scan { padding: 14px; font-size: 15px; font-weight: 600; }
.btn-link { background: none; border: none; color: #0f6e56; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }

.hint-text { font-size: 12px; color: #64748b; margin-top: 8px; display: flex; gap: 6px; align-items: flex-start; }
.hint-text i { margin-top: 1px; }
.divider { display: flex; align-items: center; gap: 10px; margin: 16px 0 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94a3b8; }
.divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: #e2e8f0; }
.wh-row { display: flex; gap: 8px; }
.wh-row > :first-child { flex: 1; min-width: 0; }

.table-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.table-title { font-weight: 700; font-size: 15px; color: #0f172a; overflow-wrap: anywhere; }
.totals { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 10px 0 12px; }
.total-chip { background: #f0fdf4; color: #166534; font-weight: 700; font-size: 13px; padding: 5px 10px; border-radius: 999px; }
.total-chip small { font-weight: 500; }
.totals--ledger { margin-top: -6px; }
.totals__label { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94a3b8; min-width: 86px; }
.total-chip--ledger { background: #f1f5f9; color: #334155; }

.table-wrap { overflow: auto; max-height: 70vh; border: 1px solid #f1f5f9; border-radius: 10px; }
.stock-table { width: 100%; min-width: 780px; border-collapse: collapse; font-size: 13px; }
.stock-table td.code { min-width: 150px; max-width: 240px; overflow-wrap: normal; word-break: keep-all; }
.stock-table td:nth-child(4) { white-space: nowrap; }
.stock-table td:nth-child(2) { min-width: 140px; }
.stock-table thead th { position: sticky; background: #f8fafc; z-index: 1; text-align: left; }
.stock-table thead tr:first-child th { top: 0; padding: 9px 10px 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; color: #64748b; cursor: pointer; user-select: none; white-space: nowrap; }
.stock-table thead tr.filter-row th { top: 30px; padding: 4px 6px 8px; border-bottom: 1px solid #e2e8f0; }
.th-label { display: inline-flex; gap: 4px; align-items: center; }
.th-label .pi { font-size: 11px; color: #0f6e56; }
.f-input { width: 100%; min-width: 80px; box-sizing: border-box; border: 1px solid #e2e8f0; border-radius: 6px; padding: 5px 7px; font-size: 12px; font-family: inherit; background: #fff; }
.f-input.num { text-align: right; min-width: 70px; }
.stock-table td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.stock-table tbody tr:hover td { background: #f8fafc; }
.num { text-align: right !important; white-space: nowrap; }
.strong { font-weight: 700; color: #0f172a; }
.mono { font-variant-numeric: tabular-nums; }
.row--batch td { background: #fffbeb; }
.row--hit td { background: #dcfce7 !important; }
.tag { font-size: 11px; font-weight: 600; color: #92400e; background: #fef3c7; border-radius: 999px; padding: 2px 8px; white-space: nowrap; }
.flag-icon { color: #b45309; margin-left: 4px; font-size: 12px; }

.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 10px; font-size: 11px; color: #64748b; }
.legend > span { display: inline-flex; align-items: center; gap: 6px; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.swatch--batch { background: #fef3c7; border: 1px solid #fde68a; }

.empty { text-align: center; color: #94a3b8; padding: 22px 10px; }
.empty--page { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 40px 16px; font-size: 14px; }
.empty--page .pi { font-size: 28px; }

.error-banner { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 20px; }
.modal-box { background: #fff; border-radius: 14px; padding: 22px; width: 100%; max-width: 380px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 12px; color: #0f172a; }
.camera-region { width: 100%; min-height: 260px; border-radius: 10px; overflow: hidden; background: #0f172a; }
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>
