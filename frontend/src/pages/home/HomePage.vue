<template>
  <div class="home-page" :data-theme="theme">

    <!-- Drawer Overlay -->
    <transition name="overlay-fade">
      <div v-if="drawerOpen" class="drawer-overlay" @click="drawerOpen = false"></div>
    </transition>

    <!-- Side Drawer -->
    <transition name="drawer-slide">
      <aside v-if="drawerOpen" class="drawer">
        <div class="drawer-header">
          <div class="drawer-avatar">{{ initials }}</div>
          <div class="drawer-user">
            <div class="drawer-user__name">{{ auth.username || 'User' }}</div>
            <div class="drawer-user__role">{{ auth.designation || 'Operator' }}</div>
          </div>
          <button class="drawer-close" @click="drawerOpen = false">✕</button>
        </div>

        <nav class="drawer-nav">
          <div class="drawer-section-label">PRODUCTION</div>
          <button class="drawer-link" @click="navigate('/knit-app/work-order')">
            <span class="drawer-link__icon">📄</span><span>Work Order</span>
          </button>
          <button class="drawer-link drawer-link--active" @click="navigate('/knit-app/home')">
            <span class="drawer-link__icon">🗂</span><span>Job Cards</span>
          </button>
          <button class="drawer-link" @click="navigate('/knit-app/roll-wise-pick-list')">
            <span class="drawer-link__icon">📦</span><span>Roll-wise Pick List</span>
          </button>


          <div class="drawer-section-label" style="margin-top:8px">PRODUCTION DATA</div>
            <button class="drawer-link" @click="navigate('/knit-app/rolls')">
              <span class="drawer-link__icon">🧶</span><span>Rolls</span>
            </button>
            <button class="drawer-link" @click="navigate('/knit-app/stock-entry')">
              <span class="drawer-link__icon">📦</span><span>Stock Entry</span>
            </button>
          <div class="drawer-section-label" style="margin-top:8px">REPORTS</div>
          <button class="drawer-link" @click="navigate('/knit-app/production-report')">
            <span class="drawer-link__icon">📋</span><span>Production Report</span>
          </button>
          <button class="drawer-link" @click="navigate('/knit-app/process-loss')">
            <span class="drawer-link__icon">📉</span><span>Process Loss</span>
          </button>
          <div class="drawer-section-label" style="margin-top:8px">ANALYTICS</div>
          <button class="drawer-link" @click="navigate('/knit-app/dashboard')">
            <span class="drawer-link__icon">📈</span><span>Dashboard</span>
          </button>
        </nav>

        <div class="drawer-themes">
          <div class="drawer-section-label">THEME</div>
          <div class="theme-grid">
            <button
              v-for="t in themes" :key="t.id"
              class="theme-btn"
              :class="{ 'theme-btn--active': theme === t.id }"
              :style="{ background: t.color }"
              @click="setTheme(t.id)"
              :title="t.name"
            ><span v-if="theme === t.id" style="color:white;font-weight:800">✓</span></button>
          </div>
        </div>

        <div class="drawer-footer">
          <button class="drawer-logout" @click="logout">
            <span>⎋</span><span>Logout</span>
          </button>
        </div>
      </aside>
    </transition>

    <!-- Header -->
    <header class="home-header">
      <button class="h-menu-btn" @click="drawerOpen = true">
        <span class="hamburger"></span>
        <span class="hamburger"></span>
        <span class="hamburger"></span>
      </button>
      <div class="home-header__center">
        <div class="home-header__title">Job Cards</div>
        <div class="home-header__sub">{{ auth.username }} · {{ auth.designation }}</div>
      </div>
      <button class="h-icon-btn" @click="refresh" :disabled="homeStore.loading">↻</button>
    </header>

    <!-- Offline / cache banner -->
    <div class="home-offline-bar" v-if="!isOnline && homeStore.jobCards.length">
      📵 Offline — showing cached job cards
    </div>
    <div class="home-offline-bar home-offline-bar--error" v-if="!isOnline && !homeStore.jobCards.length">
      📵 Offline — no cached data. Connect to load job cards.
    </div>

    <!-- Summary Strip -->
    <div class="home-strips" v-if="homeStore.jobCards.length">
      <div class="s-pill s-pill--wip"><span class="s-num">{{ wipCount }}</span><span class="s-lbl">In Progress</span></div>
      <div class="s-pill s-pill--open"><span class="s-num">{{ openCount }}</span><span class="s-lbl">Open</span></div>
    </div>

    <!-- Toolbar -->
    <div class="home-toolbar">
      <div class="home-search">
        <span class="home-search__icon">🔍</span>
        <input v-model="search" class="home-search__input" placeholder="Search job card, item, workstation…" type="search" />
      </div>
      <select v-model="statusFilter" class="home-filter">
        <option value="">All</option>
        <option value="Work In Progress">In Progress</option>
        <option value="Open">Open</option>
        <option value="Pending">Pending</option>
        <option value="Completed">Completed</option>
      </select>
    </div>

    <!-- Content -->
    <div class="home-content">
      <div v-if="homeStore.loading && !homeStore.jobCards.length" class="home-loading">
        <div class="home-spinner"></div><p>Loading job cards…</p>
      </div>
      <div v-else-if="!filtered.length && !homeStore.loading" class="home-empty">
        <div style="font-size:44px;opacity:0.35">🧶</div>
        <div class="home-empty__title">{{ search || statusFilter ? 'No results found' : 'No job cards available' }}</div>
        <div class="home-empty__sub" v-if="search || statusFilter">Clear the search or filter</div>
      </div>
      <div class="jc-grid">
        <div v-for="jc in filtered" :key="jc.name || jc.id" class="jc-card" :class="`jc-card--${homeStore.statusColour(jc.status)}`">
          <div class="jc-top">
            <div class="jc-id">{{ jc.name || jc.id }}</div>
            <span :class="`jc-badge jc-badge--${homeStore.statusColour(jc.status)}`">{{ jc.status }}</span>
          </div>
          <div class="jc-wo">{{ jc.work_order }}</div>
          <div class="jc-details">
            <div class="jc-detail">
              <span class="jc-detail__l">Item</span>
              <span class="jc-detail__v">
                {{ jc.production_item || '—' }}
                <span v-if="jc.commercial_name" class="jc-detail__side">· {{ jc.commercial_name }}</span>
              </span>
            </div>
            <div class="jc-detail"><span class="jc-detail__l">Workstation</span><span class="jc-detail__v">{{ jc.workstation || '—' }}</span></div>
          </div>
          <div class="jc-prog" v-if="jc.for_quantity">
            <div class="jc-prog__bar"><div class="jc-prog__fill" :style="{ width: pct(jc) + '%' }"></div></div>
            <span class="jc-prog__lbl">{{ jc.produced_qty || 0 }} / {{ jc.for_quantity }}</span>
          </div>
          <div class="jc-actions">
            <button class="jc-btn jc-btn--primary" @click="openCreateRoll(jc)">+ Roll</button>
            <button v-if="!auth.isKnittingOperator" class="jc-btn" :class="jc.quality_inspection ? 'jc-btn--qi-done' : 'jc-btn--outline'" @click="createQI(jc)">{{ jc.quality_inspection ? '✓ QI Done' : '✓ QI' }}</button>
            <button v-if="auth.isSupervisor" class="jc-btn jc-btn--assign" @click.stop="openAssignModal(jc)" title="Assign Employee">👤</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Nav -->
    <nav class="home-nav">
      <button class="home-nav__item home-nav__item--active"><span>🗂</span><span>Job Cards</span></button>
      <button class="home-nav__item" @click="navigate('/knit-app/roll-wise-pick-list')"><span>📦</span><span>Pick List</span></button>
      <button class="home-nav__item" @click="navigate('/knit-app/dashboard')"><span>📈</span><span>Dashboard</span></button>
      <button class="home-nav__item" @click="drawerOpen = true"><span>☰</span><span>Menu</span></button>
    </nav>

  </div>

  <!-- ── Assign Employee Modal ── -->
  <div class="assign-overlay" v-if="assignModal.open" @click.self="closeAssignModal">
    <div class="assign-modal">
      <div class="assign-modal__hd">
        <div>
          <div class="assign-modal__title">Assign Employee</div>
          <div class="assign-modal__sub">{{ assignModal.jobCard?.name }}</div>
        </div>
        <button class="assign-modal__close" @click="closeAssignModal">✕</button>
      </div>

      <!-- Current assignment -->
      <div v-if="assignModal.assigned.length" class="assign-current">
        <div class="assign-current__label">Currently assigned</div>
        <div v-for="e in assignModal.assigned" :key="e.employee" class="assign-chip">
          👤 {{ e.custom_employee_name || e.employee }}
        </div>
      </div>

      <!-- Employee search + list -->
      <div class="assign-field">
        <label class="assign-label">Select Employee</label>
        <input class="assign-input" v-model="assignModal.search"
          placeholder="Search by name or ID…"
          @input="onEmpSearch"
          @focus="onEmpSearch"
          autocomplete="off" />
      </div>

      <!-- Results list — inline, not absolute -->
      <div class="assign-results" v-if="assignModal.options.length">
        <div v-for="e in assignModal.options" :key="e.name"
          class="assign-result-item" @click="selectEmp(e)">
          <div class="assign-dropdown__name">{{ e.employee_name }}</div>
          <div class="assign-dropdown__sub">{{ e.name }} · {{ e.designation }}</div>
        </div>
      </div>
      <div class="assign-no-results" v-else-if="!isOnline && assignModal.cacheEmpty">
        ⚠ Employee list not cached yet. Connect once online to enable offline assignment.
      </div>
      <div class="assign-no-results" v-else-if="assignModal.search && !assignModal.options.length">
        No employees found
      </div>

      <!-- Selected employee preview -->
      <div v-if="assignModal.selected" class="assign-selected">
        <div class="assign-selected__info">
          <span class="assign-selected__name">{{ assignModal.selected.employee_name }}</span>
          <span class="assign-selected__id">{{ assignModal.selected.name }}</span>
        </div>
        <button class="assign-selected__clear" @click="assignModal.selected = null; assignModal.search = ''">✕</button>
      </div>

      <div class="assign-error"   v-if="assignModal.error">⚠ {{ assignModal.error }}</div>
      <div class="assign-success" v-if="assignModal.successMsg">✓ {{ assignModal.successMsg }}</div>

      <div class="assign-actions">
        <button class="assign-btn assign-btn--ghost" @click="closeAssignModal">Cancel</button>
        <button class="assign-btn assign-btn--primary"
          :disabled="!assignModal.selected || assignModal.loading"
          @click="assignEmployee(assignModal.selected)">
          <span v-if="assignModal.loading" class="assign-spinner"></span>
          {{ assignModal.loading ? 'Assigning…' : 'Assign' }}
        </button>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useHomeStore } from '@/stores/home'
import { useRollStore } from '@/stores/roll'
import { useQIStore } from '@/stores/qualityInspection'
import { isOnline, checkReachable } from '@/composables/useSync'
import { call } from '@/api/frappe'
import { db } from '@/db'

const router = useRouter()
const route = useRoute()
watch(() => route.query.work_order, (wo) => {
  if (wo) search.value = wo
})
const auth = useAuthStore()
const homeStore = useHomeStore()
const rollStore = useRollStore()
const qiStore = useQIStore()

const search = ref(route.query.work_order || '')
const statusFilter = ref('')
const drawerOpen = ref(false)
const theme = ref(localStorage.getItem('KNIT_THEME') || 'green')

const themes = [
  { id: 'green',  name: 'Forest Green', color: '#0f6e56' },
  { id: 'navy',   name: 'Navy Blue',    color: '#1e3a5f' },
  { id: 'maroon', name: 'Deep Maroon',  color: '#7c2d12' },
  { id: 'indigo', name: 'Indigo',       color: '#3730a3' },
  { id: 'slate',  name: 'Slate',        color: '#334155' },
  { id: 'teal',   name: 'Teal',         color: '#0d7377' },
]

function setTheme(t) { theme.value = t; localStorage.setItem('KNIT_THEME', t); window.__applyKnitTheme?.(t) }
const initials = computed(() => (auth.username||'').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)||'PK')

// ── Assign Employee Modal ──────────────────────────────────────────────────
const assignModal = ref({
  open: false, jobCard: null, search: '', options: [],
  assigned: [], showDrop: false, error: '', successMsg: '', loading: false, selected: null, cacheEmpty: false
})

async function openAssignModal(jc) {
  assignModal.value = { open: true, jobCard: jc, search: '', options: [],
    assigned: [], showDrop: false, error: '', successMsg: '', loading: false, cacheEmpty: false }
  if (!isOnline.value) {
    // Offline — load current assignment + employee options from cache
    try {
      const sess = await db.rollSessions.get(jc.name)
      if (sess?._assignedName) {
        assignModal.value.assigned = [{ employee: sess._assignedId || '', custom_employee_name: sess._assignedName }]
      }
    } catch(_) {}
    // Preload first page of cached employees so the list isn't blank
    onEmpSearch()
    return
  }
  // Fetch current assignments from time logs
  try {
    const resp = await call('knit_get_job_card_employees', { job_card: jc.name })
    const assigned = resp?.message || []
    assignModal.value.assigned = assigned
    // Cache the current assignment so it displays offline in future sessions
    if (assigned.length) {
      const first = assigned[0]
      await db.rollSessions.put({
        jobCardId: jc.name,
        _hasAssignment: true,
        _assignedId: first.employee || '',
        _assignedName: first.custom_employee_name || first.employee_name || first.employee || '',
        _updatedAt: new Date().toISOString()
      })
    }
  } catch(e) { /* silent */ }
}

function closeAssignModal() { assignModal.value.open = false }

let empTimer = null
async function onEmpSearch() {
  clearTimeout(empTimer)
  empTimer = setTimeout(async () => {
    const q = (assignModal.value.search || '').trim()
    // Offline — search the cached employee directory in IndexedDB
    if (!isOnline.value) {
      try {
        const total = await db.employees.count()
        assignModal.value.cacheEmpty = total === 0
        if (total === 0) { assignModal.value.options = []; return }
        const ql = q.toLowerCase()
        let rows
        if (!ql) {
          rows = await db.employees.limit(20).toArray()
        } else {
          rows = await db.employees
            .filter(e => (e._search || '').includes(ql))
            .limit(20).toArray()
        }
        assignModal.value.options = rows
      } catch(e) {
        console.warn('offline employee search:', e.message)
        assignModal.value.cacheEmpty = true
        assignModal.value.options = []
      }
      return
    }
    try {
      const resp = await call('knit_search_employees', { search: q })
      const results = resp?.message || []
      assignModal.value.options = results
    } catch(e) {
      console.error('Employee search error:', e)
      assignModal.value.options = []
    }
  }, 200)
}

function selectEmp(e) {
  assignModal.value.selected  = e
  assignModal.value.search    = e.employee_name
  assignModal.value.showDrop  = false
  assignModal.value.successMsg = ''
  assignModal.value.error     = ''
}

async function assignEmployee(emp) {
  if (!emp) return
  assignModal.value.loading    = true
  assignModal.value.error      = ''
  assignModal.value.successMsg = ''

  // Offline — queue the assignment and cache it locally so rolling works now
  if (!isOnline.value) {
    try {
      const jobCard = assignModal.value.jobCard.name
      const { enqueue } = await import('@/composables/useSync')
      await enqueue('assignEmployeeToJobCard', 'POST', { job_card: jobCard, employee_id: emp.name })
      // Cache assignment so create-roll's offline check passes
      await db.rollSessions.put({
        jobCardId: jobCard,
        _hasAssignment: true,
        _assignedId: emp.name,
        _assignedName: emp.employee_name,
        _updatedAt: new Date().toISOString()
      })
      assignModal.value.assigned  = [{ employee: emp.name, custom_employee_name: emp.employee_name }]
      assignModal.value.successMsg = `${emp.employee_name} assigned offline — will sync when reconnected`
      assignModal.value.selected  = null
      assignModal.value.search    = ''
    } catch(e) {
      assignModal.value.error = e.message || 'Offline assignment failed'
    } finally {
      assignModal.value.loading = false
    }
    return
  }

  try {
    const resp = await call('knit_assign_employee_to_job_card', {
      job_card: assignModal.value.jobCard.name,
      employee_id: emp.name
    })
    const d = resp?.message || {}
    // Replace assigned list with just the new employee (old ones cleared by server)
    assignModal.value.assigned  = [{ employee: emp.name, custom_employee_name: emp.employee_name }]
    assignModal.value.successMsg = `${d.employee_name} assigned successfully`
    assignModal.value.selected  = null
    assignModal.value.search    = ''
    // Cache assignment state for offline roll creation
    try {
      await db.rollSessions.put({
        jobCardId: assignModal.value.jobCard.name,
        _hasAssignment: true,
        _assignedId: emp.name,
        _assignedName: emp.employee_name,
        _updatedAt: new Date().toISOString()
      })
    } catch(_) {}
  } catch(e) {
    assignModal.value.error = e.message || 'Assignment failed'
  } finally {
    assignModal.value.loading = false
  }
}

onMounted(async () => {
  // Verify real connectivity first (isOnline can be stale after offline
  // toggling), then load. When online, loadJobCards fetches fresh cards AND
  // caches every card's assignment internally, so "Currently assigned" works
  // offline for all cards without opening them.
  await checkReachable()
  await homeStore.loadJobCards(auth.username, auth.designation, auth.employeeId)
  if (isOnline.value) {
    // Warm the employee directory cache for the Assign modal offline
    try {
      const { syncEmployees } = await import('@/api/frappe')
      const res = await syncEmployees()
      const rows = Array.isArray(res) ? res : (res?.data?.data || res?.data || res?.message || [])
      if (rows.length) {
        await db.employees.bulkPut(rows.map(e => ({
          ...e,
          _search: `${e.employee_name || ''} ${e.name || ''} ${e.designation || ''}`.toLowerCase(),
        })))
      }
    } catch (e) { console.warn('employee cache warm-up failed:', e.message) }
  }
})
async function refresh() {
  await checkReachable()
  await homeStore.loadJobCards(auth.username, auth.designation, auth.employeeId)
}
function navigate(path) { drawerOpen.value = false; router.push(path) }

const filtered = computed(() => {
  let cards = homeStore.jobCards
  if (statusFilter.value) cards = cards.filter(c => c.status === statusFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    cards = cards.filter(c => (c.name||'').toLowerCase().includes(q)||(c.work_order||'').toLowerCase().includes(q)||(c.production_item||'').toLowerCase().includes(q)||(c.workstation||'').toLowerCase().includes(q))
  }
  return cards
})

const wipCount  = computed(() => homeStore.jobCards.filter(c => c.status === 'Work In Progress').length)
const openCount = computed(() => homeStore.jobCards.filter(c => c.status === 'Open').length)
const doneCount = computed(() => homeStore.jobCards.filter(c => c.status === 'Completed').length)
function pct(jc) { return jc.for_quantity ? Math.min(100, Math.round(((jc.produced_qty||0)/jc.for_quantity)*100)) : 0 }
async function openCreateRoll(jc) {
  // Offline: skip the server-side assignment check and go straight to
  // create-roll. Rolls are saved locally and synced later by the sync queue.
  if (isOnline.value) {
    try {
      const resp = await call('knit_get_job_card_employees', { job_card: jc.name })
      const assigned = resp?.message || []
      if (!assigned.length) {
        // Show assign modal instead of navigating
        openAssignModal(jc)
        return
      }
      // Cache the assignment result so an immediate offline retry still works
      try { await db.rollSessions.put({ jobCardId: jc.name, _assignedCached: true, _updatedAt: new Date().toISOString() }) } catch(_) {}
    } catch(e) { /* network error — allow navigation */ }
  }
  rollStore.setProductData(jc)
  router.push('/knit-app/create-roll')
}
function createQI(jc) { qiStore.setProductData(jc); router.push('/knit-app/create-qi') }
async function logout() {
  await auth.logout()
  router.push('/knit-app/login')
}
</script>

<style scoped>
.home-page { --primary:#0f6e56; --primary-dark:#0a4a38; --primary-light:#e6f4f0; }
.home-page[data-theme="navy"]   { --primary:#1e3a5f; --primary-dark:#12253d; --primary-light:#e8eef6; }
.home-page[data-theme="maroon"] { --primary:#7c2d12; --primary-dark:#5a1e0a; --primary-light:#fef2ee; }
.home-page[data-theme="indigo"] { --primary:#3730a3; --primary-dark:#2d2880; --primary-light:#eef2ff; }
.home-page[data-theme="slate"]  { --primary:#334155; --primary-dark:#1e293b; --primary-light:#f1f5f9; }
.home-page[data-theme="teal"]   { --primary:#0d7377; --primary-dark:#095558; --primary-light:#e6f4f4; }

.home-page { min-height:100vh; display:flex; flex-direction:column; background:#f8fafc; overflow-x:hidden; width:100%; position:relative; }

/* Drawer */
.drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:200; backdrop-filter:blur(2px); }
.drawer { position:fixed; top:0; left:0; bottom:0; width:280px; background:white; z-index:300; display:flex; flex-direction:column; box-shadow:4px 0 24px rgba(0,0,0,0.15); overflow-y:auto; }
.drawer-header { background:var(--primary); padding:20px 16px; display:flex; align-items:center; gap:12px; flex-shrink:0; }
.drawer-avatar { width:44px; height:44px; border-radius:50%; background:rgba(255,255,255,0.2); color:white; font-size:15px; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.drawer-user { flex:1; min-width:0; }
.drawer-user__name { font-size:14px; font-weight:700; color:white; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.drawer-user__role { font-size:11px; color:rgba(255,255,255,0.75); margin-top:2px; }
.drawer-close { background:rgba(255,255,255,0.15); border:none; color:white; width:30px; height:30px; border-radius:50%; cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.drawer-nav { padding:12px 8px; flex:1; }
.drawer-section-label { font-size:10px; font-weight:700; letter-spacing:0.08em; color:#94a3b8; padding:8px 10px 4px; text-transform:uppercase; }
.drawer-link { width:100%; display:flex; align-items:center; gap:12px; padding:11px 10px; border-radius:10px; border:none; background:none; cursor:pointer; font-size:14px; font-weight:500; color:#334155; text-align:left; transition:background 0.15s,color 0.15s; margin-bottom:2px; font-family:inherit; }
.drawer-link:hover { background:var(--primary-light); color:var(--primary); }
.drawer-link--active { background:var(--primary-light); color:var(--primary); font-weight:700; }
.drawer-link__icon { font-size:18px; width:24px; text-align:center; }
.drawer-themes { padding:8px 16px 12px; }
.theme-grid { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
.theme-btn { width:34px; height:34px; border-radius:50%; border:3px solid transparent; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:transform 0.15s; }
.theme-btn:hover { transform:scale(1.1); }
.theme-btn--active { border-color:#0f172a; transform:scale(1.15); }
.drawer-footer { padding:12px 16px 20px; border-top:1px solid #f1f5f9; }
.drawer-logout { width:100%; display:flex; align-items:center; justify-content:center; gap:8px; padding:11px; border-radius:10px; border:1.5px solid #fee2e2; background:#fff5f5; color:#dc2626; font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; }
.drawer-logout:hover { background:#fee2e2; }
.drawer-slide-enter-active,.drawer-slide-leave-active { transition:transform 0.25s cubic-bezier(0.4,0,0.2,1); }
.drawer-slide-enter-from,.drawer-slide-leave-to { transform:translateX(-100%); }
.overlay-fade-enter-active,.overlay-fade-leave-active { transition:opacity 0.25s; }
.overlay-fade-enter-from,.overlay-fade-leave-to { opacity:0; }

/* Header */
.home-header { background:var(--primary); padding:12px 16px; display:flex; align-items:center; gap:10px; position:sticky; top:0; z-index:100; box-shadow:0 2px 8px rgba(0,0,0,0.15); width:100%; box-sizing:border-box; }
.h-menu-btn { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.2); border-radius:8px; width:38px; height:38px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; cursor:pointer; flex-shrink:0; }
.hamburger { display:block; width:18px; height:2px; background:white; border-radius:2px; }
.home-header__center { flex:1; min-width:0; }
.home-header__title { font-size:17px; font-weight:700; color:white; }
.home-header__sub { font-size:11px; color:rgba(255,255,255,0.75); margin-top:1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.h-icon-btn { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.2); color:white; width:38px; height:38px; border-radius:8px; cursor:pointer; font-size:18px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }

/* Summary */
.home-strips { background:var(--primary); display:flex; gap:8px; padding:0 16px 14px; overflow-x:auto; scrollbar-width:none; width:100%; box-sizing:border-box; }
.home-strips::-webkit-scrollbar { display:none; }
.s-pill { display:flex; flex-direction:column; align-items:center; padding:8px 16px; border-radius:10px; min-width:72px; flex-shrink:0; }
.s-pill--wip   { background:rgba(251,191,36,0.3); }
.s-pill--open  { background:rgba(99,179,237,0.3); }
.s-pill--done  { background:rgba(16,185,129,0.3); }
.s-pill--total { background:rgba(255,255,255,0.15); }
.s-num { font-size:22px; font-weight:800; color:white; line-height:1; font-variant-numeric:tabular-nums; }
.s-lbl { font-size:10px; color:rgba(255,255,255,0.8); font-weight:600; margin-top:3px; text-transform:uppercase; letter-spacing:0.04em; white-space:nowrap; }

/* Toolbar */
.home-toolbar { display:flex; gap:10px; padding:12px 16px; background:white; border-bottom:1px solid #e2e8f0; width:100%; box-sizing:border-box; position:sticky; top:62px; z-index:50; }
.home-search { flex:1; position:relative; min-width:0; }
.home-search__icon { position:absolute; left:10px; top:50%; transform:translateY(-50%); font-size:13px; pointer-events:none; }
.home-search__input { width:100%; padding:9px 12px 9px 32px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:14px; outline:none; background:#f8fafc; box-sizing:border-box; font-family:inherit; }
.home-search__input:focus { border-color:var(--primary); background:white; }
.home-filter { padding:9px 10px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:13px; font-weight:500; background:#f8fafc; outline:none; cursor:pointer; flex-shrink:0; font-family:inherit; }

/* Content */
.home-content { flex:1; padding:16px 16px 80px; width:100%; box-sizing:border-box; overflow-x:hidden; }
.home-loading { display:flex; flex-direction:column; align-items:center; gap:14px; padding:60px; color:#94a3b8; }
.home-spinner { width:32px; height:32px; border:3px solid #e2e8f0; border-top-color:var(--primary); border-radius:50%; animation:spin 0.75s linear infinite; }
.home-empty { display:flex; flex-direction:column; align-items:center; gap:8px; padding:60px 20px; color:#94a3b8; text-align:center; }
.home-empty__title { font-size:15px; font-weight:600; color:#64748b; }
.home-empty__sub { font-size:13px; }

/* Grid */
.jc-grid { display:grid; grid-template-columns:1fr; gap:12px; width:100%; }
@media (min-width:640px)  { .jc-grid { grid-template-columns:repeat(2,1fr); } }
@media (min-width:1024px) { .jc-grid { grid-template-columns:repeat(3,1fr); } }

/* Card */
.jc-card { background:white; border-radius:14px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,0.07); border:1px solid #e2e8f0; border-top:3px solid #e2e8f0; display:flex; flex-direction:column; gap:10px; box-sizing:border-box; width:100%; transition:box-shadow 0.15s,transform 0.15s; }
.jc-card:hover { box-shadow:0 4px 12px rgba(0,0,0,0.1); transform:translateY(-1px); }
.jc-card--warning   { border-top-color:#d97706; }
.jc-card--success   { border-top-color:#047857; }
.jc-card--info      { border-top-color:#2563eb; }
.jc-card--secondary { border-top-color:#94a3b8; }
.jc-card--danger    { border-top-color:#dc2626; }
.jc-top { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
.jc-id  { font-size:14px; font-weight:800; color:#0f172a; letter-spacing:-0.02em; }
.jc-wo  { font-size:12px; color:#94a3b8; font-weight:500; }
.jc-badge { display:inline-flex; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; white-space:nowrap; flex-shrink:0; }
.jc-badge--warning   { background:#fef3c7; color:#d97706; }
.jc-badge--success   { background:#d1fae5; color:#047857; }
.jc-badge--info      { background:#dbeafe; color:#2563eb; }
.jc-badge--secondary { background:#f1f5f9; color:#64748b; }
.jc-badge--danger    { background:#fee2e2; color:#dc2626; }
.jc-details { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.jc-detail  { display:flex; flex-direction:column; gap:2px; min-width:0; }
.jc-detail__l { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#94a3b8; }
.jc-detail__v { font-size:12px; font-weight:600; color:#334155; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jc-detail__side { font-weight:500; color:#64748b; }
.jc-detail__sub { font-size:11px; font-weight:500; color:#64748b; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jc-prog { display:flex; align-items:center; gap:8px; }
.jc-prog__bar { flex:1; height:5px; background:#f1f5f9; border-radius:10px; overflow:hidden; }
.jc-prog__fill { height:100%; background:var(--primary); border-radius:10px; transition:width 0.4s ease; }
.jc-prog__lbl { font-size:11px; font-weight:700; color:#64748b; white-space:nowrap; font-variant-numeric:tabular-nums; }
.jc-actions { display:flex; gap:8px; padding-top:6px; border-top:1px solid #f1f5f9; }
.jc-btn { flex:1; padding:9px 12px; font-size:13px; font-weight:600; border-radius:8px; border:none; cursor:pointer; transition:opacity 0.15s; font-family:inherit; }
.jc-btn:disabled { opacity:0.4; cursor:not-allowed; }
.jc-btn--primary { background:var(--primary); color:white; }
.jc-btn--outline  { background:transparent; border:1.5px solid var(--primary); color:var(--primary); }

/* Bottom nav */
.home-nav { position:fixed; bottom:0; left:0; right:0; height:60px; background:white; border-top:1px solid #e2e8f0; display:flex; z-index:90; box-shadow:0 -2px 12px rgba(0,0,0,0.06); }
.home-nav__item { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:3px; border:none; background:none; cursor:pointer; color:#94a3b8; font-size:10px; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; font-family:inherit; transition:color 0.15s; }
.home-nav__item span:first-child { font-size:20px; }
.home-nav__item--active { color:var(--primary); }
.home-nav__item:hover   { color:var(--primary); }
@media (min-width:1024px) { .home-nav { display:none; } .home-content { padding-bottom:24px; } }
@keyframes spin { to { transform:rotate(360deg); } }

/* Offline banner */
.home-offline-bar { background:#fef3c7; color:#92400e; font-size:12px; font-weight:600; padding:8px 16px; text-align:center; border-bottom:1px solid #fde68a; }
.home-offline-bar--error { background:#fee2e2; color:#991b1b; border-bottom-color:#fecaca; }
.jc-btn--assign { background:rgba(59,130,246,0.1); color:#2563eb; border:none; border-radius:8px;
  padding:0; width:36px; font-size:16px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
.jc-btn--assign:hover { background:rgba(59,130,246,0.2); }

/* Assign modal */
.assign-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:300;
  display:flex; align-items:center; justify-content:center; padding:16px; }
.assign-modal { background:white; border-radius:16px; width:100%; max-width:420px;
  padding:20px 16px; box-shadow:0 16px 48px rgba(0,0,0,0.2); max-height:90vh; overflow-y:auto; }
.assign-modal__hd { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.assign-modal__title { font-size:15px; font-weight:700; color:#0f172a; }
.assign-modal__sub   { font-size:12px; color:#94a3b8; margin-top:2px; }
.assign-modal__close { background:none; border:none; font-size:18px; cursor:pointer; color:#94a3b8; }
.assign-current { margin-bottom:14px; }
.assign-current__label { font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:0.06em; color:#94a3b8; margin-bottom:6px; }
.assign-chips { display:flex; flex-wrap:wrap; gap:6px; }
.assign-chip  { background:#e0f2fe; color:#0369a1; border-radius:20px; padding:4px 12px;
  font-size:12px; font-weight:600; }
.assign-field { margin-bottom:12px; }
.assign-label { display:block; font-size:10px; font-weight:700; text-transform:uppercase;
  letter-spacing:0.06em; color:#94a3b8; margin-bottom:6px; }
.assign-input  { width:100%; padding:10px 14px; border:1.5px solid #e2e8f0; border-radius:10px;
  font-size:14px; font-family:inherit; outline:none; box-sizing:border-box; }
.assign-input:focus { border-color:#0f6e56; }
.assign-results { border:1.5px solid #e2e8f0; border-radius:10px; overflow:hidden; margin-bottom:10px; max-height:200px; overflow-y:auto; }
.assign-result-item { padding:10px 14px; cursor:pointer; border-bottom:1px solid #f1f5f9; }
.assign-result-item:last-child { border-bottom:none; }
.assign-result-item:hover { background:#f0fdf4; }
.assign-dropdown__name { font-size:13px; font-weight:600; color:#0f172a; }
.assign-dropdown__sub  { font-size:11px; color:#94a3b8; margin-top:1px; }
.assign-no-results { font-size:13px; color:#94a3b8; text-align:center; padding:10px; margin-bottom:10px; }
.assign-selected { display:flex; align-items:center; justify-content:space-between;
  background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:10px; padding:10px 12px; margin-bottom:12px; }
.assign-selected__info { display:flex; flex-direction:column; gap:2px; }
.assign-selected__name { font-size:14px; font-weight:700; color:#0f172a; }
.assign-selected__id   { font-size:11px; color:#64748b; }
.assign-selected__clear { background:none; border:none; color:#94a3b8; cursor:pointer; font-size:16px; }
.assign-error   { margin-bottom:10px; color:#dc2626; font-size:13px; }
.assign-success { margin-bottom:10px; color:#16a34a; font-size:13px; font-weight:600; }
.assign-actions { display:flex; gap:8px; margin-top:4px; }
.assign-btn { flex:1; padding:11px; border-radius:10px; border:none; font-size:14px;
  font-weight:600; cursor:pointer; font-family:inherit; transition:opacity 0.15s; }
.assign-btn:disabled { opacity:0.4; cursor:not-allowed; }
.assign-btn--primary { background:#0f6e56; color:white; }
.assign-btn--ghost   { background:#f8fafc; color:#64748b; border:1.5px solid #e2e8f0; }
.assign-spinner { display:inline-block; width:14px; height:14px; border:2px solid rgba(255,255,255,0.35);
  border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; margin-right:6px; }
</style>
