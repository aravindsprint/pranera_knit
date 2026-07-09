// src/composables/useSync.js
// Core offline-first sync engine
// Replaces Node.js backend as the intermediary — Vue PWA talks directly to ERPNext
import { ref, onMounted, onUnmounted } from 'vue'
import { db } from '@/db'
import {
  createRollInERP, createQualityInspection,
  createPickingEntry, startJobCard, submitRollPackingList
} from '@/api/frappe'

export const isOnline = ref(navigator.onLine)
export const isSyncing = ref(false)
export const pendingCount = ref(0)
export const lastSyncAt = ref(null)

// Normalize a list response into a plain array of rows. Our getList() helper
// returns a bare array, while raw /api/resource fetches return { data: [...] }
// and some endpoints nest as { data: { data: [...] } }. Handle all shapes.
function normalizeRows(res) {
  if (Array.isArray(res)) return res
  if (Array.isArray(res?.data)) return res.data
  if (Array.isArray(res?.data?.data)) return res.data.data
  if (Array.isArray(res?.message)) return res.message
  return []
}

let syncTimer = null
let reachTimer = null

// ── Real connectivity probe ──────────────────────────────────────────────────
// navigator.onLine only reports whether a network interface exists — it returns
// true on WiFi that has no route to the ERP server. This actually pings the
// backend so isOnline reflects whether erp.pranera.in is reachable right now.
export async function checkReachable() {
  // If the OS says the interface is down, trust it — we're definitely offline.
  if (!navigator.onLine) {
    if (isOnline.value) isOnline.value = false
    return false
  }
  try {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 4000)
    // knit_get_csrf is a cheap, always-available Server Script endpoint.
    const r = await fetch('/api/method/knit_get_csrf', {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
      signal: ctrl.signal,
    })
    clearTimeout(t)
    const reachable = r.ok
    if (isOnline.value !== reachable) {
      isOnline.value = reachable
      if (reachable) { flushQueue(); syncLookupTables() }
    }
    return reachable
  } catch {
    if (isOnline.value) isOnline.value = false
    return false
  }
}

// ── Refresh pending count from DB ────────────────────────────────────────────
async function refreshPendingCount() {
  pendingCount.value = await db.syncQueue
    .where('_status').equals('pending').count()
}

// ── Queue any mutation for deferred sync ─────────────────────────────────────
export async function enqueue(endpoint, method = 'POST', payload = {}) {
  await db.syncQueue.add({
    endpoint,
    method,
    payload,
    _status: 'pending',
    _retries: 0,
    _createdAt: new Date().toISOString()
  })
  await refreshPendingCount()
  if (isOnline.value) flushQueue()
}

// ── Save a roll locally, queue sync to ERP ───────────────────────────────────
export async function saveRollOffline(rollData) {
  // Use the offline roll number as the local ID (it's the sequential number from nextOfflineRollNo)
  const localId = String(rollData.roll_no || `ROLL-LOCAL-${Date.now()}`)
  await db.rolls.add({
    ...rollData,
    id: localId,
    _syncStatus: 'pending',
    _createdAt: new Date().toISOString()
  })
  await enqueue('insertIntoRollTable', 'POST', { ...rollData, _localId: localId })
  return localId
}

// ── Save a QI locally, queue sync to ERP ─────────────────────────────────────
export async function saveQIOffline(qiData) {
  const localId = `QI-LOCAL-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  await db.quality_inspections.add({
    ...qiData,
    local_id: localId,
    erp_name: null,
    _syncStatus: 'pending',
    _createdAt: new Date().toISOString()
  })
  await enqueue('createQualityInspection', 'POST', { ...qiData, _localId: localId })
  return localId
}

// ── Save roll session (breakdown tracking) in IndexedDB ──────────────────────
export async function saveRollSession(jobCardId, sessionData) {
  await db.rollSessions.put({
    jobCardId,
    ...sessionData,
    _updatedAt: new Date().toISOString()
  })
}

export async function getRollSession(jobCardId) {
  return db.rollSessions.get(jobCardId)
}

export async function clearRollSession(jobCardId) {
  await db.rollSessions.delete(jobCardId)
}

// ── Flush pending queue to ERPNext ────────────────────────────────────────────
export async function flushQueue() {
  if (isSyncing.value || !isOnline.value) return
  isSyncing.value = true

  try {
    const pending = await db.syncQueue
      .where('_status').equals('pending')
      .sortBy('_createdAt')

    for (const item of pending) {
      await db.syncQueue.update(item.id, { _status: 'syncing' })

      try {
        let erpResult = null

        // Route each queued operation to the right ERP API call
        switch (item.endpoint) {
          case 'insertIntoRollTable': {
            // Call knit_save_roll_data which handles both new and existing rolls
            const { call: frappeCall } = await import('@/api/frappe')
            erpResult = await frappeCall('knit_save_roll_data', item.payload)
            const realName = erpResult?.message?.name
            // Update local roll record with real ERP name and update sequence cache
            if (item.payload._localId && realName) {
              await db.rolls
                .where('id').equals(item.payload._localId)
                .modify({ id: realName, _syncStatus: 'synced' })
              // Update the cached last roll number so future offline rolls stay in sequence
              const n = parseInt(realName, 10)
              if (!isNaN(n)) {
                const cached = parseInt(localStorage.getItem('KNIT_LAST_ROLL_NO') || '0', 10)
                if (n > cached) {
                  localStorage.setItem('KNIT_LAST_ROLL_NO', String(n))
                  localStorage.setItem('KNIT_LAST_ROLL_TS', String(Date.now()))
                }
              }
            }
            break
          }

          case 'createQualityInspection':
            erpResult = await createQualityInspection(item.payload)
            if (item.payload._localId && erpResult?.data?.data?.name) {
              await db.quality_inspections
                .where('local_id').equals(item.payload._localId)
                .modify({ erp_name: erpResult.data.data.name, _syncStatus: 'synced' })
            }
            break

          case 'createRollPickingEntry':
            erpResult = await createPickingEntry(item.payload)
            break

          case 'startJobCard':
            erpResult = await startJobCard(item.payload.jobCardId)
            break

          case 'assignEmployeeToJobCard': {
            const { call: frappeCall } = await import('@/api/frappe')
            erpResult = await frappeCall('knit_assign_employee_to_job_card', {
              job_card: item.payload.job_card,
              employee_id: item.payload.employee_id
            })
            break
          }

          case 'submitRollPackingList':
            erpResult = await submitRollPackingList(item.payload.jobcard, item.payload.work_order)
            break

          default:
            console.warn('Unknown sync endpoint:', item.endpoint)
        }

        await db.syncQueue.update(item.id, { _status: 'synced', _syncedAt: new Date().toISOString() })

      } catch (err) {
        const retries = (item._retries || 0) + 1
        // Exponential backoff — mark as failed after 5 retries
        const newStatus = retries >= 5 ? 'failed' : 'pending'
        await db.syncQueue.update(item.id, { _status: newStatus, _retries: retries })
        console.error(`Sync failed for ${item.endpoint} (attempt ${retries}):`, err.message)
      }
    }

    lastSyncAt.value = new Date().toISOString()
  } finally {
    isSyncing.value = false
    await refreshPendingCount()
  }
}

// ── Sync lookup tables (replaces dojobs* Node cron endpoints) ─────────────────
export async function syncLookupTables() {
  if (!isOnline.value) return

  const {
    syncItems, syncWorkOrders, syncTimeLogs,
    syncStockEntries, syncQIParameters, syncEmployees
  } = await import('@/api/frappe')

  const tasks = [
    { name: 'Items',          fn: syncItems,        table: 'items',         key: 'name' },
    { name: 'Work Orders',    fn: syncWorkOrders,   table: 'work_orders',   key: 'name' },
    { name: 'Time Logs',      fn: syncTimeLogs,     table: 'time_logs',     key: 'name' },
    { name: 'Stock Entries',  fn: syncStockEntries, table: 'stock_entries', key: 'name' },
    { name: 'QI Parameters',  fn: syncQIParameters, table: 'quality_inspection_parameters', key: 'name' },
  ]

  for (const task of tasks) {
    try {
      const res = await task.fn()
      const rows = normalizeRows(res)
      // Upsert all rows into IndexedDB
      await db[task.table].bulkPut(
        rows.map(r => ({ ...r, id: r.name }))
      )
      console.log(`Synced ${rows.length} ${task.name}`)
    } catch (err) {
      console.warn(`Sync failed for ${task.name}:`, err.message)
    }
  }

  // Employees — cached separately so we can add a lowercase _search field
  // for fast offline name/ID matching in the Assign modal.
  try {
    const res = await syncEmployees()
    const rows = normalizeRows(res)
    await db.employees.bulkPut(
      rows.map(e => ({
        ...e,
        _search: `${e.employee_name || ''} ${e.name || ''} ${e.designation || ''}`.toLowerCase(),
      }))
    )
    console.log(`Synced ${rows.length} Employees`)
  } catch (err) {
    console.warn('Sync failed for Employees:', err.message)
  }
}

// ── Composable setup / teardown ──────────────────────────────────────────────
export function useSync() {
  function onOnlineHandler() {
    // OS says a network appeared — confirm the ERP is actually reachable
    // before flipping online (checkReachable flushes + syncs if it is).
    checkReachable()
  }
  function onOfflineHandler() {
    isOnline.value = false
  }

  onMounted(async () => {
    window.addEventListener('online', onOnlineHandler)
    window.addEventListener('offline', onOfflineHandler)
    await refreshPendingCount()
    // Periodic retry every 10s
    syncTimer = setInterval(flushQueue, 10_000)
    // Probe real backend reachability immediately, then every 15s.
    checkReachable()
    reachTimer = setInterval(checkReachable, 15_000)
    if (isOnline.value) {
      flushQueue()
      // Populate offline caches (employees, items, params…) on first load
      syncLookupTables()
    }
  })

  onUnmounted(() => {
    window.removeEventListener('online', onOnlineHandler)
    window.removeEventListener('offline', onOfflineHandler)
    clearInterval(syncTimer)
    clearInterval(reachTimer)
  })

  return { isOnline, isSyncing, pendingCount, lastSyncAt, flushQueue, syncLookupTables }
}
