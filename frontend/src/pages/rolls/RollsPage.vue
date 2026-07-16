<template>
  <div class="rp-page">
    <AppHeader title="Rolls" active="" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="rp-content">

      <!-- ── LIST VIEW ─────────────────────────────────────────────────── -->
      <template v-if="!selectedRoll">

        <!-- Search + filters -->
        <div class="rp-toolbar">
          <div class="rp-search">
            <span class="rp-search__icon">🔍</span>
            <input v-model="search" class="rp-search__input" placeholder="Roll No, Item, Work Order, Job Card, Batch…"
              @keydown.enter="fetchRolls" />
          </div>
          <button class="rp-btn rp-btn--primary" @click="openCreate">+ New Roll</button>
        </div>

        <div class="rp-error" v-if="listError">⚠ {{ listError }}</div>

        <!-- List -->
        <div class="rp-card rp-card--table" v-if="rolls.length || listLoading">
          <div class="rp-table-wrap">
            <table class="rp-table">
              <thead>
                <tr>
                  <th>Roll No</th>
                  <th>Item</th>
                  <th>Work Order</th>
                  <th>Weight</th>
                  <th>Batch</th>
                  <th>Shift</th>
                  <th>Date</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="listLoading">
                  <td colspan="8" class="rp-td-center"><span class="rp-spinner"></span> Loading…</td>
                </tr>
                <tr v-for="r in rolls" :key="r.name" class="rp-row" @click="openDetail(r.name)">
                  <td class="rp-td-bold">{{ r.name }}</td>
                  <td class="rp-td-sm">{{ r.item_code }}</td>
                  <td class="rp-td-sm">{{ r.work_order || '—' }}</td>
                  <td class="rp-td-num">{{ r.roll_weight ? Number(r.roll_weight).toFixed(3) : '—' }}</td>
                  <td class="rp-td-sm">{{ r.batch || '—' }}</td>
                  <td>{{ r.shift || '—' }}</td>
                  <td class="rp-td-sm">{{ r.datetime ? fmtDate(r.datetime) : '—' }}</td>
                  <td @click.stop>
                    <div class="rp-row-actions">
                      <button class="rp-icon-btn" title="Print sticker" @click.stop="quickPrint(r.name)">🖨</button>
                      <button class="rp-icon-btn rp-icon-btn--danger" title="Delete" @click.stop="confirmDelete(r.name)">🗑</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div class="rp-pagination" v-if="!listLoading">
            <button class="rp-btn rp-btn--ghost rp-btn--sm" :disabled="page === 0" @click="page--; fetchRolls()">← Prev</button>
            <span class="rp-page-info">Page {{ page + 1 }}</span>
            <button class="rp-btn rp-btn--ghost rp-btn--sm" :disabled="rolls.length < pageSize" @click="page++; fetchRolls()">Next →</button>
          </div>
        </div>

        <div class="rp-empty" v-else-if="!listLoading">
          <div style="font-size:40px">🧶</div>
          <div>No rolls found</div>
          <div style="font-size:12px;color:#94a3b8">Try a different search term</div>
        </div>

      </template>

      <!-- ── DETAIL / EDIT VIEW ─────────────────────────────────────────── -->
      <template v-else>
        <div class="rp-detail-header">
          <button class="rp-back-btn" @click="closeDetail">← Back</button>
          <div class="rp-detail-title">Roll {{ selectedRoll.name }}</div>
          <div class="rp-detail-actions">
            <button class="rp-btn rp-btn--outline rp-btn--sm" @click="printSticker(selectedRoll)">🖨 Print Sticker</button>
            <button class="rp-btn rp-btn--primary rp-btn--sm" @click="saveRoll" :disabled="saving">
              <span v-if="saving" class="rp-spinner rp-spinner--sm"></span>
              {{ saving ? 'Saving…' : '💾 Save' }}
            </button>
          </div>
        </div>

        <div class="rp-error" v-if="detailError">⚠ {{ detailError }}</div>
        <div class="rp-success" v-if="saveSuccess">✓ Roll saved successfully</div>

        <!-- Info grid -->
        <div class="rp-card">
          <div class="rp-field-grid">
            <div class="rp-field">
              <label class="rp-label">Roll No</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.name" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Work Order</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.work_order || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Job Card</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.job_card || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Item Code</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.item_code || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Commercial Name</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.commercial_name || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Color</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.color || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Width</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.width || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Batch</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.batch || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Shift</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.shift || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Operator</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.knit_operator_name || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Knitting Machine</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.knitting_machine_no || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Warehouse</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.warehouse || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Stock UOM</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.stock_uom || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Start Time</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.start_time || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">End Time</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.end_time || ''" readonly />
            </div>
            <div class="rp-field">
              <label class="rp-label">Efficiency</label>
              <input class="rp-input rp-input--readonly" :value="selectedRoll.efficiency || ''" readonly />
            </div>
          </div>

          <!-- Editable fields -->
          <div class="rp-edit-section">
            <div class="rp-edit-section__title">Edit</div>
            <div class="rp-field-grid rp-field-grid--edit">
              <div class="rp-field">
                <label class="rp-label rp-label--edit">Roll Weight (kg) *</label>
                <input class="rp-input rp-input--edit" v-model="editForm.roll_weight" type="number" step="0.001" min="0" />
              </div>
              <div class="rp-field">
                <label class="rp-label rp-label--edit">Total Qty (pcs)</label>
                <input class="rp-input rp-input--edit" v-model="editForm.total_qty" type="number" min="0" />
              </div>
              <div class="rp-field">
                <label class="rp-label rp-label--edit">Mistake Qty</label>
                <input class="rp-input rp-input--edit" v-model="editForm.mistake_qty" type="number" min="0" />
              </div>
            </div>
          </div>
        </div>

        <!-- QR preview -->
        <div class="rp-card rp-card--qr">
          <div class="rp-card__title">Sticker Preview</div>
          <canvas ref="detailQrCanvas" style="display:block;margin:0 auto 12px;border-radius:8px"></canvas>
          <div class="rp-sticker-preview">
            <div class="rp-sticker-row"><span>Roll No</span><strong>{{ selectedRoll.name }}</strong></div>
            <div class="rp-sticker-row"><span>Item</span><strong>{{ selectedRoll.item_code }}</strong></div>
            <div class="rp-sticker-row"><span>Commercial</span><strong>{{ selectedRoll.commercial_name }}</strong></div>
            <div class="rp-sticker-row"><span>Work Order</span><strong>{{ selectedRoll.work_order }}</strong></div>
            <div class="rp-sticker-row"><span>Batch</span><strong>{{ selectedRoll.batch }}</strong></div>
            <div class="rp-sticker-row"><span>Weight</span><strong>{{ Number(editForm.roll_weight || 0).toFixed(3) }} kg</strong></div>
            <div class="rp-sticker-row" v-if="selectedRoll.stock_uom === 'Pcs'"><span>Qty</span><strong>{{ editForm.total_qty }}</strong></div>
            <div class="rp-sticker-row"><span>Date</span><strong>{{ fmtDate(selectedRoll.datetime) }}</strong></div>
          </div>
          <button class="rp-btn rp-btn--primary rp-btn--full" @click="printSticker(selectedRoll)" style="margin-top:14px">🖨 Print Sticker</button>
        </div>
      </template>

      <!-- ── CREATE MODAL ───────────────────────────────────────────────── -->
      <div class="rp-modal-overlay" v-if="showCreateModal" @click.self="showCreateModal = false">
        <div class="rp-modal">
          <div class="rp-modal__hd">
            <span>New Roll</span>
            <button class="rp-modal__close" @click="showCreateModal = false">✕</button>
          </div>
          <div class="rp-field-grid">
            <div class="rp-field">
              <label class="rp-label">Job Card *</label>
              <input class="rp-input" v-model="createForm.job_card" placeholder="PO-JOBxxxx" />
            </div>
            <div class="rp-field">
              <label class="rp-label">Work Order</label>
              <input class="rp-input" v-model="createForm.work_order" placeholder="WO/26/xxxx" />
            </div>
            <div class="rp-field">
              <label class="rp-label">Roll Weight (kg) *</label>
              <input class="rp-input" v-model="createForm.roll_weight" type="number" step="0.001" min="0" />
            </div>
            <div class="rp-field">
              <label class="rp-label">Batch</label>
              <input class="rp-input" v-model="createForm.batch" />
            </div>
            <div class="rp-field">
              <label class="rp-label">Shift</label>
              <input class="rp-input" v-model="createForm.shift" />
            </div>
          </div>
          <div class="rp-error" v-if="createError">⚠ {{ createError }}</div>
          <div class="rp-modal__footer">
            <button class="rp-btn rp-btn--ghost" @click="showCreateModal = false">Cancel</button>
            <button class="rp-btn rp-btn--primary" @click="createRoll" :disabled="creating">
              <span v-if="creating" class="rp-spinner rp-spinner--sm"></span>
              {{ creating ? 'Creating…' : 'Create Roll' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Delete confirm -->
      <div class="rp-modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
        <div class="rp-modal rp-modal--sm">
          <div class="rp-modal__hd"><span>Delete Roll {{ deleteTarget }}?</span></div>
          <p style="padding:0 16px 4px;font-size:14px;color:#475569">This cannot be undone.</p>
          <div class="rp-error" v-if="deleteError">⚠ {{ deleteError }}</div>
          <div class="rp-modal__footer">
            <button class="rp-btn rp-btn--ghost" @click="deleteTarget = null">Cancel</button>
            <button class="rp-btn rp-btn--danger" @click="doDelete" :disabled="deleting">
              {{ deleting ? 'Deleting…' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { call, getList, getDoc, updateDoc, createDoc } from '@/api/frappe'
import QRCode from 'qrcode'
import moment from 'moment'

const auth = useAuthStore()

// ── State ─────────────────────────────────────────────────────────────────
const rolls       = ref([])
const search      = ref('')
const page        = ref(0)
const pageSize    = 20
const listLoading = ref(false)
const listError   = ref('')

const selectedRoll  = ref(null)
const editForm      = ref({})
const saving        = ref(false)
const detailError   = ref('')
const saveSuccess   = ref(false)
const detailQrCanvas = ref(null)

const showCreateModal = ref(false)
const createForm = ref({ job_card: '', work_order: '', roll_weight: '', batch: '', shift: '1' })
const creating   = ref(false)
const createError = ref('')

const deleteTarget = ref(null)
const deleting     = ref(false)
const deleteError  = ref('')

// ── Fetch list ─────────────────────────────────────────────────────────────
async function fetchRolls() {
  listLoading.value = true
  listError.value   = ''
  try {
    const q = (search.value || '').trim()
    const orFilters = q
      ? [
          ['name', 'like', `%${q}%`],
          ['roll_no', 'like', `%${q}%`],
          ['item_code', 'like', `%${q}%`],
          ['work_order', 'like', `%${q}%`],
          ['batch', 'like', `%${q}%`],
          ['job_card', 'like', `%${q}%`],
        ]
      : []

    const res = await getList('Roll', {
      fields: ['name', 'roll_no', 'item_code', 'work_order', 'roll_weight',
               'batch', 'shift', 'datetime', 'commercial_name', 'color', 'job_card'],
      orFilters,
      limit: pageSize,
      orderBy: `CAST(name AS UNSIGNED) desc`,
    })
    // Offset manually via page
    const raw = Array.isArray(res) ? res : (res?.data || [])
    rolls.value = raw
  } catch(e) {
    listError.value = e.message || 'Failed to load rolls'
  } finally {
    listLoading.value = false
  }
}

// ── Open detail ────────────────────────────────────────────────────────────
async function openDetail(name) {
  detailError.value = ''
  saveSuccess.value = false
  try {
    const data = await getDoc('Roll', name)
    selectedRoll.value = data
    editForm.value = {
      roll_weight:       data.roll_weight ?? '',
      total_qty:         data.total_qty ?? 0,
      mistake_qty:       data.mistake_qty ?? 0,
      actual_width:      data.actual_width ?? '',
      width:             data.width ?? '',
      shift:             data.shift ?? '',
      knit_operator_name: data.knit_operator_name ?? '',
      knitting_machine_no: data.knitting_machine_no ?? '',
    }
    await nextTick()
    renderDetailQr(data)
  } catch(e) {
    detailError.value = e.message
  }
}

function closeDetail() {
  selectedRoll.value = null
  saveSuccess.value  = false
  detailError.value  = ''
}

async function renderDetailQr(roll) {
  await nextTick()
  if (!detailQrCanvas.value) return
  const qrData = `${roll.item_code}#${roll.work_order}#${roll.name}`
  try {
    await QRCode.toCanvas(detailQrCanvas.value, qrData, { width: 180 })
  } catch(e) { console.error(e) }
}

// ── Save ───────────────────────────────────────────────────────────────────
async function saveRoll() {
  saving.value = true
  detailError.value = ''
  saveSuccess.value = false
  try {
    const payload = {
      roll_weight:         parseFloat(editForm.value.roll_weight) || 0,
      total_qty:           parseInt(editForm.value.total_qty) || 0,
      mistake_qty:         parseInt(editForm.value.mistake_qty) || 0,
      correct_qty:         (parseInt(editForm.value.total_qty) || 0) - (parseInt(editForm.value.mistake_qty) || 0),
      actual_width:        editForm.value.actual_width || '',
      width:               editForm.value.width || '',
      shift:               editForm.value.shift || '',
      knit_operator_name:  editForm.value.knit_operator_name || '',
      name_of_the_operator: editForm.value.knit_operator_name || '',
      knitting_machine_no: editForm.value.knitting_machine_no || '',
    }
    await updateDoc('Roll', selectedRoll.value.name, payload)
    // Refresh the selectedRoll data
    selectedRoll.value = { ...selectedRoll.value, ...payload }
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 3000)
  } catch(e) {
    detailError.value = e.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

// ── Create ─────────────────────────────────────────────────────────────────
function openCreate() {
  createForm.value = { job_card: '', work_order: '', roll_weight: '', batch: '', shift: '1' }
  createError.value = ''
  showCreateModal.value = true
}

async function createRoll() {
  if (!createForm.value.job_card) { createError.value = 'Job Card is required'; return }
  if (!createForm.value.roll_weight) { createError.value = 'Roll Weight is required'; return }
  creating.value = true
  createError.value = ''
  try {
    const resp = await call('knit_create_roll', {
      job_card: createForm.value.job_card,
      batch_no: createForm.value.batch || '',
    })
    const newName = resp?.message?.[0]?.name
    // Save weight
    if (newName) {
      await call('knit_save_roll_data', {
        job_card:    createForm.value.job_card,
        work_order:  createForm.value.work_order,
        roll_no:     newName,
        roll_weight: createForm.value.roll_weight,
        batch:       createForm.value.batch,
        shift:       createForm.value.shift,
      })
    }
    showCreateModal.value = false
    await fetchRolls()
    if (newName) openDetail(newName)
  } catch(e) {
    createError.value = e.message || 'Create failed'
  } finally {
    creating.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────
function confirmDelete(name) { deleteTarget.value = name; deleteError.value = '' }

async function doDelete() {
  deleting.value = true
  deleteError.value = ''
  try {
    await call('knit_delete_roll', { roll_name: deleteTarget.value })
    deleteTarget.value = null
    await fetchRolls()
  } catch(e) {
    deleteError.value = e.message || 'Delete failed'
  } finally {
    deleting.value = false
  }
}

// ── Quick print from list ──────────────────────────────────────────────────
async function quickPrint(name) {
  try {
    const roll = await getDoc('Roll', name)
    printSticker(roll)
  } catch(e) { alert('Failed to load roll: ' + e.message) }
}

// ── Print sticker ──────────────────────────────────────────────────────────
async function printSticker(roll) {
  const w = window.open('', '_blank')
  if (!w) { alert('Allow pop-ups to print.'); return }

  const weight = Number(editForm.value?.roll_weight ?? roll.roll_weight ?? 0).toFixed(3)
  const qty    = roll.stock_uom === 'Pcs' ? (editForm.value?.total_qty ?? roll.total_qty ?? 0) : null
  const qrData = `${roll.item_code}#${roll.work_order}#${roll.name}`
  const batchRow = roll.batch ? `<tr><td>${roll.batch}</td></tr>` : ''
  // Generate QR as a data URL with the bundled package (offline-safe, no CDN)
  let qrImg = ''
  try {
    qrImg = await QRCode.toDataURL(qrData, { width: 200, margin: 1 })
  } catch(e) { console.error('QR generation failed:', e) }
  const qrCell = qrImg ? `<img src="${qrImg}" style="width:24mm;height:24mm" alt="QR"/>` : ''

  w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Roll Sticker</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:100%; height:100%; }
  body { font-family:Arial,sans-serif; display:flex; flex-direction:column;
         align-items:center; justify-content:center; min-height:100vh; }
  .sticker { width:50mm; min-height:65mm; border:1px solid #000; display:flex;
             margin:0 auto; flex-direction:column; flex-shrink:0; }
  .qr-cell { display:flex; align-items:center; justify-content:center; padding:2mm;
             border-bottom:1px solid #000; flex:0 0 auto; }
  table { width:calc(100% - 0.5cm); margin-left:0.5cm; border-collapse:collapse; flex:1; }
  td { padding:1.2mm 3mm; border-bottom:0.3px solid #888; font-size:7.5pt; font-weight:700;
       font-family:Arial,sans-serif; color:#000; line-height:1.15; }
  tr:last-child td { border-bottom:none; padding-bottom:1.5mm; }
  .noprint { text-align:center; padding:10px; }
  .noprint button { padding:7px 18px; margin:0 4px; border-radius:5px; border:none;
    cursor:pointer; font-size:12px; font-weight:600; }
  .btn-p { background:#000; color:#fff; }
  .btn-c { background:#eee; color:#333; }
  @media print {
    .noprint { display:none; }
    html, body { width:100%; height:75mm; max-height:75mm; margin:0; padding:0; overflow:hidden; }
    body { display:block; }
    .sticker { margin:0 auto; max-height:75mm; overflow:hidden; }
    @page { size:60mm 75mm; margin:0; }
  }
</style>
</head><body>
<div class="sticker">
  <div class="qr-cell">${qrCell}</div>
  <table>
    <tr><td>${roll.item_code || ''}</td></tr>
    <tr><td>${roll.commercial_name || ''}</td></tr>
    <tr><td>${roll.work_order || ''}</td></tr>
    <tr><td>${roll.name}</td></tr>
    <tr><td>${weight} kg${qty !== null ? ` · ${qty} pcs` : ''}</td></tr>
    ${batchRow}
  </table>
</div>
<div class="noprint">
  <button class="btn-p" onclick="window.print()">🖨 Print</button>
  <button class="btn-c" onclick="window.close()">Close</button>
</div>
</body></html>`)
  w.document.close()
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d) return '—'
  return moment(d).format('DD-MM-YYYY')
}

// ── Init ───────────────────────────────────────────────────────────────────
onMounted(fetchRolls)

let searchTimer = null
watch(search, () => {
  clearTimeout(searchTimer)
  page.value = 0
  searchTimer = setTimeout(fetchRolls, 400)
})
</script>

<style scoped>
.rp-page    { min-height:100vh; background:#f1f5f9; }
.rp-content { padding:16px; max-width:1100px; margin:0 auto; }

/* Toolbar */
.rp-toolbar { display:flex; gap:10px; margin-bottom:14px; align-items:center; }
.rp-search  { flex:1; position:relative; }
.rp-search__icon  { position:absolute; left:10px; top:50%; transform:translateY(-50%); font-size:13px; pointer-events:none; }
.rp-search__input { width:100%; padding:10px 12px 10px 32px; border:1.5px solid #e2e8f0; border-radius:10px;
  font-size:14px; outline:none; background:white; font-family:inherit; box-sizing:border-box; }
.rp-search__input:focus { border-color:var(--app-primary,#0f6e56); }

/* Buttons */
.rp-btn { padding:10px 18px; border-radius:10px; border:none; font-size:13px; font-weight:600;
  cursor:pointer; font-family:inherit; display:inline-flex; align-items:center; gap:6px; transition:opacity 0.15s; }
.rp-btn:disabled { opacity:0.5; cursor:not-allowed; }
.rp-btn--primary { background:var(--app-primary,#0f6e56); color:white; }
.rp-btn--outline { background:white; color:var(--app-primary,#0f6e56); border:1.5px solid var(--app-primary,#0f6e56); }
.rp-btn--ghost   { background:#f8fafc; color:#64748b; border:1.5px solid #e2e8f0; }
.rp-btn--danger  { background:#dc2626; color:white; }
.rp-btn--sm   { padding:7px 14px; font-size:12px; }
.rp-btn--full { width:100%; justify-content:center; }

/* Card */
.rp-card { background:white; border-radius:14px; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.07); overflow:hidden; }
.rp-card--table { padding:0; }
.rp-card--qr    { padding:16px; }
.rp-card__title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em;
  color:#94a3b8; margin-bottom:12px; }

/* Table */
.rp-table-wrap { overflow-x:auto; }
.rp-table { width:100%; border-collapse:collapse; font-size:13px; }
.rp-table th { background:#f8fafc; padding:9px 12px; text-align:left; font-size:10px; font-weight:700;
  text-transform:uppercase; letter-spacing:0.05em; color:#64748b; border-bottom:2px solid #e2e8f0; white-space:nowrap; }
.rp-table td { padding:9px 12px; border-bottom:1px solid #f1f5f9; color:#0f172a; vertical-align:middle; }
.rp-row { cursor:pointer; transition:background 0.1s; }
.rp-row:hover td { background:#f8fafc; }
.rp-td-bold { font-weight:800; color:#0f172a; }
.rp-td-sm   { font-size:11px; color:#475569; }
.rp-td-num  { text-align:right; font-family:monospace; font-size:12px; }
.rp-td-center { text-align:center; padding:24px; color:#94a3b8; }
.rp-row-actions { display:flex; gap:6px; }
.rp-icon-btn { background:#f1f5f9; border:none; border-radius:6px; width:30px; height:30px;
  cursor:pointer; font-size:14px; display:flex; align-items:center; justify-content:center; }
.rp-icon-btn:hover { background:#e2e8f0; }
.rp-icon-btn--danger:hover { background:#fee2e2; }

/* Pagination */
.rp-pagination { display:flex; align-items:center; justify-content:center; gap:14px; padding:12px; border-top:1px solid #f1f5f9; }
.rp-page-info { font-size:13px; color:#64748b; font-weight:600; }

/* Empty */
.rp-empty { text-align:center; padding:48px 24px; color:#94a3b8; display:flex; flex-direction:column; align-items:center; gap:8px; }

/* Detail header */
.rp-detail-header { display:flex; align-items:center; gap:12px; margin-bottom:14px; flex-wrap:wrap; }
.rp-back-btn { background:white; border:1.5px solid #e2e8f0; border-radius:8px; padding:8px 14px;
  font-size:13px; font-weight:600; cursor:pointer; color:#475569; }
.rp-back-btn:hover { background:#f8fafc; }
.rp-detail-title { font-size:17px; font-weight:800; color:#0f172a; flex:1; }
.rp-detail-actions { display:flex; gap:8px; }

/* Field grid */
.rp-field-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; padding:16px; }
@media(max-width:600px) { .rp-field-grid { grid-template-columns:1fr; } }
.rp-field { display:flex; flex-direction:column; gap:4px; }
.rp-label { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#94a3b8; }
.rp-input { padding:9px 12px; border:1.5px solid #e2e8f0; border-radius:8px; font-size:13px;
  font-family:inherit; outline:none; background:white; }
.rp-input:focus { border-color:var(--app-primary,#0f6e56); }
.rp-input--readonly { background:#f8fafc; color:#64748b; cursor:default; }
.rp-edit-section { border-top:2px solid var(--app-primary,#0f6e56); margin:0 16px 16px; padding-top:14px; }
.rp-edit-section__title { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
  color:var(--app-primary,#0f6e56); margin-bottom:10px; }
.rp-field-grid--edit { grid-template-columns:repeat(3,1fr); padding:0; }
@media(max-width:600px) { .rp-field-grid--edit { grid-template-columns:1fr; } }
.rp-label--edit { color:var(--app-primary,#0f6e56); }
.rp-input--edit { border-color:var(--app-primary,#0f6e56); background:#f0fdf4; }
.rp-input--edit:focus { border-color:var(--app-primary,#0f6e56); box-shadow:0 0 0 3px rgba(15,110,86,0.1); }

/* Sticker preview */
.rp-sticker-preview { border:1.5px solid #e2e8f0; border-radius:8px; overflow:hidden; }
.rp-sticker-row { display:flex; justify-content:space-between; padding:7px 12px; border-bottom:1px solid #f1f5f9; font-size:13px; }
.rp-sticker-row:last-child { border-bottom:none; }
.rp-sticker-row span { color:#64748b; font-size:11px; }
.rp-sticker-row strong { color:#0f172a; font-weight:700; }

/* Modal */
.rp-modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:200;
  display:flex; align-items:center; justify-content:center; padding:16px; }
.rp-modal { background:white; border-radius:14px; width:100%; max-width:480px;
  box-shadow:0 16px 48px rgba(0,0,0,0.2); overflow:hidden; }
.rp-modal--sm { max-width:340px; }
.rp-modal__hd { display:flex; justify-content:space-between; align-items:center;
  padding:16px 16px 12px; font-size:15px; font-weight:700; border-bottom:1px solid #f1f5f9; }
.rp-modal__close { background:none; border:none; font-size:18px; cursor:pointer; color:#94a3b8; }
.rp-modal__footer { display:flex; justify-content:flex-end; gap:10px; padding:14px 16px;
  border-top:1px solid #f1f5f9; }

/* Alerts */
.rp-error   { background:#fef2f2; color:#dc2626; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:10px; }
.rp-success { background:#f0fdf4; color:#16a34a; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:10px; }

/* Spinner */
.rp-spinner { display:inline-block; width:14px; height:14px; border:2px solid rgba(255,255,255,0.35);
  border-top-color:white; border-radius:50%; animation:spin 0.7s linear infinite; }
.rp-spinner--sm { width:12px; height:12px; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
