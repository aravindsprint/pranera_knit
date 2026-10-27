<template>
  <div class="page">
    <AppHeader
      :title="mode === 'list' ? 'Outward Requests' : (store.name || 'New Outward Request')"
      active="outward-request" :username="auth.username" :designation="auth.designation" :show-back="true"
    />

    <!-- ══════════════════════ LIST ══════════════════════ -->
    <div v-if="mode === 'list'" class="page-content">
      <button class="btn btn-primary btn-full" @click="openNew">
        <i class="pi pi-plus"></i> New Outward Request
      </button>

      <div class="card card--tight">
        <div class="chips">
          <button
            v-for="f in FILTERS" :key="f.value" class="chip"
            :class="{ 'chip--active': store.listFilter === f.value }"
            @click="setFilter(f.value)"
          >{{ f.label }}</button>
        </div>
        <input
          v-model="store.listSearch" class="form-input" style="margin-top:10px"
          placeholder="Search request, building, WO or PO..." @input="onListSearch"
        />
      </div>

      <div v-if="store.loadingList && !store.requests.length" class="empty">
        <i class="pi pi-spin pi-spinner"></i> Loading...
      </div>
      <div v-else-if="!store.requests.length" class="empty">No outward requests yet.</div>

      <button v-for="r in store.requests" :key="r.name" class="req-card" @click="openExisting(r.name)">
        <div class="req-card__top">
          <span class="req-card__name">{{ r.name }}</span>
          <span class="pill" :class="docStatusClass(r.request_status)">{{ r.request_status || 'Pending' }}</span>
        </div>
        <div class="req-card__to"><i class="pi pi-building"></i> {{ r.to_building }}</div>
        <div class="req-card__meta">
          <span>{{ r.work_order ? 'WO' : 'PO' }} · {{ r.work_order || r.purchase_order }}</span>
          <span>{{ fmtDate(r.date) }}</span>
        </div>
        <div class="req-card__foot">
          <span class="muted">{{ r.created_by_name }}</span>
          <span v-if="r.status" class="pill pill--soft" :class="statusClass(r.status)">{{ r.status }}</span>
        </div>
      </button>
    </div>

    <!-- ══════════════════════ FORM ══════════════════════ -->
    <div v-else class="page-content">
      <div v-if="store.meta" class="card status-card">
        <div class="status-grid">
          <div>
            <div class="form-label">Status</div>
            <span v-if="store.meta.status" class="pill" :class="statusClass(store.meta.status)">{{ store.meta.status }}</span>
            <span v-else class="muted">Not assigned yet</span>
          </div>
          <div>
            <div class="form-label">Doc Status</div>
            <span class="pill" :class="docStatusClass(store.meta.request_status)">{{ store.meta.request_status }}</span>
          </div>
          <div>
            <div class="form-label">Created By</div>
            <div class="value">{{ store.meta.created_by_name }}</div>
          </div>
          <div>
            <div class="form-label">Created On</div>
            <div class="value">{{ fmtDateTime(store.meta.created_on) }}</div>
          </div>
        </div>
        <div class="stepper">
          <div v-for="(s, i) in STEPS" :key="s" class="step" :class="{ 'step--done': stepIndex >= i }">
            <span class="step__dot"></span><span class="step__label">{{ s }}</span>
          </div>
        </div>
        <div v-if="store.meta.assignments.length" class="hint-text">
          <i class="pi pi-link"></i>
          <span>Roll Pick Assignment: {{ store.meta.assignments.map(a => `${a.name} (${a.status})`).join(', ') }}</span>
        </div>
      </div>

      <div class="card">
        <div class="row-2">
          <div>
            <label class="form-label">Date <span class="req">*</span></label>
            <input v-model="store.date" type="date" class="form-input" :disabled="!store.isEditable" />
          </div>
          <div>
            <label class="form-label">To <span class="req">*</span></label>
            <AutoComplete
              v-model="store.toBuilding" :options="store.buildingOptions"
              placeholder="Select building..." :disabled="!store.isEditable"
            />
          </div>
        </div>

        <label class="form-label" style="margin-top:14px">Fetch Items From <span class="req">*</span></label>
        <div class="segmented">
          <button
            v-for="t in ['Work Order', 'Purchase Order']" :key="t" class="segmented__btn"
            :class="{ 'segmented__btn--active': store.sourceType === t }"
            :disabled="!store.isEditable" @click="changeSource(t)"
          >{{ t }}</button>
        </div>

        <div class="fetch-row">
          <template v-if="store.sourceType === 'Work Order'">
            <input
              v-model="store.workOrder" list="or-wo-list" class="form-input"
              placeholder="Search work order..." :disabled="!store.isEditable"
              @input="onDocInput($event, 'wo')"
            />
            <datalist id="or-wo-list">
              <option v-for="wo in store.workOrders" :key="wo.name" :value="wo.name">{{ wo.production_item }}</option>
            </datalist>
          </template>
          <template v-else>
            <input
              v-model="store.purchaseOrder" list="or-po-list" class="form-input"
              placeholder="Search subcontracted PO..." :disabled="!store.isEditable"
              @input="onDocInput($event, 'po')"
            />
            <datalist id="or-po-list">
              <option v-for="po in store.purchaseOrders" :key="po.name" :value="po.name">{{ po.supplier_name }}</option>
            </datalist>
          </template>
          <button
            class="btn btn-outline" :disabled="!store.documentName || store.fetching || !store.isEditable"
            @click="store.fetchItems()"
          >
            <i class="pi" :class="store.fetching ? 'pi-spin pi-spinner' : 'pi-download'"></i>
            Fetch
          </button>
        </div>
        <div class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span v-if="store.sourceType === 'Work Order'">Items come from the Work Order's Required Items. Work Orders don't carry a batch — add one per row if needed.</span>
          <span v-else>Items come from the Raw Materials Supplied table of the submitted Subcontracting Receipt(s) for this PO, merged by item + batch.</span>
        </div>
      </div>

      <div class="card">
        <div class="items-head">
          <label class="form-label" style="margin:0">Items</label>
          <span v-if="store.receipts.length" class="muted small">From {{ store.receipts.join(', ') }}</span>
        </div>

        <div v-if="!store.items.length" class="empty empty--inline">
          Pick a {{ store.sourceType }} and tap Fetch to load items.
        </div>

        <div v-else class="items">
          <div class="items__header">
            <span>Item Code</span><span>Batch</span><span class="num">Qty</span><span>UOM</span><span></span>
          </div>
          <div v-for="(row, i) in store.items" :key="i" class="item-row">
            <span class="item-row__code">{{ row.item_code }}</span>
            <input v-model="row.batch" class="form-input form-input--sm" placeholder="—" :disabled="!store.isEditable" />
            <input
              v-model.number="row.qty" type="number" min="0" step="0.001"
              class="form-input form-input--sm num" :disabled="!store.isEditable"
            />
            <span class="item-row__uom">{{ row.stock_uom }}</span>
            <button v-if="store.isEditable" class="btn-remove" title="Remove row" @click="store.removeItem(i)">
              <i class="pi pi-times"></i>
            </button>
            <span v-else></span>
          </div>
          <div class="totals">
            <span v-for="(qty, uom) in store.totalsByUom" :key="uom" class="total-chip">
              {{ fmtQty(qty) }} <small>{{ uom }}</small>
            </span>
          </div>
        </div>
      </div>

      <div class="card" v-if="store.isEditable">
        <button class="btn btn-primary btn-full" :disabled="!store.canSave || store.saving" @click="save">
          <i v-if="store.saving" class="pi pi-spin pi-spinner"></i>
          {{ store.saving ? 'Saving...' : (store.name ? 'Update Outward Request' : 'Create Outward Request') }}
        </button>
        <div v-if="store.name" class="hint-text">
          <i class="pi pi-lock"></i>
          <span>Editable until a Roll Pick Assignment is linked to it.</span>
        </div>
      </div>

      <div v-if="store.error" class="error-banner">
        <i class="pi pi-exclamation-triangle"></i> {{ store.error }}
      </div>
    </div>

    <div v-if="mode === 'list' && store.error" class="page-content" style="padding-top:0">
      <div class="error-banner"><i class="pi pi-exclamation-triangle"></i> {{ store.error }}</div>
    </div>

    <transition name="modal-fade">
      <div v-if="savedName" class="modal-overlay" @click.self="savedName = ''">
        <div class="modal-box">
          <i class="pi pi-check-circle modal-icon"></i>
          <h3 class="modal-title">Outward Request Saved</h3>
          <div class="modal-docno">{{ savedName }}</div>
          <button class="btn btn-primary btn-full" @click="savedName = ''">OK</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useOutwardRequestStore } from '@/stores/outwardRequest'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'

const FILTERS = [
  { label: 'All', value: '' },
  { label: 'Pending', value: 'Pending' },
  { label: 'Processing', value: 'Processing' },
  { label: 'Completed', value: 'Completed' },
]
const STEPS = ['Roll Pick Assigned', 'Picked', 'Completed']

const auth = useAuthStore()
const store = useOutwardRequestStore()
const route = useRoute()
const router = useRouter()
const savedName = ref('')

// ?name=OR/26/00001 opens an existing request, ?new=1 a blank form,
// neither shows the list — so the header's back button and the browser's
// back gesture both step form → list as expected.
const mode = computed(() => (route.query.name || route.query.new ? 'form' : 'list'))
const stepIndex = computed(() => STEPS.indexOf(store.meta?.status || ''))

async function syncWithRoute() {
  if (route.query.name) {
    if (store.name !== route.query.name) await store.open(route.query.name)
  } else if (route.query.new) {
    if (store.name || store.meta) store.reset()
  } else {
    store.loadList()
  }
}

onMounted(() => {
  store.loadLookups()
  syncWithRoute()
})
watch(() => [route.query.name, route.query.new], syncWithRoute)
onBeforeUnmount(() => store.reset())

function openNew() {
  store.reset()
  router.push({ query: { new: '1' } })
}
function openExisting(name) {
  router.push({ query: { name } })
}
function setFilter(v) {
  store.listFilter = v
  store.loadList()
}

let listTimer = null
function onListSearch() {
  clearTimeout(listTimer)
  listTimer = setTimeout(() => store.loadList(), 300)
}

function changeSource(t) {
  if (t !== store.sourceType && store.items.length &&
      !window.confirm('Switching clears the fetched items. Continue?')) return
  store.setSourceType(t)
}

// Remote search while typing; once the text exactly matches a listed
// document (picked from the datalist), fetch its items straight away.
let docTimer = null
function onDocInput(e, kind) {
  const txt = e.target.value
  if (store.fetchedFor && store.fetchedFor !== txt) store.clearItems()
  const list = kind === 'wo' ? store.workOrders : store.purchaseOrders
  if (txt && list.some(d => d.name === txt)) {
    store.fetchItems()
    return
  }
  clearTimeout(docTimer)
  docTimer = setTimeout(() => {
    kind === 'wo' ? store.searchWorkOrders(txt) : store.searchPurchaseOrders(txt)
  }, 250)
}

async function save() {
  const wasNew = !store.name
  const doc = await store.save()
  if (!doc) return
  savedName.value = doc.name
  if (wasNew) router.replace({ query: { name: doc.name } })
}

function statusClass(s) {
  return { 'Roll Pick Assigned': 'pill--blue', Picked: 'pill--amber', Completed: 'pill--green' }[s] || ''
}
function docStatusClass(s) {
  return { Pending: 'pill--grey', Processing: 'pill--amber', Completed: 'pill--green' }[s || 'Pending'] || ''
}
function fmtDate(d) {
  if (!d) return ''
  const [y, m, day] = String(d).split('-')
  return `${day}-${m}-${y}`
}
function fmtDateTime(dt) {
  if (!dt) return '—'
  const [d, t = ''] = String(dt).split(' ')
  return `${fmtDate(d)} ${t.slice(0, 5)}`
}
function fmtQty(n) {
  return (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 3 })
}
</script>

<style scoped>
.page-content { padding: 16px; max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card--tight { padding: 12px; }

.form-label { display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
.req { color: #dc2626; }
.form-input {
  width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px;
  font-size: 14px; box-sizing: border-box; font-family: inherit; background: #fff;
}
.form-input:disabled { background: #f8fafc; color: #475569; }
.form-input--sm { padding: 7px 8px; font-size: 13px; border-radius: 8px; }
.muted { color: #64748b; }
.small { font-size: 11px; }
.value { font-size: 14px; color: #0f172a; font-weight: 600; }
.num { text-align: right; }

.row-2 { display: grid; grid-template-columns: 1fr 1.6fr; gap: 12px; }
@media (max-width: 480px) { .row-2 { grid-template-columns: 1fr; } }

.segmented { display: flex; background: #f1f5f9; border-radius: 10px; padding: 3px; }
.segmented__btn {
  flex: 1; border: none; background: none; padding: 9px; border-radius: 8px;
  font-size: 13px; font-weight: 600; color: #475569; cursor: pointer;
}
.segmented__btn--active { background: #fff; color: var(--app-primary, #0f6e56); box-shadow: 0 1px 2px rgba(0,0,0,0.08); }
.segmented__btn:disabled { cursor: not-allowed; }

.fetch-row { display: flex; gap: 8px; margin-top: 10px; }
.fetch-row .form-input { flex: 1; min-width: 0; }

.hint-text { font-size: 12px; color: #64748b; margin-top: 8px; display: flex; align-items: flex-start; gap: 6px; }
.hint-text i { margin-top: 1px; flex-shrink: 0; }
.hint-text span { flex: 1; min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }

.items-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.items__header, .item-row {
  display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1.4fr) 90px 52px 26px;
  gap: 8px; align-items: center;
}
.items__header { font-size: 11px; font-weight: 700; text-transform: uppercase; color: #94a3b8; padding: 0 0 6px; border-bottom: 1px solid #f1f5f9; }
.item-row { padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
.item-row__code { font-size: 13px; font-weight: 600; color: #0f172a; overflow-wrap: anywhere; }
.item-row__uom { font-size: 12px; color: #64748b; }
@media (max-width: 520px) {
  .items__header { display: none; }
  .item-row { grid-template-columns: minmax(0, 1fr) 84px 26px; grid-template-areas: "code code rm" "batch qty uom"; row-gap: 6px; }
  .item-row__code { grid-area: code; }
  .item-row > input:first-of-type { grid-area: batch; }
  .item-row > input.num { grid-area: qty; }
  .item-row__uom { grid-area: uom; }
  .item-row > .btn-remove, .item-row > span:last-child { grid-area: rm; }
}
.btn-remove { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px; font-size: 13px; }
.btn-remove:hover { color: #dc2626; }

.totals { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; justify-content: flex-end; }
.total-chip { background: #f0fdf4; color: #166534; font-weight: 700; font-size: 13px; padding: 5px 10px; border-radius: 999px; }
.total-chip small { font-weight: 500; }

.status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; }
.stepper { display: flex; gap: 6px; margin-top: 14px; }
.step { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.step__dot { height: 6px; border-radius: 3px; background: #e2e8f0; }
.step--done .step__dot { background: var(--app-primary, #0f6e56); }
.step__label { font-size: 11px; color: #94a3b8; font-weight: 600; }
.step--done .step__label { color: #0f172a; }

.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid #e2e8f0; background: #fff; color: #475569; border-radius: 999px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.chip--active { background: var(--app-primary, #0f6e56); border-color: var(--app-primary, #0f6e56); color: #fff; }

.req-card {
  text-align: left; width: 100%; border: none; cursor: pointer; font-family: inherit;
  background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  display: flex; flex-direction: column; gap: 6px;
}
.req-card:active { transform: scale(0.995); }
.req-card__top, .req-card__meta, .req-card__foot { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.req-card__name { font-weight: 700; color: #0f172a; font-size: 15px; }
.req-card__to { font-size: 14px; color: #334155; display: flex; gap: 6px; align-items: center; }
.req-card__meta { font-size: 12px; color: #64748b; }
.req-card__foot { font-size: 12px; }

.pill { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap; background: #f1f5f9; color: #475569; display: inline-block; }
.pill--grey { background: #f1f5f9; color: #475569; }
.pill--blue { background: #dbeafe; color: #1e40af; }
.pill--amber { background: #fef3c7; color: #92400e; }
.pill--green { background: #dcfce7; color: #166534; }

.empty { text-align: center; color: #94a3b8; padding: 28px 12px; font-size: 14px; }
.empty--inline { padding: 18px 8px; }

.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; padding: 0 14px; white-space: nowrap; }
.btn-outline:disabled { border-color: #cbd5e1; color: #94a3b8; cursor: not-allowed; }
.btn-full { width: 100%; padding: 12px; }

.error-banner {
  background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px;
}

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 20px; }
.modal-box { background: #fff; border-radius: 14px; padding: 28px 24px; width: 100%; max-width: 360px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.modal-icon { font-size: 40px; color: #16a34a; margin-bottom: 10px; display: block; }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 12px; color: #0f172a; }
.modal-docno { font-size: 15px; font-weight: 700; color: #0f6e56; background: #f0fdf4; border-radius: 8px; padding: 10px 14px; margin-bottom: 18px; word-break: break-all; }
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>
