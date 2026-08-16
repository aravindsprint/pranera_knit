// ── CSRF ──────────────────────────────────────────────────────────────────
let _csrf = ''

function getCookieValue(name) {
  return document.cookie
    .split('; ')
    .find(r => r.startsWith(name + '='))
    ?.split('=')[1] || ''
}

export async function ensureCSRF() {
  // 1. Already cached
  if (_csrf) return _csrf
  // 2. Injected by Jinja (production)
  if (window.csrf_token) { _csrf = window.csrf_token; return _csrf }
  // 3. Cookie fallback
  const cookie = getCookieValue('csrftoken') || getCookieValue('X-Frappe-CSRF-Token')
  if (cookie) { _csrf = cookie; return _csrf }
  // 4. Fetch from Server Script (dev proxy)
  try {
    const r = await fetch('/api/method/knit_get_csrf', { credentials: 'include' })
    if (r.ok) {
      const d = await r.json()
      if (d?.message) { _csrf = d.message; window.csrf_token = d.message }
      else console.warn('ensureCSRF: knit_get_csrf returned no token (no session/sid cookie?)')
    } else {
      console.warn('ensureCSRF: knit_get_csrf HTTP', r.status)
    }
  } catch(e) {
    console.warn('ensureCSRF: knit_get_csrf failed', e)
  }
  return _csrf
}

// Forget the cached CSRF token so the next ensureCSRF() call re-fetches it.
// Required after login/logout, since both actions issue a brand new session
// (and therefore a brand new token) — reusing the old one causes silent
// CSRFTokenError 403s on the very next authenticated request.
export function resetCSRF() {
  _csrf = ''
  window.csrf_token = ''
}

export async function initCSRF() {
  window.__FRAPPE_SESSION__ = {
    user: decodeURIComponent(getCookieValue('user_id') || '') || 'Guest',
    base_url: ''
  }
  // Pre-warm the token so first API call doesn't need to fetch it
  await ensureCSRF()
  // Keep csrf_token on the session object too — logout()/other callers read
  // it from here, and previously this field was silently dropped because
  // this function replaces window.__FRAPPE_SESSION__ wholesale.
  window.__FRAPPE_SESSION__.csrf_token = _csrf
  console.log('Session user:', window.__FRAPPE_SESSION__.user, '| CSRF:', _csrf ? '✓' : '✗')
}

// True once we've established the browser holds a real (non-Guest) Frappe
// session. Call initCSRF() first so window.__FRAPPE_SESSION__ is current.
export function isLoggedIn() {
  const user = window.__FRAPPE_SESSION__?.user
  return !!user && user !== 'Guest'
}

// ── Core fetch helpers ────────────────────────────────────────────────────
export async function call(method, args = {}) {
  const token = await ensureCSRF()
  const body = new URLSearchParams()
  for (const [k, v] of Object.entries(args)) {
    body.append(k, typeof v === 'object' ? JSON.stringify(v) : v)
  }
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Frappe-CSRF-Token': token
    },
    body: body.toString(),
    credentials: 'include'
  })
  const data = await res.json()
  if (!res.ok || data.exc) throw new Error(extractServerError(data, res.statusText))
  return data
}

// Turn Frappe's error payload into a short human-readable message
// instead of dumping the entire Python traceback into the UI.
function extractServerError(data, fallback = 'Request failed') {
  // 1. _server_messages: JSON array of JSON strings, last one is most relevant
  try {
    const msgs = JSON.parse(data._server_messages || '[]')
    if (msgs.length) {
      const last = JSON.parse(msgs[msgs.length - 1])
      const text = String(last.message || last)
        .replace(/<[^>]+>/g, '')   // strip HTML tags
        .trim()
      if (text) return text
    }
  } catch { /* fall through */ }
  // 2. data.exception: "module.path.ErrorClass: message" — keep the message part
  if (data.exception) {
    const parts = String(data.exception).split(':')
    return (parts.length > 1 ? parts.slice(1).join(':') : parts[0]).trim()
  }
  // 3. Last line of the traceback, if that's all we have
  if (data.exc) {
    try {
      const tb = JSON.parse(data.exc)
      const lines = String(tb[0] || '').trim().split('\n')
      return lines[lines.length - 1].trim()
    } catch { /* fall through */ }
  }
  return fallback
}

export async function getList(doctype, { filters = [], orFilters = [], fields = ['name'], limit = 200, orderBy } = {}) {
  const params = new URLSearchParams({
    filters: JSON.stringify(filters),
    fields: JSON.stringify(fields),
    limit_page_length: limit,
    ...(orFilters && orFilters.length ? { or_filters: JSON.stringify(orFilters) } : {}),
    ...(orderBy ? { order_by: orderBy } : {})
  })
  const res = await fetch(`/api/resource/${encodeURIComponent(doctype)}?${params}`, {
    credentials: 'include'
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.exc || res.statusText)
  return data.data || []
}

// Paginated variant of getList — fetches EVERY matching row, not just the
// first page. Frappe's REST list endpoint silently truncates at whatever
// limit_page_length you pass, and with no explicit order_by it sorts by
// "modified desc" across the WHOLE doctype (not just this app's records) —
// so a plain single-request limit can drop rows in an unpredictable way
// (e.g. an entire warehouse building missing from the dropdown because its
// records happen to be older than 500 other, unrelated warehouses site-wide).
// Pages through with limit_start until a page comes back short.
export async function getAllList(doctype, { filters = [], orFilters = [], fields = ['name'], pageSize = 500, orderBy = 'name asc', maxPages = 40 } = {}) {
  const all = []
  let start = 0
  for (let page = 0; page < maxPages; page++) {
    const params = new URLSearchParams({
      filters: JSON.stringify(filters),
      fields: JSON.stringify(fields),
      limit_page_length: pageSize,
      limit_start: start,
      order_by: orderBy,
      ...(orFilters && orFilters.length ? { or_filters: JSON.stringify(orFilters) } : {})
    })
    const res = await fetch(`/api/resource/${encodeURIComponent(doctype)}?${params}`, {
      credentials: 'include'
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.exc || res.statusText)
    const rows = data.data || []
    all.push(...rows)
    if (rows.length < pageSize) break // last page reached
    start += pageSize
  }
  return all
}

export async function getDoc(doctype, name) {
  const res = await fetch(
    `/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    { credentials: 'include' }
  )
  const data = await res.json()
  if (!res.ok) throw new Error(data.exc || res.statusText)
  return data.data
}

export async function createDoc(doctype, doc) {
  const token = await ensureCSRF()
  const res = await fetch(`/api/resource/${encodeURIComponent(doctype)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token },
    body: JSON.stringify(doc),
    credentials: 'include'
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.exc || res.statusText)
  return data.data
}

export async function updateDoc(doctype, name, doc) {
  const token = await ensureCSRF()
  const res = await fetch(
    `/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token },
      body: JSON.stringify(doc),
      credentials: 'include'
    }
  )
  const data = await res.json()
  if (!res.ok) throw new Error(data.exc || res.statusText)
  return data.data
}

// ── Domain helpers ────────────────────────────────────────────────────────
export const getEmployeeDetails = (username) =>
  getList('Employee', {
    filters: [['Employee', 'user_id', '=', username]],
    fields: ['*'],
    limit: 1
  })

export const fetchJobCards = (username, designation, employeeId) => {
  const filters = [['Job Card', 'docstatus', '!=', 2]]
  if (designation === 'Knitting Operator' || designation === 'Senior Knitting Operator') {
    // Filter by employee ID (e.g. E254) in time logs — set when supervisor assigns
    const empFilter = employeeId || username
    filters.push(['Job Card Time Log', 'employee', '=', empFilter])
  }
  return getList('Job Card', {
    filters,
    fields: [
      'name', 'work_order', 'production_item', 'item_name',
      'commercial_name', 'color', 'width',
      'status', 'workstation', 'for_quantity',
      'total_completed_qty as produced_qty',
      'project', 'docstatus', 'quality_inspection', 'stock_uom'
    ],
    limit: 500,
    orderBy: 'modified desc'
  })
}

// Fetch current employee assignments (from Job Card Time Log) for a set of
// job cards in ONE query. Returns a map: { [jobCardName]: {employee, custom_employee_name} }.
// Kept separate from fetchJobCards so it can never distort the main list.
// Work orders with item, qty, and job card count (via knit_get_work_orders
// Server Script). Returns [{name, production_item, item_name, qty,
// produced_qty, status, job_card_count}].
export async function fetchWorkOrders() {
  const resp = await call('knit_get_work_orders', {})
  return resp?.message || []
}

export async function fetchJobCardAssignments(jobCardNames = []) {
  if (!jobCardNames.length) return {}
  // Uses the knit_get_job_card_assignments Server Script — child-table
  // (Job Card Time Log) rows can't be listed via /api/resource, so we query
  // server-side. Returns [{job_card, employee, custom_employee_name}].
  const resp = await call('knit_get_job_card_assignments', { job_cards: jobCardNames })
  const rows = resp?.message || []
  const map = {}
  for (const r of rows) {
    if (r.job_card && !map[r.job_card]) {
      map[r.job_card] = { employee: r.employee, custom_employee_name: r.custom_employee_name }
    }
  }
  return map
}

export const createRollInERP         = (data) => createDoc('Roll', data)
export const createQualityInspection = (data) => createDoc('Quality Inspection', data)

export const getQIParameters = () =>
  getList('Quality Inspection Parameter', { filters: [], fields: ['*'] })

export const startJobCard = (jobCardId) =>
  call('frappe.client.set_value', {
    doctype: 'Job Card', name: jobCardId,
    fieldname: 'status', value: 'Work In Progress'
  })

export const createPickingEntry    = (data) => call('pranera_knit.api.knit.create_roll_picking_entry', data)
export const submitRollPackingList = (jobcard, work_order) =>
  call('pranera_knit.api.knit.submit_roll_packing_list', { jobcard, work_order })

export const syncItems = () =>
  getAllList('Item', {
    filters: [['Item', 'disabled', '=', 0]],
    fields: ['name', 'item_code', 'item_name', 'stock_uom', 'quality_inspection_template', 'has_batch_no', 'modified'],
    pageSize: 500
  })

export const syncWorkOrders = () =>
  getAllList('Work Order', {
    filters: [['Work Order', 'docstatus', '!=', 2]],
    fields: ['name', 'production_item', 'item_name', 'status', 'qty', 'produced_qty', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })

export const syncBatches    = () => getAllList('Batch',     { fields: ['name', 'item', 'expiry_date', 'modified'], pageSize: 500, orderBy: 'modified desc' })
export const syncWarehouses = () => getAllList('Warehouse', { fields: ['name', 'warehouse_name', 'modified'],      pageSize: 500, orderBy: 'name asc' })

// Stock Entries (parent doctype — listable via /api/resource)
export const syncStockEntries = () =>
  getAllList('Stock Entry', {
    filters: [['Stock Entry', 'docstatus', '=', 1]],
    fields: ['name', 'purpose', 'stock_entry_type', 'work_order', 'posting_date', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })

// Purchase Orders / Subcontracting Orders — used by the Roll-wise Pick List's
// "From Purchase Order" / "To|From Subcontracting Order" pick types. These were
// missing entirely before, so those pick types always showed "No matches".
export const syncPurchaseOrders = () =>
  getAllList('Purchase Order', {
    filters: [['Purchase Order', 'docstatus', '!=', 2]],
    fields: ['name', 'supplier', 'status', 'transaction_date', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })

export const syncSubcontractingOrders = () =>
  getAllList('Subcontracting Order', {
    filters: [['Subcontracting Order', 'docstatus', '!=', 2]],
    fields: ['name', 'supplier', 'status', 'transaction_date', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })

// Time Logs: Job Card Time Log is a CHILD table (not listable via /api/resource),
// so cache the parent Job Cards' timing instead. Kept lightweight; these caches
// aren't consumed by any offline feature yet, so this just prevents sync errors.
export const syncTimeLogs = () =>
  getAllList('Job Card', {
    filters: [['Job Card', 'docstatus', '=', 1]],
    fields: ['name', 'employee', 'actual_start_date as from_time', 'total_time_in_mins', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })
export const syncJobCards   = () =>
  getAllList('Job Card', {
    filters: [['Job Card', 'docstatus', '!=', 2]],
    fields: ['name', 'work_order', 'production_item', 'item_name', 'status', 'workstation', 'modified'],
    pageSize: 500,
    orderBy: 'modified desc'
  })
export const syncQIParameters = () => getAllList('Quality Inspection Parameter', { fields: ['*'], pageSize: 500 })

// Cache the active employee directory for offline assignment
export const syncEmployees = () =>
  getAllList('Employee', {
    filters: [['Employee', 'status', '=', 'Active']],
    fields: ['name', 'employee_name', 'designation', 'user_id', 'modified'],
    pageSize: 500
  })


export const getWorkOrderDetails           = (name) => getDoc('Work Order',           name)
export const getPurchaseOrderDetails       = (name) => getDoc('Purchase Order',        name)
export const getSubcontractingOrderDetails = (name) => getDoc('Subcontracting Order',  name)
export const getStockEntryDetails          = (name) => getDoc('Stock Entry',           name)
export const getBatchDetails               = (name) => getDoc('Batch',                 name)

// Batches for a project (optionally scoped to a work order), matching the
// "{project}/{workOrder}/{job_card}" batch_id naming convention used across
// the whole app (mirrors Node's /api/getBatchesForProject exactly).
export async function getBatchesForProject(project, workOrder) {
  const pattern = workOrder ? `${project}/${workOrder}/%` : `${project}/%`
  const rows = await getList('Batch', {
    filters: [['Batch', 'batch_id', 'like', pattern]],
    fields: ['name', 'batch_id', 'item', 'batch_qty', 'stock_uom'],
    limit: 500
  })
  // Extra client-side safety filter — same double-check the Node endpoint does.
  const expectedPrefix = workOrder ? `${project}/${workOrder}/` : `${project}/`
  return rows
    .filter(b => (b.batch_id || b.name || '').startsWith(expectedPrefix))
    .map(b => ({
      name: b.name,
      batch_id: b.batch_id || b.name,
      item: b.item,
      item_code: b.item,
      batch_qty: b.batch_qty,
      stock_uom: b.stock_uom
    }))
}

// Rolls for a given batch — live query against ERPNext's Roll doctype
// (not a stale local cache), matching the fix applied to Node's
// /api/getRollsForBatch.
export const getRollsForBatch = (batchName) =>
  getList('Roll', {
    filters: [
      ['Roll', 'batch', '=', batchName],
      ['Roll', 'docstatus', '!=', 2]
    ],
    fields: ['name', 'roll_no', 'item_code', 'batch', 'roll_weight', 'total_qty', 'stock_uom'],
    limit: 1000
  }).then(rows => rows.map(r => ({
    roll_no: r.roll_no || r.name,
    item_code: r.item_code || '',
    batch: r.batch || batchName,
    roll_weight: (r.stock_uom || '').toLowerCase() === 'pcs' ? (r.total_qty || 0) : (r.roll_weight || 0),
    stock_uom: r.stock_uom || 'Kg'
  })))

// Rolls for a given job card — used to filter the roll dropdown when a
// Job Card is selected on the Roll-wise Pick List page.
export const getRollsForJobCard = (jobCardName) =>
  getList('Roll', {
    filters: [['Roll', 'job_card', '=', jobCardName]],
    fields: ['name', 'roll_no', 'item_code', 'item_name', 'batch', 'roll_weight', 'total_qty', 'stock_uom'],
    limit: 1000
  }).then(rows => rows.map(r => ({
    roll_no: r.roll_no || r.name,
    job_card: jobCardName,
    item_code: r.item_code,
    item_name: r.item_name,
    batch_no: r.batch,
    qty: (r.stock_uom || '').toLowerCase() === 'pcs' ? (r.total_qty || 0) : (r.roll_weight || 0),
    uom: r.stock_uom || 'Kg'
  })))

// Submitted Job Cards for a work order — populates the (optional) Job Card
// filter on the Roll-wise Pick List page.
export const getJobCardsForWorkOrder = (workOrderName) =>
  getList('Job Card', {
    filters: [
      ['Job Card', 'work_order', '=', workOrderName],
      ['Job Card', 'docstatus', '=', 1]
    ],
    fields: ['name', 'work_order', 'production_item', 'item_name', 'status'],
    limit: 500,
    orderBy: 'creation asc'
  })

// Find a Roll doc by its roll_no field (roll_no is not always the same as
// the document name), used when a barcode is scanned or a roll no is typed.
export const findRollByRollNo = (rollNo) =>
  getList('Roll', {
    filters: [['Roll', 'roll_no', '=', rollNo]],
    fields: ['name', 'roll_no', 'item_code', 'batch', 'roll_weight', 'total_qty', 'stock_uom'],
    limit: 1
  }).then(rows => rows[0] || null)

// Recent rolls — used by the "Manual Roll Pick" pick type, which lets the
// user search any roll directly without first picking a Work Order/Batch.
export const getRecentRolls = () =>
  getList('Roll', {
    fields: ['name', 'roll_no', 'item_code', 'batch', 'roll_weight', 'total_qty', 'stock_uom'],
    limit: 500,
    orderBy: 'creation desc'
  })

export const callMethod     = call
export const getCurrentUser = () => call('frappe.auth.get_logged_user')

export const getMTMNo = (jobCardId) =>
  getList('Job Card', {
    filters: [['Job Card', 'name', '=', jobCardId]],
    fields: ['name', 'work_order', 'production_item', 'custom_mtm_no'],
    limit: 1
  })

// ── Offline roll number sequencing ───────────────────────────────────────────
// Fetches the last ERP roll number and caches it in localStorage.
// Offline rolls increment from this value so they match ERP's sequence.

const ROLL_SEQ_KEY   = 'KNIT_LAST_ROLL_NO'
const ROLL_SEQ_TS    = 'KNIT_LAST_ROLL_TS'
const SEQ_TTL_MS     = 5 * 60 * 1000   // re-fetch from ERP every 5 minutes when online

export async function getLastRollNo() {
  try {
    const res = await call('knit_get_last_roll_no')
    const no  = parseInt(res?.message || 0, 10)
    if (no > 0) {
      localStorage.setItem(ROLL_SEQ_KEY, String(no))
      localStorage.setItem(ROLL_SEQ_TS, String(Date.now()))
    }
    return no
  } catch(e) {
    console.warn('getLastRollNo failed:', e.message)
    return parseInt(localStorage.getItem(ROLL_SEQ_KEY) || '0', 10)
  }
}

export function nextOfflineRollNo() {
  // Increment the cached value and persist it so parallel tabs don't collide
  const current = parseInt(localStorage.getItem(ROLL_SEQ_KEY) || '0', 10)
  const next    = current + 1
  localStorage.setItem(ROLL_SEQ_KEY, String(next))
  return next
}

export function isCachedRollNoStale() {
  const ts = parseInt(localStorage.getItem(ROLL_SEQ_TS) || '0', 10)
  return Date.now() - ts > SEQ_TTL_MS
}
