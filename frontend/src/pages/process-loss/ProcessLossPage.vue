<template>
  <div class="pl-page">
    <AppHeader title="Process Loss" active="" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="pl-content">

      <!-- Work Order Selector -->
      <div class="pl-card">
        <div class="pl-card__title">Select Work Orders</div>

        <div class="pl-autocomplete">
          <input
            v-model="woSearch"
            class="pl-input"
            placeholder="Search Work Order…"
            @input="onWoInput"
            @focus="onWoInput"
            @blur="closeWoDropdown"
          />
          <div class="pl-dropdown" v-if="showWoDropdown && woOptions.length">
            <div
              v-for="o in woOptions" :key="o"
              class="pl-dropdown__item"
              :class="{ 'pl-dropdown__item--added': selectedWOs.includes(o) }"
              @mousedown.prevent="addWO(o)"
            >
              <span>{{ o }}</span>
              <span v-if="selectedWOs.includes(o)" class="pl-check">✓</span>
            </div>
          </div>
        </div>

        <div class="pl-chips" v-if="selectedWOs.length">
          <div class="pl-chip" v-for="wo in selectedWOs" :key="wo">
            <span>{{ wo }}</span>
            <button class="pl-chip__rm" @click="removeWO(wo)">✕</button>
          </div>
        </div>

        <div class="pl-actions">
          <button class="pl-btn pl-btn--primary" @click="runReport" :disabled="!selectedWOs.length || loading">
            <span v-if="loading" class="pl-spinner"></span>
            {{ loading ? 'Processing…' : '⚙ Calculate Process Loss' }}
          </button>
          <button class="pl-btn pl-btn--ghost" @click="clearAll" v-if="selectedWOs.length || hasResults">✕ Clear</button>
          <template v-if="hasResults">
            <button class="pl-btn pl-btn--excel" @click="downloadExcel">⬇ Excel</button>
            <button class="pl-btn pl-btn--pdf" @click="downloadPDF">⬇ PDF</button>
          </template>
        </div>

        <div class="pl-error" v-if="errorMsg">⚠ {{ errorMsg }}</div>
      </div>

      <!-- KPI cards -->
      <div class="pl-kpi-row" v-if="hasResults">
        <div class="pl-kpi">
          <div class="pl-kpi__num">{{ summaryRows.length }}</div>
          <div class="pl-kpi__lbl">Items</div>
        </div>
        <div class="pl-kpi">
          <div class="pl-kpi__num">{{ totalSent.toFixed(3) }}</div>
          <div class="pl-kpi__lbl">Total Sent</div>
        </div>
        <div class="pl-kpi">
          <div class="pl-kpi__num">{{ totalReturn.toFixed(3) }}</div>
          <div class="pl-kpi__lbl">Total Return</div>
        </div>
        <div class="pl-kpi">
          <div class="pl-kpi__num">{{ totalReceived.toFixed(3) }}</div>
          <div class="pl-kpi__lbl">Total Received</div>
        </div>
        <div class="pl-kpi pl-kpi--loss">
          <div class="pl-kpi__num">{{ totalLoss.toFixed(3) }}</div>
          <div class="pl-kpi__lbl">Process Loss</div>
        </div>
        <div class="pl-kpi" :class="avgLossPct > 5 ? 'pl-kpi--warn' : 'pl-kpi--ok'">
          <div class="pl-kpi__num">{{ avgLossPct.toFixed(2) }}%</div>
          <div class="pl-kpi__lbl">Avg Loss %</div>
        </div>
      </div>

      <!-- ① Summary -->
      <div class="pl-section" v-if="summaryRows.length">
        <div class="pl-section__hd">
          <span class="pl-section__icon">📊</span>
          <span>Process Loss Summary</span>
          <span class="pl-section__count">{{ summaryRows.length }} items</span>
        </div>
        <div class="pl-table-wrap">
          <table class="pl-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Work Order</th>
                <th>Item Code</th>
                <th>UOM</th>
                <th>WO Qty</th>
                <th>Sent Qty</th>
                <th>Return Qty</th>
                <th>Received Qty</th>
                <th>Loss Qty</th>
                <th>Loss %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in summaryRows" :key="i" :class="rowClass(r.process_loss_percentage)">
                <td class="pl-td-num">{{ i + 1 }}</td>
                <td class="pl-td-wo">{{ r.work_order }}</td>
                <td class="pl-td-item">{{ r.item_code }}</td>
                <td>{{ r.uom }}</td>
                <td class="pl-td-num">{{ fmt(r.wo_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.sent_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.return_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.received_qty) }}</td>
                <td class="pl-td-num pl-loss">{{ fmt(r.process_loss_qty) }}</td>
                <td class="pl-td-num">
                  <span class="pl-pct-badge" :class="pctClass(r.process_loss_percentage)">{{ fmt(r.process_loss_percentage) }}%</span>
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="pl-tfoot">
                <td colspan="5">Totals</td>
                <td class="pl-td-num">{{ totalSent.toFixed(3) }}</td>
                <td class="pl-td-num">{{ totalReturn.toFixed(3) }}</td>
                <td class="pl-td-num">{{ totalReceived.toFixed(3) }}</td>
                <td class="pl-td-num pl-loss">{{ totalLoss.toFixed(3) }}</td>
                <td class="pl-td-num"><span class="pl-pct-badge" :class="pctClass(avgLossPct)">{{ avgLossPct.toFixed(2) }}%</span></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- ② Sent Details -->
      <div class="pl-section" v-if="sentRows.length">
        <div class="pl-section__hd">
          <span class="pl-section__icon">📤</span>
          <span>Sent Details</span>
          <span class="pl-section__count">{{ sentRows.length }} entries</span>
        </div>
        <div class="pl-table-wrap">
          <table class="pl-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Work Order</th>
                <th>Stock Entry</th>
                <th>Item Code</th>
                <th>WO Item</th>
                <th>UOM</th>
                <th>WO Qty</th>
                <th>Sent Qty</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in sentRows" :key="i">
                <td class="pl-td-num">{{ i + 1 }}</td>
                <td class="pl-td-wo">{{ r.work_order }}</td>
                <td><a :href="`/app/stock-entry/${r.stock_entry}`" target="_blank" class="pl-link">{{ r.stock_entry }}</a></td>
                <td class="pl-td-item">{{ r.item_code }}</td>
                <td>{{ r.wo_item_code }}</td>
                <td>{{ r.uom }}</td>
                <td class="pl-td-num">{{ fmt(r.wo_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.sent_qty) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ③ Return Details -->
      <div class="pl-section" v-if="returnRows.length">
        <div class="pl-section__hd">
          <span class="pl-section__icon">↩</span>
          <span>Return Details</span>
          <span class="pl-section__count">{{ returnRows.length }} entries</span>
        </div>
        <div class="pl-table-wrap">
          <table class="pl-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Work Order</th>
                <th>Stock Entry</th>
                <th>Item Code</th>
                <th>WO Item</th>
                <th>UOM</th>
                <th>WO Qty</th>
                <th>Return Qty</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in returnRows" :key="i">
                <td class="pl-td-num">{{ i + 1 }}</td>
                <td class="pl-td-wo">{{ r.work_order }}</td>
                <td><a :href="`/app/stock-entry/${r.stock_entry}`" target="_blank" class="pl-link">{{ r.stock_entry }}</a></td>
                <td class="pl-td-item">{{ r.item_code }}</td>
                <td>{{ r.wo_item_code }}</td>
                <td>{{ r.uom }}</td>
                <td class="pl-td-num">{{ fmt(r.wo_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.return_qty) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ④ Received Details -->
      <div class="pl-section" v-if="receivedRows.length">
        <div class="pl-section__hd">
          <span class="pl-section__icon">📥</span>
          <span>Received Details</span>
          <span class="pl-section__count">{{ receivedRows.length }} entries</span>
        </div>
        <div class="pl-table-wrap">
          <table class="pl-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Work Order</th>
                <th>Stock Entry</th>
                <th>Item Code</th>
                <th>UOM</th>
                <th>WO Qty</th>
                <th>Received Qty</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in receivedRows" :key="i">
                <td class="pl-td-num">{{ i + 1 }}</td>
                <td class="pl-td-wo">{{ r.work_order }}</td>
                <td><a :href="`/app/stock-entry/${r.stock_entry}`" target="_blank" class="pl-link">{{ r.stock_entry }}</a></td>
                <td class="pl-td-item">{{ r.item_code }}</td>
                <td>{{ r.uom }}</td>
                <td class="pl-td-num">{{ fmt(r.wo_qty) }}</td>
                <td class="pl-td-num">{{ fmt(r.received_qty) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { call } from '@/api/frappe'

const auth = useAuthStore()

// ── State ─────────────────────────────────────────────────────────────────
const woSearch       = ref('')
const woOptions      = ref([])
const showWoDropdown = ref(false)
const selectedWOs    = ref([])
const loading        = ref(false)
const errorMsg       = ref('')

const sentRows     = ref([])
const returnRows   = ref([])
const receivedRows = ref([])
const summaryRows  = ref([])

const hasResults = computed(() =>
  summaryRows.value.length || sentRows.value.length || returnRows.value.length || receivedRows.value.length
)

// ── Totals ────────────────────────────────────────────────────────────────
const totalSent     = computed(() => summaryRows.value.reduce((s, r) => s + (r.sent_qty     || 0), 0))
const totalReturn   = computed(() => summaryRows.value.reduce((s, r) => s + (r.return_qty   || 0), 0))
const totalReceived = computed(() => summaryRows.value.reduce((s, r) => s + (r.received_qty || 0), 0))
const totalLoss     = computed(() => summaryRows.value.reduce((s, r) => s + (r.process_loss_qty || 0), 0))
const avgLossPct    = computed(() => {
  const net = totalSent.value - totalReturn.value
  return net > 0 ? (totalLoss.value / net) * 100 : 0
})

// ── WO autocomplete ───────────────────────────────────────────────────────
let woTimer = null
function onWoInput() {
  showWoDropdown.value = true
  clearTimeout(woTimer)
  woTimer = setTimeout(async () => {
    try {
      const resp = await call('knit_process_loss_wo_search', { search: woSearch.value || '' })
      woOptions.value = resp?.message || []
    } catch(e) { woOptions.value = [] }
  }, 300)
}
function closeWoDropdown() { setTimeout(() => { showWoDropdown.value = false }, 200) }
function addWO(wo) {
  if (!selectedWOs.value.includes(wo)) selectedWOs.value.push(wo)
  woSearch.value = ''; woOptions.value = []; showWoDropdown.value = false
}
function removeWO(wo) { selectedWOs.value = selectedWOs.value.filter(w => w !== wo) }

function clearAll() {
  selectedWOs.value = []; woSearch.value = ''; woOptions.value = []
  sentRows.value = []; returnRows.value = []; receivedRows.value = []; summaryRows.value = []
  errorMsg.value = ''
}

// ── Main calculation ──────────────────────────────────────────────────────
async function runReport() {
  if (!selectedWOs.value.length) return
  loading.value = true; errorMsg.value = ''
  try {
    const detailResp = await call('knit_process_loss_details', {
      work_orders: JSON.stringify(selectedWOs.value)
    })
    const details = detailResp?.message || {}
    sentRows.value     = details.sent     || []
    returnRows.value   = details.return   || []
    receivedRows.value = details.received || []

    const summaryResp = await call('knit_process_loss_summary', {
      work_orders:  JSON.stringify(selectedWOs.value),
      sent:         JSON.stringify(sentRows.value),
      return_rows:  JSON.stringify(returnRows.value),
      received:     JSON.stringify(receivedRows.value),
    })
    summaryRows.value = summaryResp?.message || []
  } catch(e) {
    errorMsg.value = e.message || 'Calculation failed.'
    console.error('Process loss error:', e)
  } finally {
    loading.value = false
  }
}

// ── Formatting ────────────────────────────────────────────────────────────
function fmt(v) { return v != null ? Number(v).toFixed(3) : '–' }
function pctClass(pct) {
  if (pct > 10) return 'pl-pct-badge--high'
  if (pct > 5)  return 'pl-pct-badge--mid'
  return 'pl-pct-badge--low'
}
function rowClass(pct) {
  if (pct > 10) return 'pl-row--high'
  if (pct > 5)  return 'pl-row--mid'
  return ''
}

// ── Excel download ────────────────────────────────────────────────────────
function downloadExcel() {
  const wos = selectedWOs.value.join(', ')
  const now = new Date().toLocaleDateString('en-IN')

  // Build CSV content for each section
  const lines = []

  lines.push('PRANERA SERVICES AND SOLUTIONS PVT. LTD.')
  lines.push('Process Loss Report')
  lines.push('Work Orders: ' + wos)
  lines.push('Date: ' + now)
  lines.push('')

  // Summary
  lines.push('PROCESS LOSS SUMMARY')
  lines.push('#,Work Order,Item Code,UOM,WO Qty,Sent Qty,Return Qty,Received Qty,Loss Qty,Loss %')
  summaryRows.value.forEach((r, i) => {
    lines.push([i+1, r.work_order, r.item_code, r.uom,
      fmt(r.wo_qty), fmt(r.sent_qty), fmt(r.return_qty),
      fmt(r.received_qty), fmt(r.process_loss_qty), fmt(r.process_loss_percentage)+'%'].join(','))
  })
  lines.push(['Totals','','','','',
    totalSent.value.toFixed(3), totalReturn.value.toFixed(3),
    totalReceived.value.toFixed(3), totalLoss.value.toFixed(3),
    avgLossPct.value.toFixed(2)+'%'].join(','))
  lines.push('')

  // Sent
  lines.push('SENT DETAILS')
  lines.push('#,Work Order,Stock Entry,Item Code,WO Item,UOM,WO Qty,Sent Qty')
  sentRows.value.forEach((r, i) => {
    lines.push([i+1, r.work_order, r.stock_entry, r.item_code,
      r.wo_item_code, r.uom, fmt(r.wo_qty), fmt(r.sent_qty)].join(','))
  })
  lines.push('')

  // Return
  lines.push('RETURN DETAILS')
  lines.push('#,Work Order,Stock Entry,Item Code,WO Item,UOM,WO Qty,Return Qty')
  returnRows.value.forEach((r, i) => {
    lines.push([i+1, r.work_order, r.stock_entry, r.item_code,
      r.wo_item_code, r.uom, fmt(r.wo_qty), fmt(r.return_qty)].join(','))
  })
  lines.push('')

  // Received
  lines.push('RECEIVED DETAILS')
  lines.push('#,Work Order,Stock Entry,Item Code,UOM,WO Qty,Received Qty')
  receivedRows.value.forEach((r, i) => {
    lines.push([i+1, r.work_order, r.stock_entry, r.item_code,
      r.uom, fmt(r.wo_qty), fmt(r.received_qty)].join(','))
  })

  const csv = lines.join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = 'process_loss_' + selectedWOs.value.join('_') + '.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// ── PDF download ──────────────────────────────────────────────────────────
function downloadPDF() {
  const wos = selectedWOs.value.join(', ')
  const now = new Date().toLocaleDateString('en-IN')

  const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Process Loss Report</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: Arial, sans-serif; font-size: 11px; color: #111; padding: 24px; }
  .hd  { text-align:center; margin-bottom:16px; }
  .hd h1 { font-size:15px; font-weight:800; }
  .hd h2 { font-size:12px; font-weight:600; color:#555; margin-top:2px; }
  .hd p  { font-size:10px; color:#777; margin-top:4px; }
  .kpi-row { display:flex; gap:10px; margin-bottom:16px; }
  .kpi { flex:1; border:1px solid #ddd; border-radius:6px; padding:8px 10px; text-align:center; }
  .kpi b { display:block; font-size:14px; }
  .kpi span { font-size:9px; color:#888; text-transform:uppercase; }
  .section { margin-bottom:20px; }
  .section-title { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;
    background:#f1f5f9; padding:6px 10px; border-left:3px solid #0f6e56; margin-bottom:6px; }
  table { width:100%; border-collapse:collapse; font-size:10px; }
  th { background:#0f6e56; color:white; padding:5px 7px; text-align:left; white-space:nowrap; }
  td { padding:4px 7px; border-bottom:1px solid #e5e7eb; }
  tr:nth-child(even) td { background:#f9fafb; }
  tfoot td { background:#f1f5f9; font-weight:700; border-top:2px solid #0f6e56; }
  .num { text-align:right; font-family:monospace; }
  .loss { color:#ea580c; font-weight:700; }
  @media print { body { padding:10px; } }
</style>
</head>
<body>
<div class="hd">
  <h1>PRANERA SERVICES AND SOLUTIONS PVT. LTD.</h1>
  <h2>Process Loss Report</h2>
  <p>Work Orders: ${wos} &nbsp;|&nbsp; Date: ${now}</p>
</div>

<div class="kpi-row">
  <div class="kpi"><b>${summaryRows.value.length}</b><span>Items</span></div>
  <div class="kpi"><b>${totalSent.value.toFixed(3)}</b><span>Total Sent</span></div>
  <div class="kpi"><b>${totalReturn.value.toFixed(3)}</b><span>Total Return</span></div>
  <div class="kpi"><b>${totalReceived.value.toFixed(3)}</b><span>Total Received</span></div>
  <div class="kpi"><b class="loss">${totalLoss.value.toFixed(3)}</b><span>Process Loss</span></div>
  <div class="kpi"><b>${avgLossPct.value.toFixed(2)}%</b><span>Avg Loss %</span></div>
</div>

<div class="section">
  <div class="section-title">📊 Process Loss Summary</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Item Code</th><th>UOM</th><th>WO Qty</th><th>Sent Qty</th><th>Return Qty</th><th>Received Qty</th><th>Loss Qty</th><th>Loss %</th></tr></thead>
    <tbody>
      ${summaryRows.value.map((r,i) => `<tr>
        <td class="num">${i+1}</td><td>${r.work_order}</td><td>${r.item_code}</td><td>${r.uom}</td>
        <td class="num">${fmt(r.wo_qty)}</td><td class="num">${fmt(r.sent_qty)}</td>
        <td class="num">${fmt(r.return_qty)}</td><td class="num">${fmt(r.received_qty)}</td>
        <td class="num loss">${fmt(r.process_loss_qty)}</td><td class="num">${fmt(r.process_loss_percentage)}%</td>
      </tr>`).join('')}
    </tbody>
    <tfoot><tr>
      <td colspan="5">Totals</td>
      <td class="num">${totalSent.value.toFixed(3)}</td>
      <td class="num">${totalReturn.value.toFixed(3)}</td>
      <td class="num">${totalReceived.value.toFixed(3)}</td>
      <td class="num loss">${totalLoss.value.toFixed(3)}</td>
      <td class="num">${avgLossPct.value.toFixed(2)}%</td>
    </tr></tfoot>
  </table>
</div>

<div class="section">
  <div class="section-title">📤 Sent Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>WO Item</th><th>UOM</th><th>WO Qty</th><th>Sent Qty</th></tr></thead>
    <tbody>
      ${sentRows.value.map((r,i) => `<tr>
        <td class="num">${i+1}</td><td>${r.work_order}</td><td>${r.stock_entry}</td><td>${r.item_code}</td>
        <td>${r.wo_item_code||''}</td><td>${r.uom}</td>
        <td class="num">${fmt(r.wo_qty)}</td><td class="num">${fmt(r.sent_qty)}</td>
      </tr>`).join('')}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">↩ Return Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>WO Item</th><th>UOM</th><th>WO Qty</th><th>Return Qty</th></tr></thead>
    <tbody>
      ${returnRows.value.map((r,i) => `<tr>
        <td class="num">${i+1}</td><td>${r.work_order}</td><td>${r.stock_entry}</td><td>${r.item_code}</td>
        <td>${r.wo_item_code||''}</td><td>${r.uom}</td>
        <td class="num">${fmt(r.wo_qty)}</td><td class="num">${fmt(r.return_qty)}</td>
      </tr>`).join('')}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">📥 Received Details</div>
  <table>
    <thead><tr><th>#</th><th>Work Order</th><th>Stock Entry</th><th>Item Code</th><th>UOM</th><th>WO Qty</th><th>Received Qty</th></tr></thead>
    <tbody>
      ${receivedRows.value.map((r,i) => `<tr>
        <td class="num">${i+1}</td><td>${r.work_order}</td><td>${r.stock_entry}</td><td>${r.item_code}</td>
        <td>${r.uom}</td><td class="num">${fmt(r.wo_qty)}</td><td class="num">${fmt(r.received_qty)}</td>
      </tr>`).join('')}
    </tbody>
  </table>
</div>

</body></html>`

  const win = window.open('', '_blank')
  win.document.write(html)
  win.document.close()
  setTimeout(() => { win.print() }, 500)
}
</script>

<style scoped>
.pl-page    { min-height:100vh; background:#f1f5f9; }
.pl-content { padding:16px; max-width:1200px; margin:0 auto; }

/* Card */
.pl-card { background:white; border-radius:14px; padding:18px 16px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }
.pl-card__title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#94a3b8; margin-bottom:12px; }

/* Autocomplete */
.pl-autocomplete { position:relative; }
.pl-input { width:100%; padding:10px 14px; border:1.5px solid #e2e8f0; border-radius:10px; font-size:14px; font-family:inherit; outline:none; box-sizing:border-box; transition:border 0.2s; }
.pl-input:focus { border-color:var(--app-primary,#0f6e56); }
.pl-dropdown { position:absolute; top:calc(100% + 4px); left:0; right:0; background:white; border:1.5px solid #e2e8f0; border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,0.12); max-height:220px; overflow-y:auto; z-index:50; }
.pl-dropdown__item { padding:10px 14px; font-size:14px; cursor:pointer; display:flex; align-items:center; justify-content:space-between; }
.pl-dropdown__item:hover { background:#f8fafc; }
.pl-dropdown__item--added { color:var(--app-primary,#0f6e56); font-weight:600; }
.pl-check { font-size:12px; color:var(--app-primary,#0f6e56); }

/* Chips */
.pl-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.pl-chip  { display:flex; align-items:center; gap:6px; background:rgba(15,110,86,0.08); color:var(--app-primary,#0f6e56); border-radius:20px; padding:5px 10px 5px 12px; font-size:13px; font-weight:600; }
.pl-chip__rm { background:none; border:none; cursor:pointer; color:var(--app-primary,#0f6e56); font-size:13px; padding:0; opacity:0.7; }
.pl-chip__rm:hover { opacity:1; }

/* Actions */
.pl-actions { display:flex; gap:10px; margin-top:14px; flex-wrap:wrap; }
.pl-btn { padding:11px 20px; border-radius:10px; border:none; font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; display:flex; align-items:center; gap:8px; transition:opacity 0.15s; }
.pl-btn:disabled { opacity:0.5; cursor:not-allowed; }
.pl-btn--primary { background:var(--app-primary,#0f6e56); color:white; }
.pl-btn--ghost   { background:#f8fafc; color:#64748b; border:1.5px solid #e2e8f0; }
.pl-btn--excel   { background:#166534; color:white; }
.pl-btn--pdf     { background:#991b1b; color:white; }
.pl-spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,0.4); border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.pl-error { margin-top:10px; padding:10px 14px; background:#fef2f2; color:#dc2626; border-radius:8px; font-size:13px; }

/* KPI */
.pl-kpi-row { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; margin-bottom:16px; }
@media(max-width:700px) { .pl-kpi-row { grid-template-columns:repeat(3,1fr); } }
.pl-kpi { background:white; border-radius:12px; padding:12px 10px; text-align:center; box-shadow:0 1px 4px rgba(0,0,0,0.07); }
.pl-kpi--loss { background:#fff7ed; }
.pl-kpi--warn { background:#fef2f2; }
.pl-kpi--ok   { background:#f0fdf4; }
.pl-kpi__num  { font-size:18px; font-weight:800; color:#0f172a; }
.pl-kpi--loss .pl-kpi__num { color:#ea580c; }
.pl-kpi--warn .pl-kpi__num { color:#dc2626; }
.pl-kpi--ok   .pl-kpi__num { color:#16a34a; }
.pl-kpi__lbl  { font-size:10px; color:#94a3b8; margin-top:2px; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; }

/* Section */
.pl-section { background:white; border-radius:14px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,0.08); overflow:hidden; }
.pl-section__hd { display:flex; align-items:center; gap:10px; padding:14px 16px; background:#f8fafc; border-bottom:1px solid #e2e8f0; font-size:14px; font-weight:700; color:#1e293b; }
.pl-section__icon { font-size:18px; }
.pl-section__count { margin-left:auto; font-size:11px; color:#94a3b8; font-weight:500; background:white; border:1px solid #e2e8f0; border-radius:20px; padding:2px 10px; }

/* Table */
.pl-table-wrap { overflow-x:auto; }
.pl-table { width:100%; border-collapse:collapse; font-size:12px; }
.pl-table th { background:#f8fafc; padding:9px 12px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#64748b; white-space:nowrap; border-bottom:2px solid #e2e8f0; }
.pl-table td { padding:8px 12px; border-bottom:1px solid #f1f5f9; color:#0f172a; }
.pl-table tbody tr:hover td { background:#f8fafc; }
.pl-td-num  { text-align:right; font-variant-numeric:tabular-nums; font-family:monospace; }
.pl-td-wo   { font-size:11px; font-weight:600; color:#475569; white-space:nowrap; }
.pl-td-item { font-weight:600; white-space:nowrap; }
.pl-loss    { color:#ea580c; font-weight:700; }
.pl-link    { color:var(--app-primary,#0f6e56); text-decoration:none; font-weight:600; font-size:11px; }
.pl-link:hover { text-decoration:underline; }
.pl-row--high td { background:#fff1f2; }
.pl-row--mid  td { background:#fffbeb; }
.pl-tfoot td  { background:#f8fafc; font-weight:700; border-top:2px solid #e2e8f0; }
.pl-pct-badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:700; }
.pl-pct-badge--low  { background:#dcfce7; color:#16a34a; }
.pl-pct-badge--mid  { background:#fef9c3; color:#a16207; }
.pl-pct-badge--high { background:#fee2e2; color:#dc2626; }
</style>
