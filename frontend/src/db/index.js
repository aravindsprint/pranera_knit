// src/db/index.js
// Mirrors the SQLite tables in knit_app.js for full offline capability
import Dexie from 'dexie'

export const db = new Dexie('PraneraKnitDB')

db.version(1).stores({
  // ── Lookup / sync tables (populated by dojobs* sync endpoints) ──
  items:          '&name, item_code, commercial_name, color, width, modified',
  job_cards:      '&id, work_order, status, workstation, production_item, modified',
  time_logs:      '&id, parent, employee, from_time, modified',
  work_orders:    '&id, item_code, status, modified',
  batches:        '&id, item, modified',
  warehouses:     '&id, warehouse_name, modified',
  stock_entries:  '&id, purpose, modified',
  purchase_orders:'&id, supplier, modified',
  subcontracting_orders: '&id, supplier, modified',
  quality_inspection_parameters: '&name, item_code, modified',

  // ── Production tables (written locally, synced to ERP) ──
  rolls: '++idx, id, job_card, roll_no, docstatus, _syncStatus, _createdAt',
  knitccrolls: '++idx, id, start_time, end_time, modified',
  quality_inspections: '++idx, local_id, erp_name, item_code, _syncStatus, _createdAt',
  quality_inspection_readings: '++idx, inspection_local_id, specification',

  // ── Offline sync queue ──
  syncQueue: '++id, endpoint, method, _status, _retries, _createdAt',

  // ── Session / local state ──
  rollSessions: '&jobCardId, rollNo, isActive, _updatedAt',
})

// v2 — add cached employees table so the Assign modal works offline.
// Adding a new version (not editing v1) lets Dexie migrate existing data
// in place instead of wiping the user's cache.
db.version(2).stores({
  employees: '&name, employee_name, designation, user_id, _search, modified',
})

// v3 — local store for stock reconciliations submitted from the Work Order page.
db.version(3).stores({
  stock_reconciliations: '++id, work_order, created_at, _syncedAt',
})

// _syncStatus values: 'pending' | 'syncing' | 'synced' | 'failed'

export default db
