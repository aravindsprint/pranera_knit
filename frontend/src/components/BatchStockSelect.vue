<template>
  <div class="bs" ref="rootEl">
    <div class="bs-wrap">
      <input
        v-model="query"
        type="text"
        class="form-input form-input--sm bs-input"
        :class="{ 'bs-input--with-wh': !open && warehouse }"
        :placeholder="placeholder"
        :title="batch ? `${batch} @ ${warehouse || '—'}` : ''"
        :disabled="disabled"
        autocomplete="off"
        @focus="onFocus"
        @input="onInput"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="chooseHighlighted"
        @keydown.esc="close(true)"
        @blur="onBlur"
      />
      <span v-if="!open && warehouse" class="bs-wh-tag"><i class="pi pi-map-marker"></i>{{ shortWh(warehouse) }}</span>
      <button v-if="batch && !disabled" type="button" class="bs-clear" tabindex="-1" title="Clear batch" @mousedown.prevent="choose(null)">
        <i class="pi pi-times"></i>
      </button>
      <i v-else class="pi pi-chevron-down bs-chevron"></i>
    </div>

    <div v-if="open" class="bs-panel">
      <div v-if="loading" class="bs-empty"><i class="pi pi-spin pi-spinner"></i> Loading stock…</div>
      <template v-else>
        <div
          v-for="(o, idx) in options" :key="o.batch + '|' + o.warehouse"
          class="bs-option"
          :class="{
            'bs-option--active': idx === highlighted,
            'bs-option--selected': o.batch === batch && o.warehouse === warehouse,
            'bs-option--full': o.available_qty <= 0,
          }"
          @mousedown.prevent="choose(o)" @mousemove="highlighted = idx"
        >
          <div class="bs-option__line">
            <span class="bs-option__name">{{ o.batch }}</span>
            <span class="bs-option__free" :class="{ 'bs-option__free--none': o.available_qty <= 0 }">
              {{ fmt(o.available_qty) }} {{ o.stock_uom }} free
            </span>
          </div>
          <div class="bs-option__line bs-option__sub">
            <span class="bs-option__wh"><i class="pi pi-map-marker"></i> {{ o.warehouse }}</span>
            <span class="bs-option__nums">
              Stock {{ fmt(o.stock_qty) }}<template v-if="o.reserved_qty > 0"> · <b class="bs-res">Reserved {{ fmt(o.reserved_qty) }}</b></template>
            </span>
          </div>
          <div v-if="o.reservations.length" class="bs-option__res">
            {{ o.reservations.slice(0, 3).map(r => `${r.outward_request} (${r.work_order || r.purchase_order}) ${fmt(r.qty)}`).join(' · ') }}<template v-if="o.reservations.length > 3"> · +{{ o.reservations.length - 3 }} more</template>
          </div>
          <div v-if="o.unallocated_qty > 0" class="bs-option__res bs-option__res--muted">
            +{{ fmt(o.unallocated_qty) }} reserved on this batch with no warehouse set
          </div>
        </div>
        <div v-if="loadError" class="bs-empty bs-error"><i class="pi pi-exclamation-triangle"></i> Couldn't load batches: {{ loadError }}</div>
        <div v-else-if="!options.length" class="bs-empty">
          No stock of this item<template v-if="workOrder || purchaseOrder"> in this {{ workOrder ? 'Work Order' : 'PO' }}'s project</template><template v-if="fromBuilding"> in {{ fromBuilding }}'s warehouses</template><template v-if="query"> matching "{{ query }}"</template>.
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// Batch + warehouse picker for one Outward Request row. Each option is a
// (batch, warehouse) pair holding stock of `itemCode` — limited to the
// source document's project and the From building's warehouses — showing
// stock, what other open Outward Requests have reserved there, and what's
// free. Only a picked option is accepted; free text is discarded on blur.
//   v-model:batch, v-model:warehouse, and @pick(option) with the numbers.
import { ref, watch, onBeforeUnmount } from 'vue'
import { searchBatchStock } from '@/api/frappe'

const props = defineProps({
  batch: { type: String, default: '' },
  warehouse: { type: String, default: '' },
  itemCode: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Select batch…' },
  workOrder: { type: String, default: '' },
  purchaseOrder: { type: String, default: '' },
  fromBuilding: { type: String, default: '' },
  excludeRequest: { type: String, default: '' },
})
const emit = defineEmits(['update:batch', 'update:warehouse', 'pick'])

const rootEl = ref(null)
const query = ref(props.batch || '')
const open = ref(false)
const loading = ref(false)
const options = ref([])
const loadError = ref('')
const highlighted = ref(-1)
let timer = null
let seq = 0

watch(() => props.batch, (v) => { if (!open.value) query.value = v || '' })

async function load(txt) {
  const mine = ++seq
  loading.value = true
  loadError.value = ''
  try {
    const rows = await searchBatchStock(props.itemCode, txt, {
      workOrder: props.workOrder, purchaseOrder: props.purchaseOrder,
      fromBuilding: props.fromBuilding, excludeRequest: props.excludeRequest,
    })
    if (mine !== seq) return
    options.value = rows
    highlighted.value = rows.length ? 0 : -1
  } catch (e) {
    if (mine === seq) { options.value = []; loadError.value = e?.message || 'server error' }
  } finally {
    if (mine === seq) loading.value = false
  }
}

function onFocus() {
  if (props.disabled) return
  open.value = true
  load(query.value && query.value !== props.batch ? query.value : '')
}
function onInput() {
  open.value = true
  clearTimeout(timer)
  timer = setTimeout(() => load(query.value.trim()), 250)
}
function move(d) {
  if (!open.value) return onFocus()
  const n = options.value.length
  if (n) highlighted.value = (highlighted.value + d + n) % n
}
function chooseHighlighted() {
  const o = options.value[highlighted.value]
  if (o) choose(o)
}
function choose(o) {
  emit('update:batch', o ? o.batch : '')
  emit('update:warehouse', o ? o.warehouse : '')
  emit('pick', o || null)
  query.value = o ? o.batch : ''
  close(false)
}
function close(restore) {
  open.value = false
  clearTimeout(timer)
  if (restore) query.value = props.batch || ''
}
function onBlur() {
  setTimeout(() => close(true), 120)
}
// "NAP_E1/GF/D09 - PSS" → "NAP_E1/GF/D09" for the compact tag.
function shortWh(w) {
  return String(w || '').replace(/ - [A-Z0-9]+$/, '')
}
function fmt(n) {
  return (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 3 })
}
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.bs { position: relative; min-width: 0; }
.bs-wrap { position: relative; }
.bs-input { width: 100%; padding-right: 28px; text-overflow: ellipsis; }
.bs-input--with-wh { padding-bottom: 20px; }
.bs-wh-tag {
  position: absolute; left: 9px; bottom: 4px; right: 28px; font-size: 11px; color: #0f6e56; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; pointer-events: none;
  display: flex; gap: 4px; align-items: center;
}
.bs-wh-tag i { font-size: 10px; }
.bs-chevron, .bs-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 11px; color: #94a3b8;
}
.bs-chevron { pointer-events: none; }
.bs-clear { background: none; border: none; padding: 2px; cursor: pointer; }
.bs-clear:hover { color: #dc2626; }
.bs-panel {
  position: absolute; z-index: 60; top: calc(100% + 4px); left: 0; min-width: 100%; width: max-content; max-width: min(480px, 92vw);
  max-height: 320px; overflow-y: auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
}
.bs-option { padding: 8px 10px; font-size: 13px; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; flex-direction: column; gap: 2px; }
.bs-option--active { background: #f0fdf4; }
.bs-option--full { opacity: 0.75; }
.bs-option--selected .bs-option__name { font-weight: 700; color: #0f6e56; }
.bs-option__line { display: flex; justify-content: space-between; gap: 14px; align-items: baseline; }
.bs-option__name { color: #0f172a; overflow-wrap: anywhere; }
.bs-option__free { font-size: 12px; font-weight: 700; color: #166534; white-space: nowrap; }
.bs-option__free--none { color: #dc2626; }
.bs-option__sub { font-size: 11.5px; color: #64748b; }
.bs-option__wh { display: flex; gap: 4px; align-items: center; overflow-wrap: anywhere; }
.bs-option__wh i { font-size: 10px; }
.bs-option__nums { white-space: nowrap; }
.bs-res { color: #b45309; font-weight: 700; }
.bs-option__res { font-size: 11px; color: #92400e; overflow-wrap: anywhere; }
.bs-option__res--muted { color: #94a3b8; }
.bs-empty { padding: 10px; font-size: 12px; color: #94a3b8; }
.bs-error { color: #dc2626; }
</style>
