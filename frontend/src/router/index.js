import { createRouter, createWebHistory } from 'vue-router'

// ── Eager (statically bundled) imports ──────────────────────────────────────
// These are the pages an operator must be able to reach OFFLINE. Importing them
// statically puts them in the main bundle instead of a lazy-loaded chunk, so
// navigation never has to fetch a module over the network. This is what makes
// offline navigation work in both `npm run dev` and production builds.
import HomePage       from '@/pages/home/HomePage.vue'
import CreateRollPage from '@/pages/create-roll/CreateRollPage.vue'
import CreateQIPage   from '@/pages/create-qi/CreateQIPage.vue'
import RollsPage      from '@/pages/rolls/RollsPage.vue'
import StockEntryPage from '@/pages/stock-entry/StockEntryPage.vue'
import WorkOrderPage  from '@/pages/work-order/WorkOrderPage.vue'

const routes = [
  { path: '/', redirect: '/knit-app/home' },
  { path: '/knit-app', redirect: '/knit-app/home' },

  // ── Offline-critical (eager) ──
  { path: '/knit-app/home',        component: HomePage },
  { path: '/knit-app/create-roll', component: CreateRollPage },
  { path: '/knit-app/create-qi',   component: CreateQIPage },
  { path: '/knit-app/rolls',       component: RollsPage },
  { path: '/knit-app/stock-entry', component: StockEntryPage },
  { path: '/knit-app/work-order',  component: WorkOrderPage },

  // ── Online-only reports / dashboards (lazy) ──
  { path: '/knit-app/dashboard', component: () => import('@/pages/dashboard/DashboardPage.vue') },
  { path: '/knit-app/collar-cuff-dashboard', component: () => import('@/pages/collar-cuff-dashboard/CollarCuffDashboardPage.vue') },
  { path: '/knit-app/roll-wise-pick-list', component: () => import('@/pages/roll-wise-pick-list/RollWisePickListPage.vue') },
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

export default router
