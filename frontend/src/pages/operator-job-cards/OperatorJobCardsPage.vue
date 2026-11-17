<template>
  <div class="oj-page">
    <AppHeader title="Operator Job Cards" active="operator-job-cards" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="oj-content">

      <!-- Period -->
      <div class="oj-toolbar">
        <div class="oj-chips">
          <button v-for="p in presets" :key="p.key" class="oj-chip" :class="{ 'oj-chip--on': preset === p.key }" @click="setPreset(p.key)">{{ p.label }}</button>
        </div>
        <div class="oj-dates" v-if="preset === 'custom'">
          <input type="date" v-model="fromDate" class="oj-date" :max="toDate" />
          <span>→</span>
          <input type="date" v-model="toDate" class="oj-date" :min="fromDate" />
          <button class="oj-go" @click="load">Go</button>
        </div>
        <button class="oj-refresh" :disabled="loading" @click="load" title="Refresh">
          <span v-if="loading" class="oj-spinner"></span><span v-else>↻</span>
        </button>
      </div>

      <!-- KPIs -->
      <div class="oj-kpi-row">
        <div class="oj-kpi"><div class="oj-kpi__num">{{ operators.length }}</div><div class="oj-kpi__lbl">Operators</div></div>
        <div class="oj-kpi oj-kpi--cur"><div class="oj-kpi__num">{{ totalCount('current') }}</div><div class="oj-kpi__lbl">Current</div></div>
        <div class="oj-kpi oj-kpi--up"><div class="oj-kpi__num">{{ totalCount('upcoming') }}</div><div class="oj-kpi__lbl">Upcoming</div></div>
        <div class="oj-kpi oj-kpi--fin"><div class="oj-kpi__num">{{ totalCount('finished') }}</div><div class="oj-kpi__lbl">Finished</div></div>
      </div>

      <input v-model="search" class="oj-search" placeholder="Search operator, job card, work order or machine…" />
      <div class="oj-period">Finished = job cards whose last roll ended {{ periodLabel }}</div>

      <div v-if="errorMsg" class="oj-card oj-state oj-state--err">⚠ {{ errorMsg }}</div>
      <div v-else-if="loading && !operators.length" class="oj-card oj-state"><span class="oj-spinner"></span> Loading…</div>
      <div v-else-if="!filtered.length && !unassigned.length" class="oj-card oj-state">No job cards found.</div>

      <!-- Operators -->
      <div class="oj-grid">
        <div v-for="op in filtered" :key="op.employee" class="oj-card oj-op">
          <div class="oj-op__hd">
            <div class="oj-avatar">{{ initials(op.employee_name) }}</div>
            <div class="oj-op__who">
              <div class="oj-op__name">{{ op.employee_name || op.employee }}</div>
              <div class="oj-op__sub">{{ op.employee }}<span v-if="op.designation"> · {{ op.designation }}</span></div>
            </div>
            <span v-if="op.current.some(j => !j.stale)" class="oj-badge oj-badge--cur">Working</span>
            <span v-else-if="op.current.length" class="oj-badge oj-badge--stale">Check</span>
            <span v-else class="oj-badge oj-badge--idle">Not running</span>
          </div>

          <div class="oj-tabs">
            <button v-for="t in tabs" :key="t.key" class="oj-tab" :class="{ 'oj-tab--on': tabOf(op) === t.key }" @click="tab[op.employee] = t.key">
              {{ t.label }} <span class="oj-tab__n">{{ op[t.key].length }}</span>
            </button>
          </div>

          <div v-if="tabOf(op) === 'finished' && op.finished_totals?.length" class="oj-totals">
            <span v-for="t in op.finished_totals" :key="t.uom">
              <b>{{ fmtQty(t.qty, t.uom) }} {{ t.uom }}</b> · {{ t.rolls }} rolls · {{ t.job_cards }} JC
            </span>
          </div>

          <div v-if="!op[tabOf(op)].length" class="oj-empty">{{ emptyText(tabOf(op)) }}</div>

          <div v-for="jc in op[tabOf(op)]" :key="jc.job_card" class="oj-jc" :class="{ 'oj-jc--stale': jc.stale }">
            <div class="oj-jc__top">
              <span class="oj-jc__name">{{ jc.job_card }}</span>
              <span class="oj-jc__mc">{{ shortMachine(jc.workstation) }}</span>
            </div>
            <div class="oj-jc__wo">{{ jc.work_order }} · <span class="oj-jc__item">{{ jc.item_name || jc.item_code }}</span></div>

            <template v-if="jc.status !== 'Open'">
              <div class="oj-bar"><div class="oj-bar__fill" :style="{ width: Math.min(jc.progress_pct, 100) + '%' }"></div></div>
              <div class="oj-jc__meta">
                <span><b>{{ fmtQty(jc.produced, jc.uom) }}</b> / {{ fmtQty(jc.for_quantity, jc.uom) }} {{ jc.uom }}</span>
                <span>{{ jc.rolls }} rolls</span>
              </div>
              <div class="oj-jc__meta">
                <span>Start {{ fmtDT(jc.start_time) }}</span>
                <span v-if="jc.status === 'Completed'">Finished {{ fmtDT(jc.finished_at) }}</span>
                <span v-else-if="jc.end_time">Last roll {{ ago(jc.end_time) }}</span>
              </div>
              <div v-if="jc.stale" class="oj-warn">⚠ No roll activity for {{ staleHours }}+ h but still Work In Progress</div>
            </template>
            <div v-else class="oj-jc__meta">
              <span>{{ fmtQty(jc.for_quantity, jc.uom) }} {{ jc.uom }} to knit</span>
              <span v-if="jc.planned_start_date">Plan {{ fmtDate(jc.planned_start_date) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Upcoming job cards with no operator yet -->
      <div v-if="unassignedFiltered.length" class="oj-card oj-unassigned">
        <div class="oj-unassigned__hd">
          <span>Upcoming job cards without an operator · {{ unassignedFiltered.length }}</span>
          <router-link v-if="access.isSupervisor" to="/knit-app/home" class="oj-link">Assign on Job Cards 👤</router-link>
        </div>
        <div class="oj-unassigned__grid">
          <div v-for="jc in unassignedFiltered" :key="jc.job_card" class="oj-jc">
            <div class="oj-jc__top">
              <span class="oj-jc__name">{{ jc.job_card }}</span>
              <span class="oj-jc__mc">{{ shortMachine(jc.workstation) }}</span>
            </div>
            <div class="oj-jc__wo">{{ jc.work_order }} · <span class="oj-jc__item">{{ jc.item_name || jc.item_code }}</span></div>
            <div class="oj-jc__meta">
              <span>{{ fmtQty(jc.for_quantity, jc.uom) }} {{ jc.uom }}</span>
              <span v-if="jc.planned_start_date">Plan {{ fmtDate(jc.planned_start_date) }}</span>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { usePageAccessStore } from '@/stores/pageAccess'
import AppHeader from '@/components/AppHeader.vue'
import { getOperatorJobCards } from '@/api/frappe'

const REFRESH_MS = 2 * 60 * 1000

const auth = useAuthStore()
const access = usePageAccessStore()
access.ensureLoaded()

const operators = ref([])
const unassigned = ref([])
const staleHours = ref(24)
const loading = ref(false)
const errorMsg = ref('')
const search = ref('')
const tab = reactive({})
let timer = null

const tabs = [
  { key: 'current', label: 'Current' },
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'finished', label: 'Finished' },
]

// ── Period ──
const presets = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: '7d', label: 'Last 7 days' },
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
  if (key !== 'custom') load()
}
const periodLabel = computed(() =>
  fromDate.value === toDate.value ? `on ${fmtDate(fromDate.value)}` : `${fmtDate(fromDate.value)} – ${fmtDate(toDate.value)}`)

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

const matches = (jc, q) =>
  [jc.job_card, jc.work_order, jc.workstation, jc.item_name, jc.item_code].some(v => (v || '').toLowerCase().includes(q))

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return operators.value
  return operators.value.filter(op =>
    [op.employee, op.employee_name].some(v => (v || '').toLowerCase().includes(q)) ||
    [...op.current, ...op.upcoming, ...op.finished].some(jc => matches(jc, q)))
})
const unassignedFiltered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return q ? unassigned.value.filter(jc => matches(jc, q)) : unassigned.value
})

function totalCount(key) {
  // A job card shared by two operators is counted once.
  const seen = new Set()
  for (const op of operators.value) for (const jc of op[key]) seen.add(jc.job_card)
  return seen.size
}

function tabOf(op) {
  if (tab[op.employee]) return tab[op.employee]
  return op.current.length ? 'current' : op.upcoming.length ? 'upcoming' : 'finished'
}
function emptyText(key) {
  return { current: 'Nothing running.', upcoming: 'No job card assigned yet.', finished: 'Nothing finished in this period.' }[key]
}

// ── Formatting ──
function initials(name) {
  return (name || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase()
}
function shortMachine(ws) { return (ws || '').split('/')[0] }
function parseDT(v) {
  if (!v) return null
  const d = new Date(String(v).replace(' ', 'T'))
  return isNaN(d) ? null : d
}
function fmtDT(v) {
  const d = parseDT(v)
  return d ? d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }) : '—'
}
function fmtDate(v) {
  const d = parseDT(v)
  return d ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'
}
function ago(v) {
  const d = parseDT(v)
  if (!d) return ''
  const mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000))
  if (mins < 60) return `${mins} min ago`
  const h = Math.floor(mins / 60)
  return h < 48 ? `${h} h ago` : `${Math.floor(h / 24)} days ago`
}
function fmtQty(n, uom) {
  const pcs = /^(nos|pcs)/i.test(uom || '')
  return (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: pcs ? 0 : 2 })
}

onMounted(() => {
  load()
  timer = setInterval(() => { if (!document.hidden) load() }, REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.oj-page { min-height: 100vh; display: flex; flex-direction: column; background: #f1f5f9; }
.oj-content { flex: 1; padding: 12px 16px 40px; width: 100%; box-sizing: border-box; }

.oj-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.oj-chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; flex: 1 1 0; min-width: 0; }
.oj-chips::-webkit-scrollbar { display: none; }
.oj-chip {
  padding: 7px 12px; border-radius: 999px; border: 1.5px solid #e2e8f0; background: white; white-space: nowrap;
  font-size: 12px; font-weight: 700; color: #475569; cursor: pointer; font-family: inherit; flex-shrink: 0;
}
.oj-chip--on { background: var(--app-primary, #059669); border-color: var(--app-primary, #059669); color: white; }
.oj-dates { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #64748b; flex-basis: 100%; }
.oj-date { padding: 7px 8px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 13px; font-family: inherit; background: white; min-width: 0; flex: 1; }
.oj-go { padding: 8px 14px; border: none; border-radius: 8px; background: var(--app-primary, #059669); color: white; font-weight: 700; cursor: pointer; }
.oj-refresh {
  width: 38px; height: 38px; border-radius: 10px; border: 1.5px solid #e2e8f0; background: white; flex-shrink: 0;
  font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center;
}

.oj-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
.oj-kpi { background: white; border-radius: 14px; padding: 12px 6px; text-align: center; border: 1px solid #e2e8f0; }
.oj-kpi__num { font-size: 24px; font-weight: 900; line-height: 1; color: #0f172a; font-variant-numeric: tabular-nums; }
.oj-kpi__lbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #94a3b8; margin-top: 4px; }
.oj-kpi--cur .oj-kpi__num { color: #059669; }
.oj-kpi--up .oj-kpi__num { color: #2563eb; }
.oj-kpi--fin .oj-kpi__num { color: #7c3aed; }

.oj-search {
  width: 100%; box-sizing: border-box; padding: 9px 12px; border: 1.5px solid #e2e8f0; border-radius: 10px;
  font-size: 14px; background: white; outline: none; font-family: inherit;
}
.oj-search:focus { border-color: var(--app-primary, #059669); }
.oj-period { font-size: 11px; color: #94a3b8; margin: 5px 2px 12px; }

.oj-card { background: white; border-radius: 14px; padding: 14px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.oj-state { display: flex; align-items: center; justify-content: center; gap: 8px; color: #64748b; padding: 28px 16px; margin-bottom: 12px; }
.oj-state--err { color: #991b1b; }

.oj-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(340px, 100%), 1fr)); gap: 12px; align-items: start; }
.oj-op { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.oj-op__hd { display: flex; align-items: center; gap: 10px; }
.oj-avatar {
  width: 38px; height: 38px; border-radius: 50%; background: color-mix(in srgb, var(--app-primary, #059669) 15%, white);
  color: var(--app-primary, #059669); font-weight: 800; font-size: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.oj-op__who { flex: 1; min-width: 0; }
.oj-op__name { font-size: 15px; font-weight: 800; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.oj-op__sub { font-size: 11px; color: #94a3b8; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.oj-badge { font-size: 10px; font-weight: 800; padding: 4px 10px; border-radius: 999px; text-transform: uppercase; white-space: nowrap; }
.oj-badge--cur { background: #d1fae5; color: #065f46; }
.oj-badge--idle { background: #f1f5f9; color: #64748b; }
.oj-badge--stale { background: #ffedd5; color: #9a3412; }

.oj-tabs { display: grid; grid-template-columns: repeat(3, 1fr); background: #f1f5f9; border-radius: 10px; padding: 3px; gap: 3px; }
.oj-tab {
  border: none; background: transparent; padding: 7px 4px; border-radius: 8px; font-size: 12px; font-weight: 700;
  color: #64748b; cursor: pointer; font-family: inherit; white-space: nowrap;
}
.oj-tab--on { background: white; color: #0f172a; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
.oj-tab__n { display: inline-block; min-width: 18px; padding: 0 5px; margin-left: 2px; border-radius: 999px; background: #e2e8f0; font-size: 10.5px; }
.oj-tab--on .oj-tab__n { background: var(--app-primary, #059669); color: white; }

.oj-totals { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: #475569; background: #f5f3ff; border-radius: 8px; padding: 7px 10px; }
.oj-totals b { color: #5b21b6; }
.oj-empty { font-size: 12.5px; color: #94a3b8; padding: 8px 2px; }

.oj-jc { background: #f8fafc; border-radius: 10px; padding: 9px 11px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.oj-jc--stale { background: #fff7ed; }
.oj-jc__top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.oj-jc__name { font-weight: 800; font-size: 13px; color: #0f172a; }
.oj-jc__mc { font-size: 11px; font-weight: 800; color: #1e40af; background: #dbeafe; padding: 1px 8px; border-radius: 6px; }
.oj-jc__wo { font-size: 12px; color: #334155; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.oj-jc__item { font-weight: 500; color: #64748b; }
.oj-jc__meta { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; font-size: 11.5px; color: #64748b; font-variant-numeric: tabular-nums; }
.oj-jc__meta b { color: #0f172a; }
.oj-bar { height: 5px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.oj-bar__fill { height: 100%; background: linear-gradient(90deg, var(--app-primary, #059669), #34d399); }
.oj-warn { font-size: 11.5px; color: #9a3412; font-weight: 600; }

.oj-unassigned { margin-top: 14px; border-left: 5px solid #d97706; }
.oj-unassigned__hd { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; font-weight: 800; color: #92400e; margin-bottom: 10px; }
.oj-link { font-size: 12px; font-weight: 700; color: var(--app-primary, #059669); text-decoration: none; }
.oj-unassigned__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr)); gap: 8px; }

.oj-spinner {
  width: 14px; height: 14px; border: 2px solid rgba(15, 23, 42, 0.2); border-top-color: #0f172a;
  border-radius: 50%; display: inline-block; animation: oj-spin 0.7s linear infinite;
}
@keyframes oj-spin { to { transform: rotate(360deg); } }

@media (max-width: 480px) {
  .oj-chip { padding: 7px 10px; }
  .oj-kpi__num { font-size: 20px; }
  .oj-kpi__lbl { font-size: 9px; }
}
</style>
