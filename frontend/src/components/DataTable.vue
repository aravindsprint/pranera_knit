<template>
  <div class="dt-wrap">
    <table class="dt">
      <thead>
        <tr>
          <th
            v-for="c in columns" :key="c.key"
            :class="{ 'dt-num': isNum(c), 'dt-sorted': sortKey === c.key }"
            :style="c.minWidth ? { minWidth: c.minWidth } : null"
            @click="sortBy(c.key)"
          >
            {{ c.label }}<span class="dt-arrow">{{ sortKey === c.key ? (sortDir === 1 ? '▲' : '▼') : '' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!sorted.length"><td :colspan="columns.length" class="dt-empty">{{ emptyText }}</td></tr>
        <tr v-for="(r, i) in sorted" :key="rowKey ? rowKey(r) : i" :class="rowClass ? rowClass(r) : null">
          <td v-for="c in columns" :key="c.key" :class="{ 'dt-num': isNum(c) }">
            <slot :name="`cell-${c.key}`" :row="r" :value="cellValue(c, r)">{{ formatCell(c, cellValue(c, r)) }}</slot>
          </td>
        </tr>
      </tbody>
      <tfoot v-if="totals && sorted.length">
        <tr>
          <td v-for="(c, i) in columns" :key="c.key" :class="{ 'dt-num': isNum(c) }">
            <template v-if="i === 0">Total ({{ sorted.length }})</template>
            <template v-else-if="c.total">{{ formatCell(c, totalOf(c)) }}</template>
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { cellValue, formatCell, parseDT } from '@/utils/tableExport'

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, required: true },
  rowKey: { type: Function, default: null },
  rowClass: { type: Function, default: null },
  totals: { type: Boolean, default: false },
  emptyText: { type: String, default: 'No rows.' },
})

const sortKey = ref(null)
const sortDir = ref(1)

const isNum = c => ['num', 'int', 'pct'].includes(c.type)

function sortBy(key) {
  if (sortKey.value === key) {
    if (sortDir.value === 1) sortDir.value = -1
    else { sortKey.value = null; sortDir.value = 1 }
  } else {
    sortKey.value = key
    sortDir.value = 1
  }
}

const sorted = computed(() => {
  if (!sortKey.value) return props.rows
  const c = props.columns.find(x => x.key === sortKey.value)
  if (!c) return props.rows
  const key = r => {
    const v = cellValue(c, r)
    if (v === null || v === undefined || v === '') return null
    if (isNum(c)) return Number(v) || 0
    if (c.type === 'date' || c.type === 'datetime') return parseDT(v)?.getTime() ?? null
    return String(v).toLowerCase()
  }
  return [...props.rows].sort((a, b) => {
    const x = key(a), y = key(b)
    if (x === y) return 0
    if (x === null) return 1          // blanks always last
    if (y === null) return -1
    return (x < y ? -1 : 1) * sortDir.value
  })
})

function totalOf(c) {
  return sorted.value.reduce((s, r) => s + (Number(cellValue(c, r)) || 0), 0)
}

// Rows in the order shown, so exports can follow the on-screen sort.
defineExpose({ sortedRows: sorted })
</script>

<style scoped>
.dt-wrap {
  background: white; border: 1px solid #e2e8f0; border-radius: 12px; overflow: auto;
  max-height: calc(100vh - 230px); box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.dt { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 12.5px; font-variant-numeric: tabular-nums; }
.dt th {
  position: sticky; top: 0; z-index: 1; background: #0f172a; color: white; text-align: left;
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  padding: 9px 10px; white-space: nowrap; cursor: pointer; user-select: none;
}
.dt th.dt-sorted { background: var(--app-primary, #059669); }
.dt-arrow { font-size: 9px; margin-left: 4px; }
.dt td { padding: 7px 10px; border-bottom: 1px solid #f1f5f9; white-space: nowrap; color: #1e293b; }
.dt tbody tr:nth-child(even) td { background: #f8fafc; }
.dt tbody tr:hover td { background: #ecfdf5; }
.dt-num { text-align: right !important; }
.dt-empty { text-align: center; color: #94a3b8; padding: 28px !important; }
.dt tfoot td {
  position: sticky; bottom: 0; background: #e2e8f0; font-weight: 800; border-top: 2px solid #94a3b8;
}
</style>
