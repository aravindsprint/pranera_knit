<template>
  <div class="db-page">
    <AppHeader title="Dashboard" active="dashboard" :username="auth.username" :designation="auth.designation" :show-back="false" />

    <div class="db-content">

      <!-- Filter bar -->
      <div class="db-filterbar">
        <div class="db-filter-group">
          <label class="db-filter-lbl">From</label>
          <input v-model="fromDate" type="date" class="db-filter-input" />
        </div>
        <div class="db-filter-group">
          <label class="db-filter-lbl">To</label>
          <input v-model="toDate" type="date" class="db-filter-input" />
        </div>
        <button class="db-filter-btn" @click="load" :disabled="loading">
          <span v-if="loading" class="db-spinner"></span>
          <span v-else>🔍</span>
        </button>
        <button class="db-refresh" @click="resetDates" title="Reset to today">↺</button>
      </div>

      <!-- KPI row -->
      <div class="db-kpi-row">
        <div class="db-kpi db-kpi--green">
          <div class="db-kpi__num">{{ data.today_rolls }}</div>
          <div class="db-kpi__lbl">Total Rolls</div>
        </div>
        <div class="db-kpi db-kpi--blue">
          <div class="db-kpi__num">{{ data.today_weight?.toFixed(1) }}</div>
          <div class="db-kpi__lbl">Weight (kg)</div>
        </div>
        <div class="db-kpi db-kpi--orange">
          <div class="db-kpi__num">{{ jcWIP }}</div>
          <div class="db-kpi__lbl">In Progress</div>
        </div>
        <div class="db-kpi db-kpi--purple">
          <div class="db-kpi__num">{{ qiPassRate }}%</div>
          <div class="db-kpi__lbl">QI Pass Rate</div>
        </div>
      </div>

      <!-- Daily Trend Chart -->
      <div class="db-card">
        <div class="db-card__title">📈 Production Trend</div>
        <div class="db-chart-wrap">
          <div class="db-chart">
            <div class="db-chart__bars">
              <div v-for="(d, i) in data.weekly" :key="i" class="db-chart__col">
                <div class="db-chart__val">{{ d.weight?.toFixed(0) }}</div>
                <div class="db-chart__bar-wrap">
                  <div class="db-chart__bar" :style="{ height: barHeight(d.weight) + '%' }"></div>
                </div>
                <div class="db-chart__lbl">{{ shortDate(d.date) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Job Card Status + QI -->
      <div class="db-grid-2">
        <div class="db-card">
          <div class="db-card__title">🗂 Job Card Status</div>
          <div class="db-donut-wrap">
            <svg viewBox="0 0 100 100" class="db-donut">
              <circle cx="50" cy="50" r="35" fill="none" stroke="#e2e8f0" stroke-width="12"/>
              <circle cx="50" cy="50" r="35" fill="none" stroke="#059669" stroke-width="12"
                stroke-dasharray="219.9"
                :stroke-dashoffset="219.9 - (219.9 * jcCompleted / jcTotal)"
                stroke-linecap="round" transform="rotate(-90 50 50)"/>
              <text x="50" y="46" text-anchor="middle" font-size="14" font-weight="800" fill="#0f172a">{{ jcCompleted }}</text>
              <text x="50" y="58" text-anchor="middle" font-size="7" fill="#94a3b8">DONE</text>
            </svg>
            <div class="db-legend">
              <div v-for="s in data.jc_stats" :key="s.status" class="db-legend__item">
                <span class="db-legend__dot" :class="jcColor(s.status)"></span>
                <span class="db-legend__lbl">{{ s.status }}</span>
                <span class="db-legend__val">{{ s.cnt }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="db-card">
          <div class="db-card__title">✅ Quality Inspection</div>
          <div class="db-donut-wrap">
            <svg viewBox="0 0 100 100" class="db-donut">
              <circle cx="50" cy="50" r="35" fill="none" stroke="#e2e8f0" stroke-width="12"/>
              <circle cx="50" cy="50" r="35" fill="none" stroke="#059669" stroke-width="12"
                stroke-dasharray="219.9"
                :stroke-dashoffset="219.9 - (219.9 * qiAccepted / qiTotal)"
                stroke-linecap="round" transform="rotate(-90 50 50)"/>
              <text x="50" y="46" text-anchor="middle" font-size="14" font-weight="800" fill="#0f172a">{{ qiPassRate }}%</text>
              <text x="50" y="58" text-anchor="middle" font-size="7" fill="#94a3b8">PASS</text>
            </svg>
            <div class="db-legend">
              <div v-for="s in data.qi_stats" :key="s.status" class="db-legend__item">
                <span class="db-legend__dot" :class="s.status === 'Accepted' ? 'db-legend__dot--green' : 'db-legend__dot--red'"></span>
                <span class="db-legend__lbl">{{ s.status }}</span>
                <span class="db-legend__val">{{ s.cnt }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Active Job Cards -->
      <div class="db-card" v-if="filteredActiveJC.length">
        <div class="db-card__title">⚡ Active Job Cards</div>
        <div class="db-inline-filter">
          <input v-model="filterJC" class="db-filter-input db-filter-input--sm" placeholder="🔍 Filter job card / item..." />
        </div>
        <div class="db-table-wrap">
          <table class="db-table">
            <thead>
              <tr><th>Job Card</th><th>Item Code</th><th>Commercial Name</th><th>Machine</th><th>Status</th></tr>
            </thead>
            <tbody>
              <tr v-for="jc in filteredActiveJC" :key="jc.name">
                <td class="db-link">{{ jc.name }}</td>
                <td class="db-mono">{{ jc.production_item }}</td>
                <td>{{ jc.commercial_name }}</td>
                <td>{{ jc.workstation }}</td>
                <td><span class="db-badge db-badge--wip">{{ jc.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Operators -->
      <div class="db-card" v-if="filteredOperators.length">
        <div class="db-card__title">👷 Top Operators</div>
        <div class="db-inline-filter">
          <input v-model="filterOp" class="db-filter-input db-filter-input--sm" placeholder="🔍 Filter operator..." />
        </div>
        <div class="db-op-list">
          <div v-for="(op, i) in filteredOperators" :key="i" class="db-op-row">
            <div class="db-op-rank">{{ i + 1 }}</div>
            <div class="db-op-name">{{ op.operator || '—' }}</div>
            <div class="db-op-bar-wrap">
              <div class="db-op-bar" :style="{ width: (op.weight / maxOpWeight * 100) + '%' }"></div>
            </div>
            <div class="db-op-stat">{{ op.rolls }} rolls · {{ op.weight }} kg</div>
          </div>
        </div>
      </div>

      <!-- Machine Output -->
      <div class="db-card" v-if="filteredMachines.length">
        <div class="db-card__title">🏭 Machine Output</div>
        <div class="db-inline-filter">
          <input v-model="filterMachine" class="db-filter-input db-filter-input--sm" placeholder="🔍 Filter machine..." />
        </div>
        <div class="db-op-list">
          <div v-for="(m, i) in filteredMachines" :key="i" class="db-op-row">
            <div class="db-op-rank">{{ i + 1 }}</div>
            <div class="db-op-name db-mono">{{ m.machine }}</div>
            <div class="db-op-bar-wrap">
              <div class="db-op-bar db-op-bar--purple" :style="{ width: (m.weight / maxMachineWeight * 100) + '%' }"></div>
            </div>
            <div class="db-op-stat">{{ m.rolls }} rolls · {{ m.weight }} kg</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { call } from '@/api/frappe'

const auth = useAuthStore()
const loading = ref(false)

const today = new Date().toISOString().split('T')[0]
const fromDate = ref(today)
const toDate   = ref(today)

// Inline filters
const filterJC      = ref('')
const filterOp      = ref('')
const filterMachine = ref('')

const data = ref({
  today_rolls: 0, today_weight: 0,
  jc_stats: [], qi_stats: [], weekly: [],
  top_operators: [], machine_output: [], active_jc: [],
  today: ''
})

const jcCompleted = computed(() => data.value.jc_stats.find(s => s.status === 'Completed')?.cnt || 0)
const jcWIP       = computed(() => data.value.jc_stats.find(s => s.status === 'Work In Progress')?.cnt || 0)
const jcTotal     = computed(() => data.value.jc_stats.reduce((s, r) => s + r.cnt, 0) || 1)
const qiAccepted  = computed(() => data.value.qi_stats.find(s => s.status === 'Accepted')?.cnt || 0)
const qiTotal     = computed(() => data.value.qi_stats.reduce((s, r) => s + r.cnt, 0) || 1)
const qiPassRate  = computed(() => Math.round(qiAccepted.value / qiTotal.value * 100))
const maxOpWeight      = computed(() => Math.max(...(data.value.top_operators?.map(o => o.weight) || [1])))
const maxMachineWeight = computed(() => Math.max(...(data.value.machine_output?.map(m => m.weight) || [1])))
const maxWeeklyWeight  = computed(() => Math.max(...(data.value.weekly?.map(d => d.weight) || [1])))

const filteredActiveJC = computed(() => {
  const q = filterJC.value.toLowerCase()
  return (data.value.active_jc || []).filter(r =>
    !q || r.name?.toLowerCase().includes(q) ||
    r.production_item?.toLowerCase().includes(q) ||
    r.commercial_name?.toLowerCase().includes(q) ||
    r.workstation?.toLowerCase().includes(q)
  )
})
const filteredOperators = computed(() => {
  const q = filterOp.value.toLowerCase()
  return (data.value.top_operators || []).filter(r => !q || r.operator?.toLowerCase().includes(q))
})
const filteredMachines = computed(() => {
  const q = filterMachine.value.toLowerCase()
  return (data.value.machine_output || []).filter(r => !q || r.machine?.toLowerCase().includes(q))
})

function barHeight(w) { return Math.max(4, (w / maxWeeklyWeight.value) * 100) }
function shortDate(d) {
  if (!d) return ''
  const parts = String(d).split('-')
  return parts[2] + '/' + parts[1]
}
function jcColor(s) {
  if (s === 'Completed') return 'db-legend__dot--green'
  if (s === 'Work In Progress') return 'db-legend__dot--orange'
  return 'db-legend__dot--gray'
}
function resetDates() {
  fromDate.value = today
  toDate.value = today
  load()
}

async function load() {
  loading.value = true
  try {
    const resp = await call('knit_dashboard_data', {
      from_date: fromDate.value,
      to_date: toDate.value,
      operator_name: ''
    })
    data.value = resp?.message || data.value
  } catch(e) {
    console.error('Dashboard error:', e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.db-page { min-height:100vh; display:flex; flex-direction:column; background:#f1f5f9; }
.db-content { flex:1; padding:12px 16px 40px; width:100%; box-sizing:border-box; }

.db-filterbar { display:flex; align-items:flex-end; gap:8px; margin-bottom:14px; flex-wrap:wrap; }
.db-filter-group { display:flex; flex-direction:column; gap:3px; }
.db-filter-lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8; }
.db-filter-input { padding:8px 10px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:13px; color:#0f172a; background:white; outline:none; font-family:inherit; }
.db-filter-input:focus { border-color:var(--app-primary,#059669); }
.db-filter-input--sm { width:100%; margin-bottom:10px; }
.db-filter-btn { padding:8px 16px; background:var(--app-primary,#059669); color:white; border:none; border-radius:8px; font-size:16px; cursor:pointer; height:38px; display:flex; align-items:center; justify-content:center; }
.db-filter-btn:disabled { opacity:0.5; }
.db-refresh { width:38px; height:38px; border-radius:8px; border:1.5px solid #e2e8f0; background:white; font-size:18px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
.db-inline-filter { margin-bottom:4px; }

.db-kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }
.db-kpi { background:white; border-radius:14px; padding:16px 12px; text-align:center; border:1px solid #e2e8f0; }
.db-kpi__num { font-size:28px; font-weight:900; font-variant-numeric:tabular-nums; line-height:1; }
.db-kpi__lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8; margin-top:4px; }
.db-kpi--green .db-kpi__num { color:#059669; }
.db-kpi--blue .db-kpi__num { color:#2563eb; }
.db-kpi--orange .db-kpi__num { color:#d97706; }
.db-kpi--purple .db-kpi__num { color:#7c3aed; }

.db-card { background:white; border-radius:14px; padding:16px; margin-bottom:12px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
.db-card__title { font-size:13px; font-weight:800; color:#334155; margin-bottom:14px; }
.db-grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }

.db-chart-wrap { overflow-x:auto; }
.db-chart { min-width:300px; }
.db-chart__bars { display:flex; align-items:flex-end; gap:6px; height:140px; padding-bottom:24px; }
.db-chart__col { flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; height:100%; }
.db-chart__val { font-size:9px; font-weight:700; color:#64748b; }
.db-chart__bar-wrap { flex:1; width:100%; display:flex; align-items:flex-end; }
.db-chart__bar { width:100%; background:linear-gradient(to top, var(--app-primary,#059669), #34d399); border-radius:4px 4px 0 0; transition:height 0.5s; min-height:4px; }
.db-chart__lbl { font-size:9px; color:#94a3b8; font-weight:600; white-space:nowrap; }

.db-donut-wrap { display:flex; align-items:center; gap:16px; }
.db-donut { width:100px; height:100px; flex-shrink:0; }
.db-legend { flex:1; display:flex; flex-direction:column; gap:8px; }
.db-legend__item { display:flex; align-items:center; gap:8px; font-size:12px; }
.db-legend__dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.db-legend__dot--green { background:#059669; }
.db-legend__dot--red { background:#dc2626; }
.db-legend__dot--orange { background:#d97706; }
.db-legend__dot--gray { background:#94a3b8; }
.db-legend__lbl { flex:1; color:#334155; font-weight:500; }
.db-legend__val { font-weight:800; color:#0f172a; }

.db-table-wrap { overflow-x:auto; }
.db-table { width:100%; border-collapse:collapse; font-size:12px; }
.db-table th { background:#f8fafc; padding:8px 10px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; color:#94a3b8; border-bottom:1px solid #e2e8f0; white-space:nowrap; }
.db-table td { padding:9px 10px; border-bottom:1px solid #f1f5f9; color:#334155; }
.db-link { color:var(--app-primary,#059669); font-weight:700; }
.db-mono { font-family:monospace; font-size:11px; }
.db-badge { font-size:10px; font-weight:700; padding:2px 8px; border-radius:20px; }
.db-badge--wip { background:rgba(217,119,6,0.15); color:#d97706; }

.db-op-list { display:flex; flex-direction:column; gap:10px; }
.db-op-row { display:flex; align-items:center; gap:10px; }
.db-op-rank { width:20px; font-size:12px; font-weight:800; color:#94a3b8; text-align:center; flex-shrink:0; }
.db-op-name { width:120px; font-size:12px; font-weight:600; color:#334155; flex-shrink:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.db-op-bar-wrap { flex:1; height:8px; background:#f1f5f9; border-radius:4px; overflow:hidden; }
.db-op-bar { height:100%; background:linear-gradient(to right, var(--app-primary,#059669), #34d399); border-radius:4px; transition:width 0.6s; }
.db-op-bar--purple { background:linear-gradient(to right, #7c3aed, #a78bfa); }
.db-op-stat { font-size:11px; color:#64748b; white-space:nowrap; }

.db-spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,0.4); border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; display:inline-block; }
@keyframes spin { to { transform:rotate(360deg); } }

@media (max-width:600px) {
  .db-kpi-row { grid-template-columns:repeat(2,1fr); }
  .db-grid-2 { grid-template-columns:1fr; }
  .db-op-name { width:80px; }
}
</style>
