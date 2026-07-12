<template>
  <div id="app">
    <!-- Offline banner -->
    <transition name="banner">
      <div v-if="!isOnline" class="status-banner status-banner--offline">
        <span class="status-banner__icon">⚡</span>
        <span>Offline — changes will sync when reconnected</span>
        <span v-if="pendingCount > 0" class="status-banner__pill">{{ pendingCount }} pending</span>
      </div>
    </transition>

    <!-- Sync banner -->
    <transition name="banner">
      <div v-if="isOnline && isSyncing" class="status-banner status-banner--sync">
        <span class="status-banner__spinner"></span>
        <span>Syncing with ERPNext…</span>
      </div>
    </transition>

    <router-view />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSync, isOnline, isSyncing, pendingCount } from '@/composables/useSync'
import { initCSRF, isLoggedIn } from '@/api/frappe'
useSync()

const THEME_COLORS = {
  green:  '#0f6e56',
  navy:   '#1e3a5f',
  maroon: '#7c2d12',
  indigo: '#3730a3',
  slate:  '#334155',
  teal:   '#0d7377',
}

function applyTheme(t) {
  const color = THEME_COLORS[t] || THEME_COLORS.green
  document.documentElement.style.setProperty('--app-primary', color)
}

const auth = useAuthStore()
onMounted(async () => {
  await initCSRF()
  auth.refreshSession()
  if (isLoggedIn()) {
    await auth.loadEmployeeDetails()
  }
  const saved = localStorage.getItem('KNIT_THEME') || 'green'
  applyTheme(saved)
})

// Watch for theme changes from other tabs or components
window.addEventListener('storage', (e) => {
  if (e.key === 'KNIT_THEME') applyTheme(e.newValue || 'green')
})

// Expose for HomePage to call after setting theme
window.__applyKnitTheme = applyTheme
</script>

<style>
/* ── Design tokens ─────────────────────────────────────────────────────────── */
:root {
  --green-900: #0a4a38;
  --green-700: #0f6e56;
  --green-600: #138a6a;
  --green-100: #e6f4f0;
  --green-50:  #f0faf7;

  --slate-900: #0f172a;
  --slate-700: #334155;
  --slate-500: #64748b;
  --slate-400: #94a3b8;
  --slate-200: #e2e8f0;
  --slate-100: #f1f5f9;
  --slate-50:  #f8fafc;

  --amber-600: #d97706;
  --amber-100: #fef3c7;
  --red-600:   #dc2626;
  --red-100:   #fee2e2;
  --blue-600:  #2563eb;
  --blue-100:  #dbeafe;
  --emerald-700: #047857;
  --emerald-100: #d1fae5;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 20px;

  --shadow-sm: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 30px rgba(0,0,0,0.12);

  --font-sans: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;

  --header-h: 60px;
}

/* ── Reset ─────────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: var(--font-sans);
  background: var(--slate-50);
  color: var(--slate-900);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
button { font-family: inherit; cursor: pointer; }
input, select, textarea { font-family: inherit; }
#app { min-height: 100vh; }

/* ── Status banners ────────────────────────────────────────────────────────── */
.status-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
}
.status-banner--offline { background: var(--red-600); color: #fff; }
.status-banner--sync    { background: var(--green-700); color: #fff; }
.status-banner__pill {
  background: rgba(255,255,255,0.25);
  border-radius: 20px;
  padding: 1px 10px;
  font-size: 11px;
  font-weight: 600;
}
.status-banner__spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

/* ── Page shell ────────────────────────────────────────────────────────────── */
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--slate-50);
}

/* ── Header ────────────────────────────────────────────────────────────────── */
.page-header {
  min-height: var(--header-h);
  background: var(--green-700);
  color: white;
  padding: 0 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  overflow: visible;
}
.page-header h1 {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.01em;
  flex: 1;
}
.page-header__sub {
  font-size: 11px;
  opacity: 0.8;
  font-weight: 400;
  margin-top: 1px;
}

/* ── Icon buttons ──────────────────────────────────────────────────────────── */
.icon-btn {
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2);
  color: white;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
  transition: background 0.15s;
}
.icon-btn:hover { background: rgba(255,255,255,0.25); }
.icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Content area ──────────────────────────────────────────────────────────── */
.page-content {
  flex: 1;
  padding: 16px;
  max-width: 720px;
  width: 100%;
  margin: 0 auto;
}

/* Desktop: wider content */
@media (min-width: 1024px) {
  .page-content { padding: 24px 32px; max-width: 900px; }
}

/* ── Card ──────────────────────────────────────────────────────────────────── */
.card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--slate-200);
}

/* ── Badges ────────────────────────────────────────────────────────────────── */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  white-space: nowrap;
}
.badge-success   { background: var(--emerald-100); color: var(--emerald-700); }
.badge-warning   { background: var(--amber-100);   color: var(--amber-600); }
.badge-danger    { background: var(--red-100);     color: var(--red-600); }
.badge-info      { background: var(--blue-100);    color: var(--blue-600); }
.badge-secondary { background: var(--slate-100);   color: var(--slate-500); }

/* ── Buttons ───────────────────────────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 20px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  white-space: nowrap;
  letter-spacing: 0.01em;
}
.btn:active  { transform: scale(0.97); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
.btn-primary { background: var(--green-700); color: white; }
.btn-primary:hover:not(:disabled) { background: var(--green-600); }
.btn-danger  { background: var(--red-600); color: white; }
.btn-warning { background: var(--amber-600); color: white; }
.btn-outline {
  background: transparent;
  border: 1.5px solid var(--green-700);
  color: var(--green-700);
}
.btn-outline:hover:not(:disabled) { background: var(--green-50); }
.btn-ghost {
  background: var(--slate-100);
  color: var(--slate-700);
  border: none;
}
.btn-full { width: 100%; }
.btn-lg { padding: 14px 24px; font-size: 15px; border-radius: var(--radius-md); }

/* ── Form elements ─────────────────────────────────────────────────────────── */
.form-group { margin-bottom: 16px; }
.form-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: var(--slate-500);
  margin-bottom: 5px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.form-input {
  width: 100%;
  padding: 11px 13px;
  border: 1.5px solid var(--slate-200);
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--slate-900);
  background: white;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  -webkit-appearance: none;
}
.form-input:focus {
  border-color: var(--green-700);
  box-shadow: 0 0 0 3px rgba(15,110,86,0.1);
}
.form-input::placeholder { color: var(--slate-400); }

/* ── Alert boxes ───────────────────────────────────────────────────────────── */
.alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 12px;
}
.alert-error   { background: var(--red-100);     color: var(--red-600); }
.alert-warning { background: var(--amber-100);   color: var(--amber-600); }
.alert-success { background: var(--emerald-100); color: var(--emerald-700); }
.alert-info    { background: var(--blue-100);    color: var(--blue-600); }

/* Aliases for backward compat */
.error-box {
  display: flex; align-items: center; gap: 8px;
  padding: 11px 14px; border-radius: var(--radius-md);
  font-size: 13px; font-weight: 500; margin-bottom: 12px;
  background: var(--red-100); color: var(--red-600);
}

/* ── Section title ─────────────────────────────────────────────────────────── */
.section-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--slate-700);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--slate-100);
  letter-spacing: -0.01em;
}

/* ── Divider ───────────────────────────────────────────────────────────────── */
.divider { height: 1px; background: var(--slate-100); margin: 14px 0; }

/* ── Loading / Empty states ────────────────────────────────────────────────── */
.loading-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 60px 20px;
  color: var(--slate-400);
}
.spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--slate-200);
  border-top-color: var(--green-700);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 60px 20px;
  color: var(--slate-400);
  text-align: center;
}
.empty-state__icon { font-size: 40px; opacity: 0.4; }
.empty-state__title { font-size: 15px; font-weight: 600; color: var(--slate-500); }
.empty-state__sub { font-size: 13px; }

/* ── Animations ────────────────────────────────────────────────────────────── */
@keyframes spin { to { transform: rotate(360deg); } }
.banner-enter-active, .banner-leave-active { transition: all 0.25s; }
.banner-enter-from, .banner-leave-to { opacity: 0; transform: translateY(-8px); }

/* ── Responsive grid helpers ───────────────────────────────────────────────── */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
@media (max-width: 480px) {
  .grid-3 { grid-template-columns: 1fr 1fr; }
}

/* ── Tablet: side by side layout for cards ─────────────────────────────────── */
@media (min-width: 768px) {
  .page-content { padding: 20px 24px; }
  .card { padding: 20px; }
}
</style>

<style>
html, body, #app { overflow-x: hidden; max-width: 100vw; }
</style>

<style>
:root { --app-primary: #0f6e56; }
.page-header { background: var(--app-primary) !important; }
.btn-primary  { background: var(--app-primary) !important; }
.home-header  { background: var(--app-primary) !important; }
.home-strips  { background: var(--app-primary) !important; }
.drawer-header { background: var(--app-primary) !important; }
.timer-card   { background: linear-gradient(135deg, color-mix(in srgb, var(--app-primary) 70%, black) 0%, var(--app-primary) 100%) !important; }
</style>
