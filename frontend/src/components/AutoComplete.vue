<template>
  <div class="ac" ref="rootEl">
    <div class="ac-input-wrap">
      <input
        ref="inputEl"
        v-model="query"
        type="text"
        class="form-input ac-input"
        :placeholder="placeholder"
        :disabled="disabled"
        autocomplete="off"
        @focus="onFocus"
        @input="onInput"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter.prevent="chooseHighlighted"
        @keydown.esc="close"
      />
      <button
        v-if="query && !disabled"
        type="button"
        class="ac-clear"
        tabindex="-1"
        @click="clearSelection"
      >
        <i class="pi pi-times"></i>
      </button>
      <i class="pi pi-chevron-down ac-chevron" :class="{ 'ac-chevron--open': open }"></i>
    </div>

    <div v-if="open" class="ac-panel">
      <div
        v-for="(opt, idx) in filteredOptions"
        :key="opt.value"
        class="ac-option"
        :class="{ 'ac-option--active': idx === highlightedIndex, 'ac-option--selected': opt.value === modelValue }"
        @mousedown.prevent="choose(opt)"
        @mousemove="highlightedIndex = idx"
      >
        {{ opt.label }}
      </div>
      <div v-if="!filteredOptions.length" class="ac-empty">
        No matches{{ query ? ` for "${query}"` : '' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] }, // items are strings or { label, value }
  placeholder: { type: String, default: 'Search...' },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'change'])

const rootEl = ref(null)
const inputEl = ref(null)
const query = ref('')
const open = ref(false)
const highlightedIndex = ref(-1)

const normalizedOptions = computed(() =>
  props.options.map(o => (typeof o === 'string' ? { label: o, value: o } : { label: o.label ?? o.value, value: o.value }))
)

const filteredOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return normalizedOptions.value
  return normalizedOptions.value.filter(o => o.label.toLowerCase().includes(q))
})

function labelForValue(val) {
  const match = normalizedOptions.value.find(o => o.value === val)
  return match ? match.label : (val || '')
}

// Keep the visible text in sync with the selected value from outside
watch(
  () => props.modelValue,
  (val) => {
    if (val !== selectedValueOfQuery()) {
      query.value = val ? labelForValue(val) : ''
    }
  },
  { immediate: true }
)

// Track whether the current query text corresponds to the current modelValue
function selectedValueOfQuery() {
  return query.value === labelForValue(props.modelValue) ? props.modelValue : undefined
}

function onFocus() {
  if (disabledCheck()) return
  open.value = true
  highlightedIndex.value = Math.max(
    0,
    normalizedOptions.value.findIndex(o => o.value === props.modelValue)
  )
  nextTick(scrollHighlightedIntoView)
}

function disabledCheck() {
  return props.disabled
}

function onInput() {
  open.value = true
  highlightedIndex.value = filteredOptions.value.length ? 0 : -1
  // Clear selection if the text no longer matches the selected option's label
  if (query.value !== labelForValue(props.modelValue)) {
    emit('update:modelValue', '')
  }
}

function move(delta) {
  if (!open.value) {
    open.value = true
    nextTick(scrollHighlightedIntoView)
    return
  }
  const len = filteredOptions.value.length
  if (!len) return
  highlightedIndex.value = (highlightedIndex.value + delta + len) % len
  nextTick(scrollHighlightedIntoView)
}

function scrollHighlightedIntoView() {
  const panel = rootEl.value?.querySelector('.ac-panel')
  const active = panel?.querySelector('.ac-option--active')
  if (active && panel) {
    const top = active.offsetTop
    const bottom = top + active.offsetHeight
    if (top < panel.scrollTop) panel.scrollTop = top
    else if (bottom > panel.scrollTop + panel.clientHeight) panel.scrollTop = bottom - panel.clientHeight
  }
}

function chooseHighlighted() {
  const opt = filteredOptions.value[highlightedIndex.value]
  if (opt) choose(opt)
  else close()
}

function choose(opt) {
  query.value = opt.label
  emit('update:modelValue', opt.value)
  emit('change', opt.value)
  close()
}

function clearSelection() {
  query.value = ''
  emit('update:modelValue', '')
  emit('change', '')
  inputEl.value?.focus()
  open.value = true
}

function close() {
  open.value = false
  // Snap the visible text back to the actual selection (or clear it)
  query.value = props.modelValue ? labelForValue(props.modelValue) : ''
}

function onClickOutside(e) {
  if (rootEl.value && !rootEl.value.contains(e.target)) close()
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<style scoped>
.ac { position: relative; width: 100%; }
.ac-input-wrap { position: relative; display: flex; align-items: center; }
.ac-input { padding-right: 60px; }
.ac-clear {
  position: absolute;
  right: 30px;
  background: none;
  border: none;
  color: var(--slate-400);
  font-size: 12px;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ac-clear:hover { color: var(--slate-700); }
.ac-chevron {
  position: absolute;
  right: 13px;
  font-size: 11px;
  color: var(--slate-400);
  pointer-events: none;
  transition: transform 0.15s;
}
.ac-chevron--open { transform: rotate(180deg); }

.ac-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  background: white;
  border: 1.5px solid var(--slate-200);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 200;
  padding: 4px;
}
.ac-option {
  padding: 10px 12px;
  font-size: 14px;
  color: var(--slate-900);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.ac-option--active { background: var(--green-50); color: var(--green-700); }
.ac-option--selected { font-weight: 700; }
.ac-empty {
  padding: 12px;
  font-size: 13px;
  color: var(--slate-400);
  text-align: center;
}
</style>
