// Every Knit App page reachable from the side menu, in menu order.
// `key` must match pranera_knit/page_access.py PAGES — it's what the
// "Knit App Page" records in Desk restrict by role.
export const PAGES = [
  { key: 'work-order',          label: 'Work Order',          icon: '📄', path: '/knit-app/work-order',          section: 'PRODUCTION' },
  { key: 'home',                label: 'Job Cards',           icon: '🗂', path: '/knit-app/home',                section: 'PRODUCTION' },
  { key: 'roll-wise-pick-list', label: 'Roll-wise Pick List', icon: '📦', path: '/knit-app/roll-wise-pick-list', section: 'PRODUCTION', active: ['pick-list'] },
  { key: 'my-pick-orders',      label: 'My Pick Orders',      icon: '✅', path: '/knit-app/my-pick-orders',      section: 'PRODUCTION', active: ['pick-execution'] },
  { key: 'outward-request',     label: 'Outward Request',     icon: '🚚', path: '/knit-app/outward-request',     section: 'PRODUCTION' },
  { key: 'vehicle-gate-entry',  label: 'Vehicle Gate Entry',  icon: '🚛', path: '/knit-app/vehicle-gate-entry',  section: 'PRODUCTION' },
  { key: 'create-rolls',        label: 'Create Rolls',        icon: '✂️', path: '/knit-app/create-rolls',        section: 'PRODUCTION DATA' },
  { key: 'rolls',               label: 'Rolls',               icon: '🧶', path: '/knit-app/rolls',               section: 'PRODUCTION DATA' },
  { key: 'stock',               label: 'Stock',               icon: '🏷️', path: '/knit-app/stock',               section: 'PRODUCTION DATA' },
  { key: 'stock-entry',         label: 'Stock Entry',         icon: '📦', path: '/knit-app/stock-entry',         section: 'PRODUCTION DATA' },
  { key: 'production-report',   label: 'Production Report',   icon: '📋', path: '/knit-app/production-report',   section: 'REPORTS' },
  { key: 'process-loss',        label: 'Process Loss',        icon: '📉', path: '/knit-app/process-loss',        section: 'REPORTS' },
  { key: 'dashboard',           label: 'Dashboard',           icon: '📈', path: '/knit-app/dashboard',           section: 'ANALYTICS' },
]

// Screens opened from inside another page follow that page's access.
export const SUB_PAGES = {
  '/knit-app/create-roll': 'home',
  '/knit-app/create-qi': 'home',
  '/knit-app/roll-wise-pick-order-execution': 'my-pick-orders',
  '/knit-app/collar-cuff-dashboard': 'dashboard',
  '/knit-app/production-roll-summary': 'production-report',
}

export function pageKeyForPath(path) {
  const page = PAGES.find(p => p.path === path)
  return page ? page.key : SUB_PAGES[path] || null
}

// [{ section, pages: [...] }] for the given visible pages.
export function groupBySection(pages) {
  const groups = []
  for (const p of pages) {
    const last = groups[groups.length - 1]
    if (last && last.section === p.section) last.pages.push(p)
    else groups.push({ section: p.section, pages: [p] })
  }
  return groups
}
