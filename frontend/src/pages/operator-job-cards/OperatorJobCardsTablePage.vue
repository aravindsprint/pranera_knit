<template>
  <div class="tv-page">
    <AppHeader title="Operator Job Cards · Table" active="operator-job-cards" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="tv-content">

      <!-- View + export -->
      <div class="tv-toolbar">
        <div class="tv-seg">
          <button v-for="v in views" :key="v.key" class="tv-seg__btn" :class="{ 'tv-seg__btn--on': view === v.key }" @click="view = v.key">{{ v.label }}</button>
        </div>
        <div class="tv-spacer"></div>
        <router-link to="/knit-app/operator-job-cards" class="tv-btn tv-btn--ghost">▦ Card view</router-link>
        <button class="tv-btn tv-btn--xls" :disabled="busy || !rows.length" @click="toExcel">⬇ Excel</button>
        <button class="tv-btn tv-btn--pdf" :disabled="busy || !rows.length" @click="toPdf">⬇ PDF</button>
        <button class="tv-refresh" :disabled="loading" @click="load" title="Refresh">
          <span v-if="loading" class="tv-spinner"></span><span v-else>↻</span>
        </button>
      </div>

      <!-- Period -->
      <div class="tv-toolbar">
        <div class="tv-chips">
          <button v-for="p in presets" :key="p.key" class="tv-chip" :class="{ 'tv-chip--on': preset === p.key }" @click="setPreset(p.key)">{{ p.label }}</button>
        </div>
        <div class="tv-dates" v-if="preset === 'custom'">
          <input type="date" v-model="fromDate" class="tv-date" :max="toDate" />
          <span>→</span>
          <input type="date" v-model="toDate" class="tv-date" :min="fromDate" />
          <button class="tv-go" @click="load">Go</button>
        </div>
      </div>

      <!-- Filters -->
      <div class="tv-toolbar">
        <input v-model="search" class="tv-search" placeholder="Search operator, job card, work order, machine or item…" />
        <select v-if="view === 'jc'" v-model="bucketFilter" class="tv-select">
          <option value="all">All job cards ({{ jcRows.length }})</option>
          <option v-for="b in bucketOptions" :key="b.key" :value="b.key">{{ b.label }} ({{ b.count }})</option>
        </select>
        <select v-model="uomFilter" class="tv-select">
          <option value="All">All UOMs</option>
          <option v-for="u in uomOptions" :key="u" :value="u">{{ u }}</option>
        </select>
      </div>
      <div class="tv-info">
        {{ rows.length }} {{ view === 'jc' ? 'rows' : 'operators' }} · Finished = last roll ended {{ periodLabel }}
        <span v-if="view === 'jc'"> · a job card shared by two operators appears once per operator</span>
      </div>

      <div v-if="errorMsg" class="tv-err">⚠ {{ errorMsg }}</div>
      <div v-else-if="loading && !operators.length && !unassigned.length" class="tv-loading"><span class="tv-spinner"></span> Loading…</div>

      <DataTable
        v-else
        ref="table"
        :columns="columns"
        :rows="rows"
        :row-key="r => r._key"
        :row-class="r => (r.stale ? 'tv-row--stale' : null)"
        :totals="view === 'summary' || singleUom"
        empty-text="No job cards found."
      >
        <template #cell-bucket_label="{ row, value }">
          <span class="tv-badge" :class="`tv-badge--${row.bucket}`">{{ value }}</span>
        </template>
        <template #cell-progress_pct="{ row, value }">
          <span v-if="row.status !== 'Open'" class="tv-pct">
            <span class="tv-pct__bar"><span :style="{ width: Math.min(value || 0, 100) + '%' }"></span></span>{{ Number(value || 0).toFixed(1) }}%
          </span>
        </template>
        <template #cell-stale="{ value }">
          <span v-if="value" class="tv-stale">⚠ {{ value }}</span>
        </template>
      </DataTable>
      <div v-if="view === 'jc' && !singleUom && rows.length" class="tv-note">Totals are hidden because the rows mix Kgs and Pcs. Pick a UOM to see totals.</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import DataTable from '@/components/DataTable.vue'
import { getOperatorJobCards } from '@/api/frappe'
import { exportExcel, exportPdf, formatCell, stamp } from '@/utils/tableExport'

const REFRESH_MS = 2 * 60 * 1000
const BUCKETS = { current: 'Current', upcoming: 'Upcoming', finished: 'Finished', unassigned: 'No operator' }

const auth = useAuthStore()
const operators = ref([])
const unassigned = ref([])
const staleHours = ref(24)
const loading = ref(false)
const busy = ref(false)
const errorMsg = ref('')
const search = ref('')
const bucketFilter = ref('all')
const uomFilter = ref('All')
const view = ref('jc')
const table = ref(null)
let timer = null

const views = [
  { key: 'jc', label: 'Job Cards' },
  { key: 'summary', label: 'Operator Summary' },
]

// ── Period (same presets as the card page) ──
const presets = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: 'custom', label: 'Custom' },
]
const preset = ref('today')
const fromDate = ref(isoDay(0))
const toDate = ref(isoDay(0))

function isoDay(offset) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function setPreset(key) {
  preset.value = key
  if (key === 'today') { fromDate.value = isoDay(0); toDate.value = isoDay(0) }
  if (key === 'yesterday') { fromDate.value = isoDay(-1); toDate.value = isoDay(-1) }
  if (key === '7d') { fromDate.value = isoDay(-6); toDate.value = isoDay(0) }
  if (key === '30d') { fromDate.value = isoDay(-29); toDate.value = isoDay(0) }
  if (key !== 'custom') load()
}
const fmtD = v => formatCell({ type: 'date' }, v)
const periodLabel = computed(() =>
  fromDate.value === toDate.value ? `on ${fmtD(fromDate.value)}` : `${fmtD(fromDate.value)} – ${fmtD(toDate.value)}`)

// ── Columns ──
const JC_COLUMNS = [
  { key: 'employee_name', label: 'Operator', type: 'text', width: 22 },
  { key: 'employee', label: 'Employee ID', type: 'text', width: 14, pdf: false },
  { key: 'designation', label: 'Designation', type: 'text', width: 16, pdf: false },
  { key: 'bucket_label', label: 'Bucket', type: 'text', width: 12 },
  { key: 'job_card', label: 'Job Card', type: 'text', width: 18 },
  { key: 'status', label: 'JC Status', type: 'text', width: 16 },
  { key: 'machine', label: 'Machine', type: 'text', width: 10 },
  { key: 'work_order', label: 'Work Order', type: 'text', width: 20 },
  { key: 'item_code', label: 'Item Code', type: 'text', width: 22, pdf: false },
  { key: 'item_name', label: 'Item Name', type: 'text', width: 32 },
  { key: 'uom', label: 'UOM', type: 'text', width: 7 },
  { key: 'for_quantity', label: 'JC Qty', type: 'num', total: true },
  { key: 'produced', label: 'Produced', type: 'num', total: true },
  { key: 'progress_pct', label: 'Progress', type: 'pct' },
  { key: 'rolls', label: 'Rolls', type: 'int', total: true },
  { key: 'planned_start_date', label: 'Planned Start', type: 'date' },
  { key: 'start_time', label: 'First Roll Start', type: 'datetime' },
  { key: 'end_time', label: 'Last Roll End', type: 'datetime' },
  { key: 'finished_at', label: 'Finished At', type: 'datetime' },
  { key: 'stale', label: 'Alert', type: 'text', width: 24 },
]

const SUMMARY_COLUMNS = [
  { key: 'employee_name', label: 'Operator', type: 'text', width: 24 },
  { key: 'employee', label: 'Employee ID', type: 'text', width: 14 },
  { key: 'designation', label: 'Designation', type: 'text', width: 18 },
  { key: 'state', label: 'Now', type: 'text', width: 12 },
  { key: 'current', label: 'Current JC', type: 'int', total: true },
  { key: 'upcoming', label: 'Upcoming JC', type: 'int', total: true },
  { key: 'finished', label: 'Finished JC', type: 'int', total: true },
  { key: 'finished_kgs', label: 'Finished Kgs', type: 'num', total: true },
  { key: 'finished_pcs', label: 'Finished Pcs', type: 'int', total: true },
  { key: 'finished_rolls', label: 'Finished Rolls', type: 'int', total: true },
  { key: 'machines', label: 'Current Machines', type: 'text', width: 22 },
  { key: 'stale_count', label: 'Stale JC', type: 'int', total: true },
]

const columns = computed(() => (view.value === 'jc' ? JC_COLUMNS : SUMMARY_COLUMNS))

// ── Rows ──
const shortMachine = ws => (ws || '').split('/')[0]
const isPcs = u => /^(nos|pcs)/i.test(u || '')

function jcRow(op, jc, bucket) {
  return {
    _key: `${op?.employee || '-'}|${jc.job_card}|${bucket}`,
    employee: op?.employee || '',
    employee_name: op ? (op.employee_name || op.employee) : '— not assigned —',
    designation: op?.designation || '',
    bucket,
    bucket_label: BUCKETS[bucket],
    ...jc,
    machine: shortMachine(jc.workstation),
    stale: jc.stale ? `No rolls for ${staleHours.value}+ h` : '',
    _search: [op?.employee, op?.employee_name, jc.job_card, jc.work_order, jc.workstation, jc.item_code, jc.item_name]
      .join(' ').toLowerCase(),
  }
}

const jcRows = computed(() => {
  const out = []
  for (const op of operators.value) {
    for (const b of ['current', 'upcoming', 'finished']) for (const jc of op[b]) out.push(jcRow(op, jc, b))
  }
  for (const jc of unassigned.value) out.push(jcRow(null, jc, 'unassigned'))
  return out
})

const summaryRows = computed(() => operators.value.map(op => {
  const fin = op.finished_totals || []
  const sum = (pred, k) => fin.filter(t => pred(t.uom)).reduce((s, t) => s + (Number(t[k]) || 0), 0)
  const all = [...op.current, ...op.upcoming, ...op.finished]
  return {
    _key: op.employee,
    employee: op.employee,
    employee_name: op.employee_name || op.employee,
    designation: op.designation || '',
    state: op.current.some(j => !j.stale) ? 'Working' : op.current.length ? 'Check' : 'Not running',
    current: op.current.length,
    upcoming: op.upcoming.length,
    finished: op.finished.length,
    finished_kgs: sum(u => !isPcs(u), 'qty'),
    finished_pcs: sum(isPcs, 'qty'),
    finished_rolls: sum(() => true, 'rolls'),
    machines: [...new Set(op.current.map(j => shortMachine(j.workstation)))].join(', '),
    stale_count: op.current.filter(j => j.stale).length,
    _uoms: all.map(j => j.uom),
    _search: [op.employee, op.employee_name, ...all.flatMap(j => [j.job_card, j.work_order, j.workstation, j.item_code, j.item_name])]
      .join(' ').toLowerCase(),
  }
}))

function filterJc(list) {
  const q = search.value.trim().toLowerCase()
  return list.filter(r => {
    if (bucketFilter.value !== 'all' && r.bucket !== bucketFilter.value) return false
    if (uomFilter.value !== 'All' && r.uom !== uomFilter.value) return false
    return !q || r._search.includes(q)
  })
}
function filterSummary(list) {
  const q = search.value.trim().toLowerCase()
  return list.filter(r => {
    if (uomFilter.value !== 'All' && !r._uoms.includes(uomFilter.value)) return false
    return !q || r._search.includes(q)
  })
}

const rows = computed(() => (view.value === 'jc' ? filterJc(jcRows.value) : filterSummary(summaryRows.value)))
const singleUom = computed(() => new Set(rows.value.map(r => r.uom).filter(Boolean)).size <= 1)

const bucketOptions = computed(() => Object.entries(BUCKETS).map(([key, label]) => ({
  key, label, count: jcRows.value.filter(r => r.bucket === key).length,
})))
const uomOptions = computed(() => [...new Set(jcRows.value.map(r => r.uom).filter(Boolean))].sort())

// ── Export ──
function filterText() {
  const parts = [`Period ${periodLabel.value.replace(/^on /, '')}`]
  if (view.value === 'jc' && bucketFilter.value !== 'all') parts.push(BUCKETS[bucketFilter.value])
  if (uomFilter.value !== 'All') parts.push(uomFilter.value)
  if (search.value.trim()) parts.push(`search "${search.value.trim()}"`)
  return parts.join(' · ')
}
const shownRows = () => table.value?.sortedRows ?? rows.value

async function toExcel() {
  busy.value = true
  try {
    const sub = filterText()
    const sheets = [
      { name: 'Job Cards', title: 'Operator Job Cards', subtitle: sub, columns: JC_COLUMNS, rows: view.value === 'jc' ? shownRows() : filterJc(jcRows.value) },
      { name: 'Operator Summary', title: 'Operator Summary', subtitle: sub, columns: SUMMARY_COLUMNS, rows: view.value === 'summary' ? shownRows() : filterSummary(summaryRows.value) },
    ]
    if (view.value === 'summary') sheets.reverse()
    await exportExcel(`Operator_Job_Cards_${fromDate.value}_to_${toDate.value}_${stamp()}.xlsx`, sheets)
  } catch (e) {
    errorMsg.value = 'Excel export failed: ' + (e.message || e)
  } finally {
    busy.value = false
  }
}

async function toPdf() {
  busy.value = true
  try {
    await exportPdf(`Operator_${view.value === 'jc' ? 'Job_Cards' : 'Summary'}_${fromDate.value}_to_${toDate.value}.pdf`, {
      title: view.value === 'jc' ? 'Operator Job Cards' : 'Operator Summary',
      subtitle: `${filterText()} · ${rows.value.length} rows`,
      columns: columns.value,
      rows: shownRows(),
      rowStyle: r => (r.stale ? { textColor: [153, 27, 27] } : null),
    })
  } catch (e) {
    errorMsg.value = 'PDF export failed: ' + (e.message || e)
  } finally {
    busy.value = false
  }
}

// ── Data ──
async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await getOperatorJobCards(fromDate.value, toDate.value)
    operators.value = res.operators || []
    unassigned.value = res.unassigned || []
    staleHours.value = res.stale_hours || 24
  } catch (e) {
    errorMsg.value = e.message || 'Could not load operator job cards'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => { if (!document.hidden) load() }, REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped src="../../styles/table-view.css"></style>
