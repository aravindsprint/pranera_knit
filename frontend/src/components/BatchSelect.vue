<template>
  <div class="bs" ref="rootEl">
    <div class="bs-wrap">
      <input
        v-model="query"
        type="text"
        class="form-input form-input--sm bs-input"
        :placeholder="placeholder"
        :title="modelValue || ''"
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
      <button v-if="modelValue && !disabled" type="button" class="bs-clear" tabindex="-1" title="Clear batch" @mousedown.prevent="choose(null)">
        <i class="pi pi-times"></i>
      </button>
      <i v-else class="pi pi-chevron-down bs-chevron"></i>
    </div>

    <div v-if="open" class="bs-panel">
      <div v-if="loading" class="bs-empty"><i class="pi pi-spin pi-spinner"></i> Loading batches…</div>
      <template v-else>
        <div
          v-for="(b, idx) in options" :key="b.name"
          class="bs-option" :class="{ 'bs-option--active': idx === highlighted, 'bs-option--selected': b.name === modelValue }"
          @mousedown.prevent="choose(b)" @mousemove="highlighted = idx"
        >
          <span class="bs-option__name">{{ b.name }}</span>
          <span class="bs-option__qty" :class="{ 'bs-option__qty--zero': !(b.batch_qty > 0) }">
            {{ fmt(b.batch_qty) }} {{ b.stock_uom || '' }}
          </span>
        </div>
        <div v-if="!options.length" class="bs-empty">
          No batches for this item{{ query ? ` matching "${query}"` : '' }}.
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// Batch picker for one item row: a Link to the Batch doctype, limited to
// batches of `itemCode` (searched on the server — there are 100k+ batches),
// in-stock first with their available qty. Only a value picked from the
// list is accepted; typing something else and leaving the field restores
// the previous value.
import { ref, watch, onBeforeUnmount } from 'vue'
import { searchBatchesForItem } from '@/api/frappe'

const props = defineProps({
  modelValue: { type: String, default: '' },
  itemCode: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Select batch…' },
})
const emit = defineEmits(['update:modelValue'])

const rootEl = ref(null)
const query = ref(props.modelValue || '')
const open = ref(false)
const loading = ref(false)
const options = ref([])
const highlighted = ref(-1)
let timer = null
let seq = 0

watch(() => props.modelValue, (v) => { if (!open.value) query.value = v || '' })

async function load(txt) {
  const mine = ++seq
  loading.value = true
  try {
    const rows = await searchBatchesForItem(props.itemCode, txt)
    if (mine !== seq) return
    options.value = rows
    highlighted.value = rows.length ? 0 : -1
  } catch {
    if (mine === seq) options.value = []
  } finally {
    if (mine === seq) loading.value = false
  }
}

function onFocus() {
  if (props.disabled) return
  open.value = true
  // Show this item's batches straight away, not just ones matching the
  // already-selected batch name.
  load(query.value && query.value !== props.modelValue ? query.value : '')
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
  const b = options.value[highlighted.value]
  if (b) choose(b)
}
function choose(b) {
  emit('update:modelValue', b ? b.name : '')
  query.value = b ? b.name : ''
  close(false)
}
function close(restore) {
  open.value = false
  clearTimeout(timer)
  if (restore) query.value = props.modelValue || ''
}
function onBlur() {
  // Free text that wasn't picked from the list is never kept.
  setTimeout(() => close(true), 120)
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
.bs-chevron, .bs-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 11px; color: #94a3b8;
}
.bs-chevron { pointer-events: none; }
.bs-clear { background: none; border: none; padding: 2px; cursor: pointer; }
.bs-clear:hover { color: #dc2626; }
.bs-panel {
  position: absolute; z-index: 60; top: calc(100% + 4px); left: 0; min-width: 100%; width: max-content; max-width: min(420px, 86vw);
  max-height: 260px; overflow-y: auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
}
.bs-option {
  display: flex; justify-content: space-between; gap: 14px; align-items: baseline;
  padding: 8px 10px; font-size: 13px; cursor: pointer; border-bottom: 1px solid #f8fafc;
}
.bs-option--active { background: #f0fdf4; }
.bs-option--selected .bs-option__name { font-weight: 700; color: #0f6e56; }
.bs-option__name { color: #0f172a; overflow-wrap: anywhere; }
.bs-option__qty { font-size: 12px; font-weight: 600; color: #166534; white-space: nowrap; }
.bs-option__qty--zero { color: #94a3b8; font-weight: 400; }
.bs-empty { padding: 10px; font-size: 12px; color: #94a3b8; }
</style>
