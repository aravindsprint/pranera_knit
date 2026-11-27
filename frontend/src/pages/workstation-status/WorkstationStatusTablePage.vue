<template>
  <div class="tv-page">
    <AppHeader title="Machine Status · Table" active="workstation-status" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="tv-content">

      <!-- View + export -->
      <div class="tv-toolbar">
        <div class="tv-seg">
          <button v-for="v in views" :key="v.key" class="tv-seg__btn" :class="{ 'tv-seg__btn--on': view === v.key }" @click="view = v.key">{{ v.label }}</button>
        </div>
        <div class="tv-spacer"></div>
        <router-link to="/knit-app/workstation-status" class="tv-btn tv-btn--ghost">▦ Card view</router-link>
        <button class="tv-btn tv-btn--xls" :disabled="busy || !rows.length" @click="toExcel">⬇ Excel</button>
        <button class="tv-btn tv-btn--pdf" :disabled="busy || !rows.length" @click="toPdf">⬇ PDF</button>
        <button class="tv-refresh" :disabled="loading" @click="load" title="Refresh">
          <span v-if="loading" class="tv-spinner"></span><span v-else>↻</span>
        </button>
      </div>

      <!-- Filters -->
      <div class="tv-toolbar">
        <input v-model="search" class="tv-search" placeholder="Search machine, WO or item…" />
        <select v-model="stateFilter" class="tv-select">
          <option value="all">All states ({{ machines.length }})</option>
          <option v-for="s in stateOptions" :key="s.key" :value="s.key">{{ s.label }} ({{ s.count }})</option>
        </select>
        <select v-model="typeFilter" class="tv-select">
          <option v-for="t in typeOptions" :key="t" :value="t">{{ t === 'All' ? 'All machine types' : t }}</option>
        </select>
        <select v-if="view === 'wo'" v-model="roleFilter" class="tv-select">
          <option value="All">All WO roles</option>
          <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
        </select>
      </div>
      <div class="tv-info">
        {{ rows.length }} {{ view === 'machine' ? 'machines' : 'work order rows' }}
        <span v-if="generatedAt"> · updated {{ fmt('datetime', generatedAt) }} · auto-refresh every 2 min</span>
        <span v-if="scope === 'assigned'"> · showing your assigned machines only</span>
      </div>

      <div v-if="errorMsg" class="tv-err">⚠ {{ errorMsg }}</div>
      <div v-else-if="loading && !machines.length" class="tv-loading"><span class="tv-spinner"></span> Loading machines…</div>

      <DataTable
        v-else
        ref="table"
        :columns="columns"
        :rows="rows"
        :row-key="r => r._key"
        :row-class="rowClass"
        :totals="singleUom"
        empty-text="No machines match this filter."
      >
        <template #cell-state_label="{ row, value }">
          <span class="tv-badge" :class="`tv-badge--${row.state}`">{{ value }}</span>
        </template>
        <template #cell-role="{ value }">
          <span class="tv-role" :class="`tv-role--${(value || '').split(' ')[0].toLowerCase()}`">{{ value }}</span>
        </template>
        <template #cell-progress_pct="{ value }">
          <span v-if="value !== null && value !== undefined" class="tv-pct">
            <span class="tv-pct__bar"><span :style="{ width: Math.min(value, 100) + '%' }"></span></span>{{ Number(value).toFixed(1) }}%
          </span>
        </template>
        <template #cell-stale="{ value }">
          <span v-if="value" class="tv-stale">⚠ {{ value }}</span>
        </template>
      </DataTable>
      <div v-if="!singleUom && rows.length" class="tv-note">Totals are hidden because the rows mix Kgs and Pcs. Filter by machine type to see totals.</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import DataTable from '@/components/DataTable.vue'
import { getWorkstationStatus } from '@/api/frappe'
import { exportExcel, exportPdf, formatCell, stamp } from '@/utils/tableExport'

const REFRESH_MS = 2 * 60 * 1000
const STATE_LABELS = { running: 'Running', idle: 'Idle · Queued', no_work_order: 'Idle · No WO' }
const ROLES = ['Running', 'Also running', 'Upcoming', 'Unfinished']

const auth = useAuthStore()
const machines = ref([])
const generatedAt = ref(null)
const staleHours = ref(24)
const scope = ref('all')
const loading = ref(false)
const busy = ref(false)
const errorMsg = ref('')
const search = ref('')
const stateFilter = ref('all')
const typeFilter = ref('All')
const roleFilter = ref('All')
const view = ref('machine')
const table = ref(null)
let timer = null

const views = [
  { key: 'machine', label: 'By Machine' },
  { key: 'wo', label: 'All Work Orders' },
]

const fmt = (type, v) => formatCell({ type }, v)

// ── Columns ──
const MACHINE_COLUMNS = [
  { key: 'workstation', label: 'Machine', type: 'text', width: 14 },
  { key: 'machine_type', label: 'Machine Type', type: 'text', width: 14 },
  { key: 'state_label', label: 'Status', type: 'text', width: 14 },
  { key: 'work_order', label: 'Running WO', type: 'text', width: 20 },
  { key: 'item_code', label: 'Item Code', type: 'text', width: 22, pdf: false },
  { key: 'item_name', label: 'Item Name', type: 'text', width: 34 },
  { key: 'uom', label: 'UOM', type: 'text', width: 7 },
  { key: 'qty', label: 'To Manufacture', type: 'num', total: true },
  { key: 'material_transferred', label: 'Material Transferred', type: 'num', total: true },
  { key: 'produced_qty', label: 'Manufactured', type: 'num', total: true },
  { key: 'pending_qty', label: 'Pending', type: 'num', total: true },
  { key: 'progress_pct', label: 'Progress', type: 'pct' },
  { key: 'start_date', label: 'Start Date', type: 'datetime' },
  { key: 'last_production_date', label: 'Last Production', type: 'datetime' },
  { key: 'rolls', label: 'Rolls', type: 'int', total: true },
  { key: 'also_running_count', label: 'Also Running', type: 'int', pdf: false },
  { key: 'upcoming_count', label: 'Upcoming WOs', type: 'int' },
  { key: 'next_wo', label: 'Next WO', type: 'text', width: 20 },
  { key: 'unfinished_count', label: 'Unfinished WOs', type: 'int', pdf: false },
  { key: 'stale', label: 'Alert', type: 'text', width: 24 },
]

const WO_COLUMNS = [
  { key: 'workstation', label: 'Machine', type: 'text', width: 14 },
  { key: 'machine_type', label: 'Machine Type', type: 'text', width: 14, pdf: false },
  { key: 'state_label', label: 'Machine Status', type: 'text', width: 14 },
  { key: 'role', label: 'WO Role', type: 'text', width: 13 },
  { key: 'work_order', label: 'Work Order', type: 'text', width: 20 },
  { key: 'wo_status', label: 'WO Status', type: 'text', width: 12, pdf: false },
  { key: 'item_code', label: 'Item Code', type: 'text', width: 22, pdf: false },
  { key: 'item_name', label: 'Item Name', type: 'text', width: 34 },
  { key: 'uom', label: 'UOM', type: 'text', width: 7 },
  { key: 'qty', label: 'To Manufacture', type: 'num', total: true },
  { key: 'material_transferred', label: 'Material Transferred', type: 'num', total: true },
  { key: 'produced_qty', label: 'Manufactured', type: 'num', total: true },
  { key: 'pending_qty', label: 'Pending', type: 'num', total: true },
  { key: 'progress_pct', label: 'Progress', type: 'pct' },
  { key: 'planned_start_date', label: 'Planned Start', type: 'date' },
  { key: 'start_date', label: 'Start Date', type: 'datetime' },
  { key: 'last_production_date', label: 'Last Production', type: 'datetime' },
  { key: 'rolls', label: 'Rolls', type: 'int', total: true },
  { key: 'sales_order', label: 'Sales Order', type: 'text', width: 20, pdf: false },
  { key: 'stale', label: 'Alert', type: 'text', width: 24 },
]

const columns = computed(() => (view.value === 'machine' ? MACHINE_COLUMNS : WO_COLUMNS))

// ── Rows ──
function staleText(wo) {
  return wo?.stale ? `No rolls for ${staleHours.value}+ h` : ''
}

function woFields(w) {
  return {
    work_order: w.work_order, wo_status: w.wo_status, item_code: w.item_code, item_name: w.item_name,
    uom: w.uom, qty: w.qty, material_transferred: w.material_transferred, produced_qty: w.produced_qty,
    pending_qty: w.pending_qty, progress_pct: w.progress_pct, planned_start_date: w.planned_start_date,
    start_date: w.start_date, last_production_date: w.last_production_date, rolls: w.rolls,
    sales_order: w.sales_order,
  }
}

const machineRows = computed(() => machines.value.map(m => {
  const c = m.current
  return {
    _key: m.workstation,
    workstation: m.workstation,
    machine_type: m.machine_type,
    state: m.state,
    state_label: STATE_LABELS[m.state] || m.state,
    ...(c ? woFields(c) : { uom: m.upcoming[0]?.uom }),
    progress_pct: c ? c.progress_pct : null,
    also_running_count: m.also_running.length,
    upcoming_count: m.upcoming.length,
    next_wo: m.upcoming[0]?.work_order || '',
    unfinished_count: m.unfinished.length,
    stale: staleText(c),
    _search: [m.workstation, ...[c, ...m.also_running, ...m.upcoming].filter(Boolean)
      .flatMap(w => [w.work_order, w.item_code, w.item_name])].join(' ').toLowerCase(),
  }
}))

const woRows = computed(() => {
  const out = []
  for (const m of machines.value) {
    const base = { workstation: m.workstation, machine_type: m.machine_type, state: m.state, state_label: STATE_LABELS[m.state] || m.state }
    const add = (w, role) => out.push({
      _key: `${m.workstation}|${w.work_order}|${role}`,
      ...base, role, ...woFields(w),
      stale: role === 'Running' ? staleText(w) : '',
      _search: [m.workstation, w.work_order, w.item_code, w.item_name].join(' ').toLowerCase(),
    })
    if (m.current) add(m.current, 'Running')
    m.also_running.forEach(w => add(w, 'Also running'))
    m.upcoming.forEach(w => add(w, 'Upcoming'))
    m.unfinished.forEach(w => add(w, 'Unfinished'))
    if (!m.current && !m.also_running.length && !m.upcoming.length && !m.unfinished.length) {
      out.push({ _key: m.workstation, ...base, role: '', _search: m.workstation.toLowerCase() })
    }
  }
  return out
})

function applyFilters(list, withRole) {
  const q = search.value.trim().toLowerCase()
  return list.filter(r => {
    if (stateFilter.value !== 'all' && r.state !== stateFilter.value) return false
    if (typeFilter.value !== 'All' && r.machine_type !== typeFilter.value) return false
    if (withRole && roleFilter.value !== 'All' && r.role !== roleFilter.value) return false
    return !q || r._search.includes(q)
  })
}

const rows = computed(() => view.value === 'machine'
  ? applyFilters(machineRows.value, false)
  : applyFilters(woRows.value, true))

const singleUom = computed(() => new Set(rows.value.map(r => r.uom).filter(Boolean)).size <= 1)

const typeOptions = computed(() => ['All', ...new Set(machines.value.map(m => m.machine_type))])
const stateOptions = computed(() => Object.entries(STATE_LABELS).map(([key, label]) => ({
  key, label, count: machines.value.filter(m => m.state === key).length,
})))

function rowClass(r) {
  return r.stale ? 'tv-row--stale' : null
}

// ── Export ──
function filterText() {
  const parts = []
  if (stateFilter.value !== 'all') parts.push(STATE_LABELS[stateFilter.value])
  if (typeFilter.value !== 'All') parts.push(typeFilter.value)
  if (view.value === 'wo' && roleFilter.value !== 'All') parts.push(`WO role: ${roleFilter.value}`)
  if (search.value.trim()) parts.push(`search "${search.value.trim()}"`)
  return parts.length ? `Filters: ${parts.join(', ')}` : 'All machines'
}

function shownRows() {
  return table.value?.sortedRows ?? rows.value
}

async function toExcel() {
  busy.value = true
  try {
    const sub = `${filterText()} · data as of ${fmt('datetime', generatedAt.value)}`
    const both = [
      { name: 'By Machine', title: 'Machine Status – By Machine', subtitle: sub, columns: MACHINE_COLUMNS, rows: applyFilters(machineRows.value, false) },
      { name: 'All Work Orders', title: 'Machine Status – All Work Orders', subtitle: sub, columns: WO_COLUMNS, rows: applyFilters(woRows.value, true) },
    ]
    // The sheet for the current view first (and in the on-screen sort order).
    if (view.value === 'machine') both[0].rows = shownRows()
    else { both[1].rows = shownRows(); both.reverse() }
    await exportExcel(`Machine_Status_${stamp()}.xlsx`, both)
  } catch (e) {
    errorMsg.value = 'Excel export failed: ' + (e.message || e)
  } finally {
    busy.value = false
  }
}

async function toPdf() {
  busy.value = true
  try {
    await exportPdf(`Machine_Status_${view.value === 'machine' ? 'By_Machine' : 'Work_Orders'}_${stamp()}.pdf`, {
      title: `Machine Status – ${view.value === 'machine' ? 'By Machine' : 'All Work Orders'}`,
      subtitle: `${filterText()} · ${rows.value.length} rows · data as of ${fmt('datetime', generatedAt.value)}`,
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
    const res = await getWorkstationStatus()
    machines.value = res.machines || []
    generatedAt.value = res.generated_at
    staleHours.value = res.stale_hours || 24
    scope.value = res.scope || 'all'
  } catch (e) {
    errorMsg.value = e.message || 'Could not load machine status'
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
