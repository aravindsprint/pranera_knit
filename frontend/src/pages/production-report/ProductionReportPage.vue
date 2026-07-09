<template>
  <div class="rp-page">
    <AppHeader title="Production Report" active="" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="rp-content">

      <!-- Filters -->
      <div class="rp-card">
        <div class="rp-card__title">Filters</div>
        <div class="rp-filter-grid">
          <!-- Date range -->
          <div class="rp-field">
            <label class="rp-label">From Date</label>
            <input v-model="filters.from_date" type="date" class="rp-input" />
          </div>
          <div class="rp-field">
            <label class="rp-label">To Date</label>
            <input v-model="filters.to_date" type="date" class="rp-input" />
          </div>

          <!-- Work Order -->
          <div class="rp-field rp-field--auto">
            <label class="rp-label">Work Order</label>
            <div class="rp-autocomplete">
              <input v-model="filters.work_order" class="rp-input" placeholder="Search WO..."
                @input="fetchOptions('work_order')" @focus="fetchOptions('work_order')"
                @blur="closeDropdown('work_order')" />
              <div class="rp-dropdown" v-if="showDropdown.work_order && options.work_order.length">
                <div v-for="o in options.work_order" :key="o" class="rp-dropdown__item"
                  @mousedown.prevent="selectOption('work_order', o)">{{ o }}</div>
              </div>
            </div>
          </div>

          <!-- Job Card -->
          <div class="rp-field rp-field--auto">
            <label class="rp-label">Job Card</label>
            <div class="rp-autocomplete">
              <input v-model="filters.job_card" class="rp-input" placeholder="Search JC..."
                @input="fetchOptions('job_card')" @focus="fetchOptions('job_card')"
                @blur="closeDropdown('job_card')" />
              <div class="rp-dropdown" v-if="showDropdown.job_card && options.job_card.length">
                <div v-for="o in options.job_card" :key="o" class="rp-dropdown__item"
                  @mousedown.prevent="selectOption('job_card', o)">{{ o }}</div>
              </div>
            </div>
          </div>

          <!-- Roll Packing List -->
          <div class="rp-field rp-field--auto">
            <label class="rp-label">Roll Packing List</label>
            <div class="rp-autocomplete">
              <input v-model="filters.roll_packing_list" class="rp-input" placeholder="Search RPL..."
                @input="fetchOptions('roll_packing_list')" @focus="fetchOptions('roll_packing_list')"
                @blur="closeDropdown('roll_packing_list')" />
              <div class="rp-dropdown" v-if="showDropdown.roll_packing_list && options.roll_packing_list.length">
                <div v-for="o in options.roll_packing_list" :key="o" class="rp-dropdown__item"
                  @mousedown.prevent="selectOption('roll_packing_list', o)">{{ o }}</div>
              </div>
            </div>
          </div>

          <!-- Stock Entry -->
          <div class="rp-field rp-field--auto">
            <label class="rp-label">Stock Entry (MFG)</label>
            <div class="rp-autocomplete">
              <input v-model="filters.stock_entry" class="rp-input" placeholder="Search MF/..."
                @input="fetchOptions('stock_entry')" @focus="fetchOptions('stock_entry')"
                @blur="closeDropdown('stock_entry')" />
              <div class="rp-dropdown" v-if="showDropdown.stock_entry && options.stock_entry.length">
                <div v-for="o in options.stock_entry" :key="o" class="rp-dropdown__item"
                  @mousedown.prevent="selectOption('stock_entry', o)">{{ o }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="rp-filter-actions">
          <button class="rp-btn rp-btn--primary" @click="loadReport" :disabled="loading">
            <span v-if="loading" class="rp-spinner"></span>
            {{ loading ? 'Loading…' : '🔍 Generate Report' }}
          </button>
          <button class="rp-btn rp-btn--ghost" @click="clearFilters">✕ Clear</button>
        </div>
      </div>

      <!-- Summary -->
      <div class="rp-summary" v-if="rows.length">
        <div class="rp-summary__item">
          <span class="rp-summary__num">{{ rows.length }}</span>
          <span class="rp-summary__lbl">Job Cards</span>
        </div>
        <div class="rp-summary__item">
          <span class="rp-summary__num">{{ totalWeight.toFixed(3) }}</span>
          <span class="rp-summary__lbl">Total Weight (kg)</span>
        </div>
        <div class="rp-summary__item">
          <span class="rp-summary__num">{{ totalPcs }}</span>
          <span class="rp-summary__lbl">Total Pcs</span>
        </div>
      </div>

      <!-- Table -->
      <div class="rp-card rp-card--table" v-if="rows.length">
        <div class="rp-table-wrap">
          <table class="rp-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Work Order</th>
                <th>WO Date</th>
                <th>Job Card</th>
                <th>JC Date</th>
                <th>Item Code</th>
                <th>UOM</th>
                <th>Roll Packing List</th>
                <th>Total Weight</th>
                <th>Total Pcs</th>
                <th>Stock Entry (MFG)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in rows" :key="i">
                <td>{{ i + 1 }}</td>
                <td class="rp-link">{{ row.work_order }}</td>
                <td>{{ formatDate(row.wo_date) }}</td>
                <td class="rp-link">{{ row.job_card }}</td>
                <td>{{ formatDate(row.jc_date) }}</td>
                <td class="rp-mono">{{ row.item_code }}</td>
                <td>{{ row.uom }}</td>
                <td class="rp-link">{{ row.roll_packing_list || '—' }}</td>
                <td class="rp-num">{{ row.total_roll_weight }}</td>
                <td class="rp-num">{{ row.total_pcs_qty }}</td>
                <td class="rp-link rp-sm">{{ row.stock_entry_manufacture || '—' }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="8" class="rp-foot-lbl">Total</td>
                <td class="rp-num rp-foot">{{ totalWeight.toFixed(3) }}</td>
                <td class="rp-num rp-foot">{{ totalPcs }}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Empty -->
      <div class="rp-empty" v-else-if="!loading && searched">
        No records found for the selected filters.
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { call } from '@/api/frappe'

const auth = useAuthStore()
const loading = ref(false)
const searched = ref(false)
const rows = ref([])

const today = new Date().toISOString().split('T')[0]
const firstOfMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0]

const filters = reactive({
  from_date: firstOfMonth,
  to_date: today,
  work_order: '',
  job_card: '',
  roll_packing_list: '',
  stock_entry: ''
})

const options = reactive({
  work_order: [], job_card: [], roll_packing_list: [], stock_entry: []
})
const showDropdown = reactive({
  work_order: false, job_card: false, roll_packing_list: false, stock_entry: false
})

let debounceTimer = null

async function fetchOptions(field) {
  showDropdown[field] = true
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    try {
      const resp = await call('knit_report_filter_options', {
        field,
        search: filters[field] || ''
      })
      options[field] = resp?.message || []
    } catch(e) { options[field] = [] }
  }, 300)
}

function selectOption(field, value) {
  filters[field] = value
  showDropdown[field] = false
}

function closeDropdown(field) {
  setTimeout(() => { showDropdown[field] = false }, 150)
}

function clearFilters() {
  filters.from_date = firstOfMonth
  filters.to_date = today
  filters.work_order = ''
  filters.job_card = ''
  filters.roll_packing_list = ''
  filters.stock_entry = ''
  rows.value = []
  searched.value = false
}

const totalWeight = computed(() => rows.value.reduce((s, r) => s + (parseFloat(r.total_roll_weight) || 0), 0))
const totalPcs = computed(() => rows.value.reduce((s, r) => s + (parseInt(r.total_pcs_qty) || 0), 0))

function formatDate(d) {
  if (!d) return '—'
  const parts = String(d).split('-')
  if (parts.length === 3) return parts[2] + '/' + parts[1] + '/' + parts[0]
  return d
}

async function loadReport() {
  loading.value = true
  searched.value = true
  rows.value = []
  try {
    const resp = await call('knit_production_report', { ...filters })
    rows.value = resp?.message || []
  } catch(e) {
    console.error('Report error:', e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.rp-page { min-height:100vh; display:flex; flex-direction:column; background:#f8fafc; }
.rp-content { flex:1; padding:16px 16px 40px; max-width:1200px; width:100%; margin:0 auto; box-sizing:border-box; }

.rp-card { background:white; border-radius:14px; padding:16px; margin-bottom:14px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.rp-card--table { padding:0; overflow:hidden; }
.rp-card__title { font-size:13px; font-weight:800; color:#334155; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:14px; }

.rp-filter-grid { display:grid; grid-template-columns:1fr 1fr 1fr 1fr 1fr 1fr; gap:12px; margin-bottom:14px; }
.rp-field { display:flex; flex-direction:column; gap:4px; position:relative; }
.rp-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#94a3b8; }
.rp-input { padding:9px 12px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:13px; color:#0f172a; background:white; outline:none; box-sizing:border-box; font-family:inherit; width:100%; }
.rp-input:focus { border-color:var(--app-primary,#0f6e56); }

.rp-autocomplete { position:relative; }
.rp-dropdown { position:absolute; top:100%; left:0; right:0; background:white; border:1.5px solid #e2e8f0; border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,0.1); z-index:100; max-height:200px; overflow-y:auto; }
.rp-dropdown__item { padding:9px 12px; font-size:13px; cursor:pointer; color:#334155; }
.rp-dropdown__item:hover { background:#f8fafc; color:var(--app-primary,#0f6e56); }

.rp-filter-actions { display:flex; gap:10px; }
.rp-btn { padding:10px 20px; border-radius:8px; border:none; font-size:13px; font-weight:700; cursor:pointer; font-family:inherit; display:inline-flex; align-items:center; gap:6px; }
.rp-btn--primary { background:var(--app-primary,#0f6e56); color:white; }
.rp-btn--ghost { background:#f1f5f9; color:#334155; }
.rp-btn:disabled { opacity:0.5; cursor:not-allowed; }

.rp-summary { display:flex; gap:12px; margin-bottom:14px; }
.rp-summary__item { flex:1; background:white; border-radius:12px; padding:14px; text-align:center; border:1px solid #e2e8f0; }
.rp-summary__num { display:block; font-size:22px; font-weight:800; color:var(--app-primary,#0f6e56); font-variant-numeric:tabular-nums; }
.rp-summary__lbl { font-size:11px; color:#94a3b8; font-weight:600; text-transform:uppercase; }

.rp-table-wrap { overflow-x:auto; }
.rp-table { width:100%; border-collapse:collapse; font-size:12px; }
.rp-table th { background:#f8fafc; padding:10px 12px; text-align:left; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8; border-bottom:1px solid #e2e8f0; white-space:nowrap; }
.rp-table td { padding:10px 12px; border-bottom:1px solid #f1f5f9; color:#334155; }
.rp-table tbody tr:hover { background:#f8fafc; }
.rp-link { color:var(--app-primary,#0f6e56); font-weight:600; }
.rp-mono { font-family:monospace; font-size:11px; }
.rp-num { text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }
.rp-sm { font-size:11px; }
.rp-foot-lbl { text-align:right; font-weight:800; color:#0f172a; }
.rp-foot { font-weight:800; color:var(--app-primary,#0f6e56); }
.rp-table tfoot td { border-top:2px solid #e2e8f0; background:#f8fafc; }

.rp-empty { text-align:center; padding:40px; color:#94a3b8; font-size:14px; }
.rp-spinner { width:14px; height:14px; border:2px solid rgba(255,255,255,0.4); border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; display:inline-block; }
@keyframes spin { to { transform:rotate(360deg); } }

@media (max-width:900px) {
  .rp-filter-grid { grid-template-columns:1fr 1fr; }
  .rp-summary { flex-direction:column; }
}
@media (max-width:500px) {
  .rp-filter-grid { grid-template-columns:1fr; }
}
</style>
