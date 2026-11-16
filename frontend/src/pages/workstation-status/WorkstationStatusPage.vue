<template>
  <div class="ws-page">
    <AppHeader title="Machine Status" active="workstation-status" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="ws-content">

      <!-- KPI / state filter -->
      <div class="ws-kpi-row">
        <button
          v-for="k in kpis" :key="k.key"
          class="ws-kpi" :class="[`ws-kpi--${k.key}`, { 'ws-kpi--on': stateFilter === k.key }]"
          @click="stateFilter = stateFilter === k.key ? 'all' : k.key"
        >
          <div class="ws-kpi__num">{{ k.count }}</div>
          <div class="ws-kpi__lbl">{{ k.label }}</div>
        </button>
      </div>

      <!-- Search / type / refresh -->
      <div class="ws-toolbar">
        <input v-model="search" class="ws-search" placeholder="Search machine, WO or item…" />
        <div class="ws-chips">
          <button
            v-for="t in typeOptions" :key="t"
            class="ws-chip" :class="{ 'ws-chip--on': typeFilter === t }"
            @click="typeFilter = t"
          >{{ t }}</button>
        </div>
        <button class="ws-refresh" :disabled="loading" @click="load" title="Refresh">
          <span v-if="loading" class="ws-spinner"></span><span v-else>↻</span>
        </button>
      </div>
      <div class="ws-updated" v-if="generatedAt">
        Updated {{ fmtDateTime(generatedAt) }} · auto-refresh every 2 min
      </div>

      <div v-if="errorMsg" class="ws-card ws-state ws-state--err">⚠ {{ errorMsg }}</div>
      <div v-else-if="loading && !machines.length" class="ws-card ws-state">
        <span class="ws-spinner ws-spinner--dark"></span> Loading machines…
      </div>
      <div v-else-if="!filtered.length" class="ws-card ws-state">No machines match this filter.</div>

      <!-- Machine cards -->
      <div class="ws-grid">
        <div v-for="m in filtered" :key="m.workstation" class="ws-card ws-machine" :class="`ws-machine--${m.state}`">

          <div class="ws-machine__hd">
            <div>
              <div class="ws-machine__name">{{ m.workstation }}</div>
              <div class="ws-machine__type">{{ m.machine_type }}<span v-if="m.workstation_type"> · {{ m.workstation_type }}</span></div>
            </div>
            <span class="ws-badge" :class="`ws-badge--${m.state}`">{{ stateLabel(m.state) }}</span>
          </div>

          <!-- Current running WO -->
          <template v-if="m.current">
            <div class="ws-wo">
              <div class="ws-wo__top">
                <span class="ws-wo__name">{{ m.current.work_order }}</span>
                <span class="ws-wo__pct">{{ m.current.progress_pct }}%</span>
              </div>
              <div class="ws-wo__item" :title="m.current.item_code">{{ m.current.item_name || m.current.item_code }}</div>
              <div class="ws-bar"><div class="ws-bar__fill" :style="{ width: Math.min(m.current.progress_pct, 100) + '%' }"></div></div>
            </div>

            <div class="ws-qty-grid">
              <div class="ws-qty"><div class="ws-qty__lbl">To Manufacture</div><div class="ws-qty__val">{{ fmtQty(m.current.qty, m.current.uom) }}</div></div>
              <div class="ws-qty"><div class="ws-qty__lbl">Material Transferred</div><div class="ws-qty__val">{{ fmtQty(m.current.material_transferred, m.current.uom) }}</div></div>
              <div class="ws-qty"><div class="ws-qty__lbl">Manufactured</div><div class="ws-qty__val ws-qty__val--ok">{{ fmtQty(m.current.produced_qty, m.current.uom) }}</div></div>
              <div class="ws-qty"><div class="ws-qty__lbl">Pending</div><div class="ws-qty__val ws-qty__val--pend">{{ fmtQty(m.current.pending_qty, m.current.uom) }}</div></div>
            </div>
            <div class="ws-uom">Qty in {{ m.current.uom || '-' }}</div>

            <div class="ws-dates">
              <div><span class="ws-dates__lbl">Start Date</span>{{ fmtDateTime(m.current.start_date) }}</div>
              <div>
                <span class="ws-dates__lbl">Last Production</span>{{ fmtDateTime(m.current.last_production_date) }}
                <span v-if="m.current.last_production_date" class="ws-ago">({{ ago(m.current.last_production_date) }})</span>
              </div>
            </div>
            <div v-if="m.current.stale" class="ws-warn">
              ⚠ No roll activity for over {{ staleHours }} h, but the job card is still Work In Progress.
            </div>

            <div v-if="m.also_running.length" class="ws-also">
              Also in progress on this machine:
              <span v-for="a in m.also_running" :key="a.work_order" class="ws-also__wo">{{ a.work_order }} ({{ a.progress_pct }}%)</span>
            </div>
          </template>

          <div v-else class="ws-idle-msg">
            {{ m.state === 'idle' ? 'Idle. Next work order is queued below.' : 'Idle. No work order assigned.' }}
          </div>

          <!-- Upcoming -->
          <div class="ws-sub" v-if="m.upcoming.length">
            <div class="ws-sub__hd">Upcoming · {{ m.upcoming.length }}</div>
            <div v-for="u in m.upcoming" :key="u.work_order" class="ws-row">
              <div class="ws-row__main">
                <span class="ws-row__wo">{{ u.work_order }}</span>
                <span class="ws-row__item">{{ u.item_name || u.item_code }}</span>
              </div>
              <div class="ws-row__meta">
                <span>{{ fmtQty(u.pending_qty, u.uom) }} {{ u.uom }}</span>
                <span>MT {{ fmtQty(u.material_transferred, u.uom) }}</span>
                <span v-if="u.planned_start_date">Plan {{ fmtDate(u.planned_start_date) }}</span>
              </div>
            </div>
          </div>

          <!-- Unfinished leftovers (collapsed) -->
          <div class="ws-sub" v-if="m.unfinished.length">
            <button class="ws-sub__toggle" @click="toggle(m.workstation)">
              {{ open[m.workstation] ? '▾' : '▸' }} Unfinished earlier WOs · {{ m.unfinished.length }}
            </button>
            <template v-if="open[m.workstation]">
              <div v-for="u in m.unfinished" :key="u.work_order" class="ws-row ws-row--muted">
                <div class="ws-row__main">
                  <span class="ws-row__wo">{{ u.work_order }}</span>
                  <span class="ws-row__item">{{ u.item_name || u.item_code }}</span>
                </div>
                <div class="ws-row__meta">
                  <span>{{ u.progress_pct }}% done</span>
                  <span>Pending {{ fmtQty(u.pending_qty, u.uom) }} {{ u.uom }}</span>
                  <span v-if="u.last_production_date">Last {{ fmtDate(u.last_production_date) }}</span>
                </div>
              </div>
            </template>
          </div>

        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { getWorkstationStatus } from '@/api/frappe'

const REFRESH_MS = 2 * 60 * 1000

const auth = useAuthStore()
const machines = ref([])
const generatedAt = ref(null)
const staleHours = ref(24)
const loading = ref(false)
const errorMsg = ref('')
const search = ref('')
const stateFilter = ref('all')
const typeFilter = ref('All')
const open = reactive({})
let timer = null

const STATE_LABELS = { running: 'Running', idle: 'Idle · Queued', no_work_order: 'Idle · No WO' }
const stateLabel = s => STATE_LABELS[s] || s

const typeOptions = computed(() => ['All', ...new Set(machines.value.map(m => m.machine_type))])

const kpis = computed(() => {
  const count = s => machines.value.filter(m => m.state === s).length
  return [
    { key: 'all', label: 'Machines', count: machines.value.length },
    { key: 'running', label: 'Running', count: count('running') },
    { key: 'idle', label: 'Idle · Queued', count: count('idle') },
    { key: 'no_work_order', label: 'Idle · No WO', count: count('no_work_order') },
  ]
})

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return machines.value.filter(m => {
    if (stateFilter.value !== 'all' && m.state !== stateFilter.value) return false
    if (typeFilter.value !== 'All' && m.machine_type !== typeFilter.value) return false
    if (!q) return true
    const wos = [m.current, ...m.also_running, ...m.upcoming].filter(Boolean)
    return m.workstation.toLowerCase().includes(q) ||
      wos.some(w => [w.work_order, w.item_code, w.item_name].some(v => (v || '').toLowerCase().includes(q)))
  })
})

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await getWorkstationStatus()
    machines.value = res.machines || []
    generatedAt.value = res.generated_at
    staleHours.value = res.stale_hours || 24
  } catch (e) {
    errorMsg.value = e.message || 'Could not load machine status'
  } finally {
    loading.value = false
  }
}

function toggle(ws) { open[ws] = !open[ws] }

function parseDT(v) {
  if (!v) return null
  const d = new Date(String(v).replace(' ', 'T'))
  return isNaN(d) ? null : d
}
function fmtDateTime(v) {
  const d = parseDT(v)
  if (!d) return '—'
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
}
function fmtDate(v) {
  const d = parseDT(v)
  return d ? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'
}
function ago(v) {
  const d = parseDT(v)
  if (!d) return ''
  const mins = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000))
  if (mins < 60) return `${mins} min ago`
  const h = Math.floor(mins / 60)
  if (h < 48) return `${h} h ago`
  return `${Math.floor(h / 24)} days ago`
}
function fmtQty(n, uom) {
  const v = Number(n) || 0
  const pcs = /^(nos|pcs|pieces?|unit)/i.test(uom || '')
  return v.toLocaleString('en-IN', { maximumFractionDigits: pcs ? 0 : 2, minimumFractionDigits: pcs ? 0 : 2 })
}

onMounted(() => {
  load()
  timer = setInterval(() => { if (!document.hidden) load() }, REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.ws-page { min-height: 100vh; display: flex; flex-direction: column; background: #f1f5f9; }
.ws-content { flex: 1; padding: 12px 16px 40px; width: 100%; box-sizing: border-box; }

.ws-kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px; }
.ws-kpi {
  background: white; border-radius: 14px; padding: 12px 6px; text-align: center;
  border: 1.5px solid #e2e8f0; cursor: pointer; font: inherit;
}
.ws-kpi--on { border-color: var(--app-primary, #059669); box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.15); }
.ws-kpi__num { font-size: 24px; font-weight: 900; font-variant-numeric: tabular-nums; line-height: 1; color: #0f172a; }
.ws-kpi__lbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #94a3b8; margin-top: 4px; }
.ws-kpi--running .ws-kpi__num { color: #059669; }
.ws-kpi--idle .ws-kpi__num { color: #d97706; }
.ws-kpi--no_work_order .ws-kpi__num { color: #dc2626; }

.ws-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 4px; }
.ws-search {
  flex: 1 1 200px; padding: 9px 12px; border: 1.5px solid #e2e8f0; border-radius: 10px;
  font-size: 14px; background: white; outline: none; font-family: inherit; min-width: 0;
}
.ws-search:focus { border-color: var(--app-primary, #059669); }
.ws-chips { display: flex; gap: 6px; flex: 0 1 auto; min-width: 0; overflow-x: auto; scrollbar-width: none; }
.ws-chips::-webkit-scrollbar { display: none; }
.ws-chip {
  padding: 7px 12px; border-radius: 999px; border: 1.5px solid #e2e8f0; background: white;
  font-size: 12px; font-weight: 700; color: #475569; cursor: pointer; font-family: inherit;
  white-space: nowrap; flex-shrink: 0;
}
.ws-chip--on { background: var(--app-primary, #059669); border-color: var(--app-primary, #059669); color: white; }
.ws-refresh {
  width: 38px; height: 38px; border-radius: 10px; border: 1.5px solid #e2e8f0; background: white;
  font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ws-updated { font-size: 11px; color: #94a3b8; margin: 4px 2px 12px; }

.ws-card { background: white; border-radius: 14px; padding: 14px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.ws-state { display: flex; align-items: center; justify-content: center; gap: 8px; color: #64748b; padding: 28px 16px; margin-bottom: 12px; }
.ws-state--err { color: #991b1b; }

.ws-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 12px; }
.ws-machine { border-left: 5px solid #cbd5e1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.ws-machine--running { border-left-color: #059669; }
.ws-machine--idle { border-left-color: #d97706; }
.ws-machine--no_work_order { border-left-color: #dc2626; }

.ws-machine__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.ws-machine__name { font-size: 16px; font-weight: 800; color: #0f172a; }
.ws-machine__type { font-size: 11px; color: #94a3b8; font-weight: 600; margin-top: 2px; }

.ws-badge { font-size: 10px; font-weight: 800; padding: 4px 10px; border-radius: 999px; text-transform: uppercase; white-space: nowrap; }
.ws-badge--running { background: #d1fae5; color: #065f46; }
.ws-badge--idle { background: #fef3c7; color: #92400e; }
.ws-badge--no_work_order { background: #fee2e2; color: #991b1b; }

.ws-wo__top { display: flex; justify-content: space-between; align-items: baseline; }
.ws-wo__name { font-weight: 800; color: var(--app-primary, #059669); font-size: 14px; }
.ws-wo__pct { font-weight: 800; font-size: 13px; color: #334155; font-variant-numeric: tabular-nums; }
.ws-wo__item { font-size: 12px; color: #475569; margin: 2px 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ws-bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.ws-bar__fill { height: 100%; background: linear-gradient(90deg, var(--app-primary, #059669), #34d399); border-radius: 999px; transition: width 0.4s; }

.ws-qty-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 6px; }
.ws-qty { background: #f8fafc; border-radius: 10px; padding: 8px 10px; }
.ws-qty__lbl { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 9.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #94a3b8; }
.ws-qty__val { font-size: 15px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; margin-top: 2px; }
.ws-qty__val--ok { color: #059669; }
.ws-qty__val--pend { color: #d97706; }
.ws-uom { font-size: 10px; color: #94a3b8; margin-top: -6px; text-align: right; }

.ws-dates { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #334155; }
.ws-dates__lbl { display: inline-block; width: 110px; font-size: 10px; font-weight: 700; text-transform: uppercase; color: #94a3b8; }
.ws-ago { color: #94a3b8; font-size: 11px; }
.ws-warn { font-size: 12px; background: #fef2f2; color: #991b1b; border-radius: 8px; padding: 7px 10px; }
.ws-also { font-size: 11.5px; color: #475569; }
.ws-also__wo { display: inline-block; margin-left: 6px; font-weight: 700; color: #1e40af; }

.ws-idle-msg { font-size: 13px; color: #64748b; background: #f8fafc; border-radius: 10px; padding: 10px 12px; }

.ws-sub { border-top: 1px dashed #e2e8f0; padding-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.ws-sub__hd { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; }
.ws-sub__toggle {
  background: none; border: none; padding: 0; text-align: left; cursor: pointer; font-family: inherit;
  font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8;
}
.ws-row { background: #f8fafc; border-radius: 8px; padding: 7px 10px; }
.ws-row--muted { opacity: 0.8; }
.ws-row__main { display: flex; gap: 8px; align-items: baseline; min-width: 0; }
.ws-row__wo { font-weight: 800; font-size: 12.5px; color: #0f172a; white-space: nowrap; }
.ws-row__item { font-size: 11.5px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ws-row__meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 11px; color: #94a3b8; margin-top: 2px; font-variant-numeric: tabular-nums; }

.ws-spinner {
  width: 14px; height: 14px; border: 2px solid rgba(15, 23, 42, 0.2); border-top-color: #0f172a;
  border-radius: 50%; display: inline-block; animation: ws-spin 0.7s linear infinite;
}
@keyframes ws-spin { to { transform: rotate(360deg); } }

@media (max-width: 480px) {
  .ws-kpi__num { font-size: 20px; }
  .ws-kpi__lbl { font-size: 9px; }
  .ws-grid { grid-template-columns: minmax(0, 1fr); }
  .ws-search { flex-basis: 100%; }
  .ws-chips { flex: 1 1 0; }
}
</style>
