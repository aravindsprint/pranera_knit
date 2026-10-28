import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '@/api/frappe'
import { pageKeyForPath } from '@/pages'
import { usePageAccessStore } from '@/stores/pageAccess'

// ── Eager (statically bundled) imports ──────────────────────────────────────
// These are the pages an operator must be able to reach OFFLINE. Importing them
// statically puts them in the main bundle instead of a lazy-loaded chunk, so
// navigation never has to fetch a module over the network. This is what makes
// offline navigation work in both `npm run dev` and production builds.
import HomePage        from '@/pages/home/HomePage.vue'
import CreateRollPage  from '@/pages/create-roll/CreateRollPage.vue'
import CreateRollsPage from '@/pages/create-rolls/CreateRollsPage.vue'
import CreateQIPage    from '@/pages/create-qi/CreateQIPage.vue'
import RollsPage       from '@/pages/rolls/RollsPage.vue'
import StockEntryPage  from '@/pages/stock-entry/StockEntryPage.vue'
import WorkOrderPage   from '@/pages/work-order/WorkOrderPage.vue'
import LoginPage       from '@/pages/login/LoginPage.vue'

const routes = [
  { path: '/', redirect: '/knit-app/home' },
  { path: '/knit-app', redirect: '/knit-app/home' },

  { path: '/knit-app/login', component: LoginPage },

  // ── Offline-critical (eager) ──
  { path: '/knit-app/home',         component: HomePage },
  { path: '/knit-app/create-roll',  component: CreateRollPage },
  { path: '/knit-app/create-rolls', component: CreateRollsPage },
  { path: '/knit-app/create-qi',    component: CreateQIPage },
  { path: '/knit-app/rolls',        component: RollsPage },
  { path: '/knit-app/stock-entry',  component: StockEntryPage },
  { path: '/knit-app/work-order',   component: WorkOrderPage },

  // ── Online-only reports / dashboards (lazy) ──
  { path: '/knit-app/dashboard', component: () => import('@/pages/dashboard/DashboardPage.vue') },
  { path: '/knit-app/collar-cuff-dashboard', component: () => import('@/pages/collar-cuff-dashboard/CollarCuffDashboardPage.vue') },
  { path: '/knit-app/roll-wise-pick-list', component: () => import('@/pages/roll-wise-pick-list/RollWisePickListPage.vue') },
  { path: '/knit-app/stock', component: () => import('@/pages/stock/StockPage.vue') },
  { path: '/knit-app/vehicle-gate-entry', component: () => import('@/pages/vehicle-gate-entry/VehicleGateEntryPage.vue') },
  { path: '/knit-app/outward-request', component: () => import('@/pages/outward-request/OutwardRequestPage.vue') },
  { path: '/knit-app/my-pick-orders', component: () => import('@/pages/my-pick-orders/MyPickOrdersPage.vue') },
  { path: '/knit-app/roll-wise-pick-order-execution', component: () => import('@/pages/roll-wise-pick-order-execution/RollWisePickOrderExecutionPage.vue') },
  { path: '/knit-app/production-roll-summary', component: () => import('@/pages/production-roll-summary/ProductionRollSummaryPage.vue') },
  { path: '/knit-app/production-report', component: () => import('@/pages/production-report/ProductionReportPage.vue') },
  { path: '/knit-app/process-loss', component: () => import('@/pages/process-loss/ProcessLossPage.vue') },
  { path: '/knit-app/no-access', component: () => import('@/pages/NoAccessPage.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Explicit auth guard: anyone without a real (non-Guest) Frappe session gets
// bounced to /knit-app/login instead of being allowed to sit on a page that
// will just fail its API calls with 403s. Conversely, someone who is already
// logged in is bounced away from the login page itself.
//
// window.__FRAPPE_SESSION__.user is set synchronously in main.js from the
// user_id cookie before the router is created, so this check is safe to run
// on the very first navigation with no async wait.
router.beforeEach(async (to) => {
  const loggedIn = isLoggedIn()
  if (to.path !== '/knit-app/login' && !loggedIn) {
    return { path: '/knit-app/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/knit-app/login' && loggedIn) {
    return { path: '/knit-app/home' }
  }

  // Role-based page access (Desk → Knit App Page). Waits for the access
  // list at most a few seconds; the cached copy covers slow / no network.
  const key = loggedIn && pageKeyForPath(to.path)
  if (key) {
    const access = usePageAccessStore()
    await Promise.race([access.ensureLoaded(), new Promise(r => setTimeout(r, 4000))])
    if (!access.can(key)) {
      // Home is where login and "/" land: send people without Job Cards
      // access to the first page they can open instead of an error.
      const first = access.visiblePages[0]
      if (to.path === '/knit-app/home' && first) return { path: first.path }
      return { path: '/knit-app/no-access', query: { page: key } }
    }
  }
  return true
})

export default router
