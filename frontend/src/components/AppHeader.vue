<template>
  <div>
    <!-- Drawer Overlay -->
    <transition name="overlay-fade">
      <div v-if="drawerOpen" class="ah-overlay" @click="drawerOpen = false"></div>
    </transition>

    <!-- Side Drawer -->
    <transition name="drawer-slide">
      <aside v-if="drawerOpen" class="ah-drawer">
        <div class="ah-drawer-header">
          <div class="ah-avatar">{{ initials }}</div>
          <div class="ah-user">
            <div class="ah-user__name">{{ username || 'User' }}</div>
            <div class="ah-user__role">{{ designation || 'Operator' }}</div>
          </div>
          <button class="ah-close" @click="drawerOpen = false">✕</button>
        </div>

        <nav class="ah-nav">
          <div class="ah-section">PRODUCTION</div>
          <button class="ah-link" :class="{ 'ah-link--active': active === 'work-order' }" @click="go('/knit-app/work-order')">
            <span class="ah-link__icon">📄</span><span>Work Order</span>
          </button>
          <button class="ah-link" :class="{ 'ah-link--active': active === 'home' }" @click="go('/knit-app/home')">
            <span class="ah-link__icon">🗂</span><span>Job Cards</span>
          </button>
          <button class="ah-link" :class="{ 'ah-link--active': active === 'pick-list' }" @click="go('/knit-app/roll-wise-pick-list')">
            <span class="ah-link__icon">📦</span><span>Roll-wise Pick List</span>
          </button>
          
          

          <div class="ah-section" style="margin-top:8px">PRODUCTION DATA</div>
            <button class="ah-link" @click="go('/knit-app/rolls')">
              <span class="ah-link__icon">🧶</span><span>Rolls</span>
            </button>
            <button class="ah-link" @click="go('/knit-app/stock-entry')">
              <span class="ah-link__icon">📦</span><span>Stock Entry</span>
            </button>
          <div class="ah-section" style="margin-top:8px">REPORTS</div>
            <button class="ah-link" @click="go('/knit-app/production-report')">
              <span class="ah-link__icon">📋</span><span>Production Report</span>
            </button>
            <button class="ah-link" @click="go('/knit-app/process-loss')">
              <span class="ah-link__icon">📉</span><span>Process Loss</span>
            </button>
            <div class="ah-section" style="margin-top:8px">ANALYTICS</div>
          <button class="ah-link" :class="{ 'ah-link--active': active === 'dashboard' }" @click="go('/knit-app/dashboard')">
            <span class="ah-link__icon">📈</span><span>Dashboard</span>
          </button>
        </nav>

        <!-- Theme -->
        <div class="ah-themes">
          <div class="ah-section">THEME</div>
          <div class="ah-theme-grid">
            <button
              v-for="t in themes" :key="t.id"
              class="ah-theme-btn"
              :class="{ 'ah-theme-btn--active': currentTheme === t.id }"
              :style="{ background: t.color }"
              @click="setTheme(t.id)"
              :title="t.name"
            ><span v-if="currentTheme === t.id" style="color:white;font-weight:800;font-size:14px">✓</span></button>
          </div>
        </div>

        <!-- Logout -->
        <div class="ah-footer">
          <button class="ah-logout" @click="logout">
            <span>⎋</span><span>Logout</span>
          </button>
        </div>
      </aside>
    </transition>

    <!-- Top bar -->
    <header class="ah-header">
      <button class="ah-menu-btn" @click="drawerOpen = true">
        <span class="ah-ham"></span>
        <span class="ah-ham"></span>
        <span class="ah-ham"></span>
      </button>
      <div class="ah-header__center">
        <div class="ah-header__title">{{ title }}</div>
        <div class="ah-header__sub" v-if="subtitle">{{ subtitle }}</div>
      </div>
      <button v-if="showBack" class="ah-back-btn" @click="$router.back()">←</button>
      <slot name="actions" />
    </header>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  title:    { type: String, default: '' },
  subtitle: { type: String, default: '' },
  username: { type: String, default: '' },
  designation: { type: String, default: '' },
  active:   { type: String, default: '' },
  showBack: { type: Boolean, default: false },
})

const router     = useRouter()
const drawerOpen = ref(false)
const currentTheme = ref(localStorage.getItem('KNIT_THEME') || 'green')

const themes = [
  { id: 'green',  name: 'Forest Green', color: '#0f6e56' },
  { id: 'navy',   name: 'Navy Blue',    color: '#1e3a5f' },
  { id: 'maroon', name: 'Deep Maroon',  color: '#7c2d12' },
  { id: 'indigo', name: 'Indigo',       color: '#3730a3' },
  { id: 'slate',  name: 'Slate',        color: '#334155' },
  { id: 'teal',   name: 'Teal',         color: '#0d7377' },
]

const THEME_COLORS = { green:'#0f6e56', navy:'#1e3a5f', maroon:'#7c2d12', indigo:'#3730a3', slate:'#334155', teal:'#0d7377' }

function setTheme(t) {
  currentTheme.value = t
  localStorage.setItem('KNIT_THEME', t)
  document.documentElement.style.setProperty('--app-primary', THEME_COLORS[t] || '#0f6e56')
  window.__applyKnitTheme?.(t)
}

function go(path) { drawerOpen.value = false; router.push(path) }

const initials = computed(() => (props.username||'').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2)||'PK')

async function logout() {
  localStorage.removeItem('KNIT_USERNAME')
  localStorage.removeItem('KNIT_DESIGNATION')
  localStorage.removeItem('KNIT_EMPLOYEE')
  await fetch('/api/method/frappe.auth.logout', {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': window.__FRAPPE_SESSION__?.csrf_token || '' },
    credentials: 'include'
  }).catch(() => {})
  window.location.href = '/login'
}
</script>

<style scoped>
/* Overlay */
.ah-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:200; backdrop-filter:blur(2px); }

/* Drawer */
.ah-drawer { position:fixed; top:0; left:0; bottom:0; width:280px; background:white; z-index:300; display:flex; flex-direction:column; box-shadow:4px 0 24px rgba(0,0,0,0.15); overflow-y:auto; }
.ah-drawer-header { background:var(--app-primary,#0f6e56); padding:20px 16px; display:flex; align-items:center; gap:12px; flex-shrink:0; }
.ah-avatar { width:44px; height:44px; border-radius:50%; background:rgba(255,255,255,0.2); color:white; font-size:15px; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.ah-user { flex:1; min-width:0; }
.ah-user__name { font-size:14px; font-weight:700; color:white; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ah-user__role { font-size:11px; color:rgba(255,255,255,0.75); margin-top:2px; }
.ah-close { background:rgba(255,255,255,0.15); border:none; color:white; width:30px; height:30px; border-radius:50%; cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }

.ah-nav { padding:12px 8px; flex:1; }
.ah-section { font-size:10px; font-weight:700; letter-spacing:0.08em; color:#94a3b8; padding:8px 10px 4px; text-transform:uppercase; }
.ah-link { width:100%; display:flex; align-items:center; gap:12px; padding:11px 10px; border-radius:10px; border:none; background:none; cursor:pointer; font-size:14px; font-weight:500; color:#334155; text-align:left; transition:background 0.15s,color 0.15s; margin-bottom:2px; font-family:inherit; }
.ah-link:hover { background:rgba(0,0,0,0.05); }
.ah-link--active { background:rgba(15,110,86,0.1); color:var(--app-primary,#0f6e56); font-weight:700; }
.ah-link__icon { font-size:18px; width:24px; text-align:center; }

.ah-themes { padding:8px 16px 12px; }
.ah-theme-grid { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }
.ah-theme-btn { width:34px; height:34px; border-radius:50%; border:3px solid transparent; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:transform 0.15s; }
.ah-theme-btn:hover { transform:scale(1.1); }
.ah-theme-btn--active { border-color:#0f172a; transform:scale(1.15); }

.ah-footer { padding:12px 16px 20px; border-top:1px solid #f1f5f9; }
.ah-logout { width:100%; display:flex; align-items:center; justify-content:center; gap:8px; padding:11px; border-radius:10px; border:1.5px solid #fee2e2; background:#fff5f5; color:#dc2626; font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; }
.ah-logout:hover { background:#fee2e2; }

/* Transitions */
.drawer-slide-enter-active,.drawer-slide-leave-active { transition:transform 0.25s cubic-bezier(0.4,0,0.2,1); }
.drawer-slide-enter-from,.drawer-slide-leave-to { transform:translateX(-100%); }
.overlay-fade-enter-active,.overlay-fade-leave-active { transition:opacity 0.25s; }
.overlay-fade-enter-from,.overlay-fade-leave-to { opacity:0; }

/* Top header bar */
.ah-header { background:var(--app-primary,#0f6e56); padding:0 16px; height:60px; display:flex; align-items:center; gap:10px; position:sticky; top:0; z-index:100; box-shadow:0 2px 8px rgba(0,0,0,0.15); width:100%; box-sizing:border-box; }
.ah-menu-btn { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.2); border-radius:8px; width:38px; height:38px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; cursor:pointer; flex-shrink:0; }
.ah-ham { display:block; width:18px; height:2px; background:white; border-radius:2px; }
.ah-header__center { flex:1; min-width:0; }
.ah-header__title { font-size:17px; font-weight:700; color:white; }
.ah-header__sub { font-size:11px; color:rgba(255,255,255,0.75); margin-top:1px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ah-back-btn { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.2); color:white; width:38px; height:38px; border-radius:8px; cursor:pointer; font-size:18px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
</style>
