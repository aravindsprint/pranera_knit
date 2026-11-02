<template>
  <div class="page">
    <AppHeader title="Needle / Sinker Issue" active="spares-issue" :username="auth.username" :designation="auth.designation" :show-back="true" />

    <div class="page-content si">

      <div v-if="setupLoading" class="loading-center"><div class="spinner"></div>Loading machines…</div>
      <div v-else-if="setupError" class="alert alert-error"><i class="pi pi-exclamation-triangle"></i> {{ setupError }}</div>

      <template v-else>
        <div v-if="!setup.can_issue" class="alert alert-warning">
          <i class="pi pi-lock"></i>
          You can view this page, but issuing needs Stock Entry create + submit permission (Stock User). Ask the ERP admin.
        </div>

        <!-- ── Success banner ── -->
        <div v-if="result" class="card result">
          <div class="result__head"><i class="pi pi-check-circle"></i> {{ result.issue_type === 'Full Set Change' ? 'Full set changed on' : 'Issued to' }} {{ result.workstation }}</div>
          <div class="result__docs">
            <div><span class="muted">Asset Repair</span> <b>{{ result.asset_repair }}</b></div>
            <div v-if="result.stock_entry"><span class="muted">Material Issue</span> <b>{{ result.stock_entry }}</b></div>
            <div><span class="muted">Value</span> <b>₹{{ fmtMoney(result.total_value) }}</b></div>
          </div>
          <button class="btn-link" @click="result = null">Dismiss</button>
        </div>

        <!-- ── 1. Machine ── -->
        <div class="card">
          <div class="section-title">1 · Machine</div>
          <AutoComplete v-model="machine" :options="machineOptions" placeholder="Search machine (SJ05, IL02, FK11…)" @update:modelValue="onMachinePicked" />

          <div v-if="machineRow" class="machine">
            <div class="machine__meta">
              <span class="chip">{{ machineRow.workstation_type || machineGroup(machineRow.workstation) }}</span>
              <span v-if="machineRow.status" class="chip chip--muted">{{ machineRow.status }}</span>
            </div>

            <div v-if="machineRow.asset && !changingAsset" class="asset asset--ok">
              <i class="pi pi-cog"></i>
              <div class="asset__text">
                <div class="asset__id">{{ machineRow.asset }}</div>
                <div class="asset__name">{{ machineRow.asset_name }}</div>
              </div>
              <button v-if="setup.can_change_asset" class="btn-link" @click="startChangeAsset">Change</button>
            </div>

            <div v-else class="asset asset--missing">
              <div class="asset__warn">
                <i class="pi pi-exclamation-circle"></i>
                <span v-if="changingAsset">Pick the correct asset for {{ machineRow.workstation }}.</span>
                <span v-else>{{ machineRow.workstation }} is not linked to its Asset yet. Pick it once — it's remembered for next time.</span>
              </div>
              <AutoComplete v-model="assetPick" :options="assetOptions" placeholder="Search asset (PSS/2023-215, Fukuhara…)" />
              <div class="asset__actions">
                <button v-if="changingAsset" class="btn btn-ghost" @click="changingAsset = false">Cancel</button>
                <button class="btn btn-outline" :disabled="!assetPick || linking" @click="doLinkAsset">
                  <i class="pi" :class="linking ? 'pi-spin pi-spinner' : 'pi-link'"></i> Link to {{ machineRow.workstation }}
                </button>
              </div>
            </div>

            <!-- Needle / sinker life (tracked items only) -->
            <div v-if="lifeItems.length" class="life">
              <div class="form-label">Needle life since last full set</div>
              <div v-for="l in lifeItems" :key="l.item_code" class="life__row">
                <div class="life__top">
                  <span class="life__code">{{ shortCode(l.item_code) }}</span>
                  <span v-if="l.produced == null" class="muted small">Not started</span>
                  <span v-else class="life__val" :class="'life__val--' + (l.level || 'ok').toLowerCase()">
                    {{ fmtQty(l.produced) }} / {{ fmtQty(l.max_production) }} kg · {{ Math.round(l.pct) }}%
                  </span>
                </div>
                <div v-if="l.produced != null" class="life__bar">
                  <div class="life__fill" :class="'life__fill--' + (l.level || 'ok').toLowerCase()" :style="{ width: Math.min(l.pct, 100) + '%' }"></div>
                </div>
                <div class="muted small">
                  <template v-if="l.last_full_set_on">Since {{ fmtDate(l.last_full_set_on) }} · </template>
                  Full set {{ l.set_qty }} pcs · store {{ fmtQty(l.qty) }}
                  <b v-if="l.set_qty && l.qty < l.set_qty" class="short">short {{ l.set_qty - l.qty }}</b>
                </div>
              </div>
              <div v-if="lifeItems.some(l => l.produced == null)" class="muted small">
                "Not started": record a Full Set Change here, or enter Last Full Set Change in Workstation → Spare Items.
              </div>
            </div>
          </div>
        </div>

        <!-- ── 2. Items ── -->
        <div class="card" :class="{ 'card--dim': !machineRow }">
          <div class="section-title section-title--row">
            <span>2 · Needles / Sinkers</span>
            <button class="btn-icon" :disabled="stockLoading || !machine" title="Refresh stock" @click="loadMachine">
              <i class="pi" :class="stockLoading ? 'pi-spin pi-spinner' : 'pi-refresh'"></i>
            </button>
          </div>
          <div class="muted small src">From {{ setup.source_warehouse }}<span v-if="machine"> · only items allowed on {{ machine }}</span></div>

          <div v-if="machine && machineData && machineData.can_full_set" class="segmented mode">
            <button v-for="t in setup.issue_types" :key="t" class="segmented__btn" :class="{ 'segmented__btn--active': issueType === t }" @click="setIssueType(t)">
              {{ t === 'Full Set Change' ? 'Full Set Change' : 'Broken / Bent' }}
            </button>
          </div>
          <div v-if="issueType === 'Full Set Change'" class="alert alert-info small-alert">
            <i class="pi pi-info-circle"></i> Replaces the whole set — the life count for the items you issue restarts at 0 kg.
          </div>

          <div v-if="!machine" class="muted empty">Select a machine to see the needles / sinkers allowed on it.</div>
          <div v-else-if="machineData && !machineData.mapped" class="alert alert-warning">
            <i class="pi pi-exclamation-circle"></i> No needles / sinkers are set up for {{ machine }}. Ask the knitting team to fill Workstation → Spare Items.
          </div>

          <div v-if="frequentItems.length && issueType !== 'Full Set Change'" class="frequent">
            <div class="form-label">Often used on {{ machine }}</div>
            <div class="frequent__chips">
              <button v-for="code in frequentItems" :key="code" class="chip chip--btn" :disabled="!stockByCode[code]" @click="addItem(code)">
                + {{ shortCode(code) }}
              </button>
            </div>
          </div>

          <div v-if="stock.length > 4" class="filters">
            <input v-model="search" class="form-input" type="search" placeholder="Search needle no., item code…" />
            <div class="segmented">
              <button v-for="k in ['All', 'Needle', 'Sinker']" :key="k" class="segmented__btn" :class="{ 'segmented__btn--active': kind === k }" @click="kind = k">{{ k }}</button>
            </div>
          </div>

          <div v-if="stockError" class="alert alert-error"><i class="pi pi-exclamation-triangle"></i> {{ stockError }}</div>
          <div v-else-if="machine && machineData?.mapped && !filteredStock.length && !stockLoading" class="muted empty">No matching needles / sinkers.</div>

          <div class="stock-list">
            <div v-for="it in filteredStock" :key="it.item_code" class="stock-row" :class="{ 'stock-row--in': cart[it.item_code], 'stock-row--out': !it.qty }">
              <div class="stock-row__main" @click="addItem(it.item_code)">
                <div class="stock-row__top">
                  <span class="kind" :class="'kind--' + it.kind.toLowerCase()">{{ it.kind }}</span>
                  <span class="stock-row__code">{{ shortCode(it.item_code) }}</span>
                  <span v-if="it.has_batch_no" class="kind kind--batch">Batch</span>
                  <span v-if="it.level" class="kind" :class="'kind--' + it.level.toLowerCase()">{{ it.level === 'Max' ? 'Life over' : 'Life ' + Math.round(it.pct) + '%' }}</span>
                </div>
                <div class="stock-row__name">{{ it.item_name }}</div>
                <div v-if="issueType === 'Full Set Change' && it.set_qty" class="stock-row__set" :class="{ short: it.qty < it.set_qty }">
                  Full set {{ it.set_qty }} pcs<span v-if="it.qty < it.set_qty"> · store short by {{ it.set_qty - it.qty }}</span>
                </div>
              </div>
              <div class="stock-row__side">
                <div class="stock-row__qty">{{ fmtQty(it.qty) }} <small>{{ it.stock_uom }}</small></div>
                <div v-if="cart[it.item_code]" class="stepper">
                  <button @click="step(it.item_code, -1)"><i class="pi pi-minus"></i></button>
                  <input v-model.number="cart[it.item_code]" type="number" inputmode="numeric" min="1" :max="it.qty" @blur="clampQty(it.item_code)" />
                  <button @click="step(it.item_code, 1)"><i class="pi pi-plus"></i></button>
                </div>
                <button v-else class="btn btn-outline btn-add" :disabled="!machineRow || !it.qty" @click="addItem(it.item_code)">{{ it.qty ? 'Add' : 'No stock' }}</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── 3. Reason + submit ── -->
        <div class="card" :class="{ 'card--dim': !cartRows.length }">
          <div class="section-title">3 · {{ issueType === 'Full Set Change' ? 'Confirm' : 'Reason' }}</div>
          <div v-if="issueType !== 'Full Set Change'" class="reasons">
            <button v-for="r in setup.reasons" :key="r" class="chip chip--btn" :class="{ 'chip--active': reason === r }" @click="reason = r">{{ r }}</button>
          </div>
          <label class="form-label" style="margin-top:12px">Remarks</label>
          <textarea v-model="remarks" class="form-input" rows="2" placeholder="Track, feeder, what happened… (optional)"></textarea>

          <div v-if="cartRows.length" class="summary">
            <div v-for="r in cartRows" :key="r.item_code" class="summary__row">
              <span>{{ shortCode(r.item_code) }}</span>
              <span>{{ r.qty }} × ₹{{ fmtMoney(r.rate) }}</span>
              <button class="btn-icon" title="Remove" @click="removeItem(r.item_code)"><i class="pi pi-times"></i></button>
            </div>
            <div class="summary__total"><span>{{ totalQty }} pcs</span><span>₹{{ fmtMoney(totalValue) }}</span></div>
          </div>

          <div v-if="submitError" class="alert alert-error" style="margin-top:12px"><i class="pi pi-exclamation-triangle"></i> {{ submitError }}</div>

          <button class="btn btn-primary btn-full btn-lg" style="margin-top:14px" :disabled="!canSubmit" @click="confirming = true">
            <i class="pi pi-send"></i> {{ issueType === 'Full Set Change' ? 'Change full set on' : 'Issue to' }} {{ machine || 'machine' }}
          </button>
          <div v-if="blockReason" class="muted small center" style="margin-top:8px">{{ blockReason }}</div>
        </div>

        <!-- ── Recent issues ── -->
        <div v-if="machineRow" class="card">
          <div class="section-title">Recent issues · {{ machine }}</div>
          <div v-if="recentLoading" class="muted small"><i class="pi pi-spin pi-spinner"></i> Loading…</div>
          <div v-else-if="!recent.length" class="muted small">No needle / sinker issues recorded for this machine yet.</div>
          <div v-for="r in recent" :key="r.name" class="recent">
            <div class="recent__top">
              <b>{{ r.name }} <span v-if="r.issue_type === 'Full Set Change'" class="chip chip--set">Full set</span></b>
              <span class="muted small">{{ fmtDate(r.completion_date) }}</span>
            </div>
            <div class="recent__items">
              <span v-for="it in r.items" :key="it.item_code" class="chip chip--muted">{{ shortCode(it.item_code) }} × {{ fmtQty(it.qty) }}</span>
            </div>
            <div class="muted small">{{ r.issued_by }}<span v-if="r.stock_entry"> · {{ r.stock_entry }}</span> · ₹{{ fmtMoney(r.total_repair_cost) }}</div>
          </div>
        </div>
      </template>
    </div>

    <!-- ── Confirm sheet ── -->
    <div v-if="confirming" class="sheet-backdrop" @click.self="confirming = false">
      <div class="sheet">
        <div class="sheet__title">{{ issueType === 'Full Set Change' ? 'Full set change on' : 'Issue to' }} {{ machine }}?</div>
        <div class="muted small">Asset {{ machineRow?.asset }} · {{ issueType === 'Full Set Change' ? 'life count restarts at 0 kg' : reason }}</div>
        <div class="sheet__list">
          <div v-for="r in cartRows" :key="r.item_code" class="summary__row">
            <span>{{ shortCode(r.item_code) }}</span><b>{{ r.qty }} pcs</b>
          </div>
        </div>
        <div class="muted small">This submits an Asset Repair and a Material Issue from {{ setup.source_warehouse }}. It can only be undone by cancelling them in ERPNext.</div>
        <div class="sheet__actions">
          <button class="btn btn-ghost" :disabled="submitting" @click="confirming = false">Back</button>
          <button class="btn btn-primary" :disabled="submitting" @click="submit">
            <i class="pi" :class="submitting ? 'pi-spin pi-spinner' : 'pi-check'"></i> Confirm issue
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getSparesIssueSetup, getSparesMachine, searchMachineAssets, linkMachineAsset,
  getRecentSpareIssues, issueSpares,
} from '@/api/frappe'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'

const auth = useAuthStore()
const route = useRoute()

const setup = reactive({ machines: [], reasons: [], issue_types: [], source_warehouse: '', can_change_asset: false, can_issue: false })
const setupLoading = ref(true)
const setupError = ref('')

const machine = ref('')
const assets = ref([])
const assetPick = ref('')
const changingAsset = ref(false)
const linking = ref(false)

const machineData = ref(null)
const issueType = ref('Broken / Bent Replacement')
const stock = computed(() => {
  const items = machineData.value?.items || []
  return issueType.value === 'Full Set Change' ? items.filter(i => i.track_life) : items
})
const lifeItems = computed(() => (machineData.value?.items || []).filter(i => i.track_life))
const stockLoading = ref(false)
const stockError = ref('')
const search = ref('')
const kind = ref('All')
const cart = reactive({})

const reason = ref('')
const remarks = ref('')
const confirming = ref(false)
const submitting = ref(false)
const submitError = ref('')
const result = ref(null)

const recent = ref([])
const recentLoading = ref(false)
const frequentItems = ref([])

// ── computed ──
const machineOptions = computed(() => setup.machines.map(m => ({
  value: m.workstation,
  label: `${m.workstation}${m.asset ? '' : '  · no asset linked'}`,
})))
const machineRow = computed(() => setup.machines.find(m => m.workstation === machine.value) || null)
const assetOptions = computed(() => assets.value.map(a => ({
  value: a.name,
  label: `${a.name} · ${a.asset_name}${a.linked_workstation ? ` (linked to ${a.linked_workstation})` : ''}`,
})))
const stockByCode = computed(() => Object.fromEntries(stock.value.map(s => [s.item_code, s])))
const filteredStock = computed(() => {
  const q = search.value.trim().toLowerCase()
  return stock.value.filter(s =>
    (kind.value === 'All' || s.kind === kind.value) &&
    (!q || s.item_code.toLowerCase().includes(q) || (s.item_name || '').toLowerCase().includes(q)))
})
const cartRows = computed(() => Object.entries(cart)
  .filter(([, q]) => Number(q) > 0)
  .map(([code, q]) => ({ item_code: code, qty: Number(q), rate: stockByCode.value[code]?.valuation_rate || 0 })))
const totalQty = computed(() => cartRows.value.reduce((s, r) => s + r.qty, 0))
const totalValue = computed(() => cartRows.value.reduce((s, r) => s + r.qty * r.rate, 0))
const blockReason = computed(() => {
  if (!setup.can_issue) return 'No permission to issue.'
  if (!machineRow.value) return 'Select a machine.'
  if (!machineRow.value.asset) return 'Link the machine to its asset first.'
  if (!cartRows.value.length) return 'Add at least one needle / sinker.'
  if (cartRows.value.some(r => r.qty > (stockByCode.value[r.item_code]?.qty || 0) || r.qty !== Math.floor(r.qty)))
    return 'A quantity is more than the stock, or not a whole number.'
  if (issueType.value !== 'Full Set Change' && !reason.value) return 'Pick a reason.'
  return ''
})
const canSubmit = computed(() => !blockReason.value && !submitting.value)

// ── loading ──
onMounted(async () => {
  try {
    Object.assign(setup, await getSparesIssueSetup())
    reason.value = setup.reasons[0] || ''
  } catch (e) {
    setupError.value = e.message
  } finally {
    setupLoading.value = false
  }
  searchMachineAssets().then(a => { assets.value = a }).catch(() => {})
  const q = String(route.query.machine || '').toUpperCase()
  if (q && setup.machines.some(m => m.workstation === q)) { machine.value = q; onMachinePicked(q) }
})

async function loadMachine() {
  if (!machine.value) { machineData.value = null; return }
  const ws = machine.value
  stockLoading.value = true
  stockError.value = ''
  try {
    const d = await getSparesMachine(ws)
    if (machine.value === ws) {
      machineData.value = d
      if (!d.can_full_set) issueType.value = 'Broken / Bent Replacement'
      Object.keys(cart).forEach(k => { if (!d.items.some(i => i.item_code === k)) delete cart[k] })
    }
  } catch (e) {
    stockError.value = e.message
  } finally {
    stockLoading.value = false
  }
}

function setIssueType(t) {
  if (issueType.value === t) return
  issueType.value = t
  Object.keys(cart).forEach(k => delete cart[k])
}

async function loadRecent() {
  if (!machine.value) { recent.value = []; frequentItems.value = []; return }
  recentLoading.value = true
  try {
    const r = await getRecentSpareIssues(machine.value)
    recent.value = r.issues || []
    frequentItems.value = r.frequent_items || []
  } catch {
    recent.value = []
    frequentItems.value = []
  } finally {
    recentLoading.value = false
  }
}

function onMachinePicked() {
  machineData.value = null
  issueType.value = 'Broken / Bent Replacement'
  Object.keys(cart).forEach(k => delete cart[k])
  loadMachine()
  changingAsset.value = false
  assetPick.value = ''
  submitError.value = ''
  loadRecent()
}

function startChangeAsset() {
  changingAsset.value = true
  assetPick.value = machineRow.value?.asset || ''
}

async function doLinkAsset() {
  if (!machineRow.value || !assetPick.value) return
  linking.value = true
  submitError.value = ''
  try {
    const r = await linkMachineAsset(machineRow.value.workstation, assetPick.value)
    Object.assign(machineRow.value, { asset: r.asset, asset_name: r.asset_name })
    assets.value.forEach(a => {
      if (a.linked_workstation === r.workstation) a.linked_workstation = null
      if (a.name === r.asset) a.linked_workstation = r.workstation
    })
    changingAsset.value = false
    loadRecent()
  } catch (e) {
    submitError.value = e.message
  } finally {
    linking.value = false
  }
}

// ── cart ──
function addItem(code) {
  const it = stockByCode.value[code]
  if (!machineRow.value || !it || !it.qty) return
  if (cart[code]) return
  cart[code] = issueType.value === 'Full Set Change' && it.set_qty ? Math.min(it.set_qty, it.qty) : 1
}
function removeItem(code) { delete cart[code] }
function step(code, d) {
  const max = stockByCode.value[code]?.qty || 0
  const next = (Number(cart[code]) || 0) + d
  if (next <= 0) return removeItem(code)
  cart[code] = Math.min(next, max)
}
function clampQty(code) {
  const max = stockByCode.value[code]?.qty || 0
  let v = Math.floor(Number(cart[code]) || 0)
  if (v <= 0) return removeItem(code)
  cart[code] = Math.min(v, max)
}

// ── submit ──
async function submit() {
  submitting.value = true
  submitError.value = ''
  try {
    const r = await issueSpares({
      workstation: machineRow.value.workstation,
      asset: machineRow.value.asset,
      items: cartRows.value.map(r => ({ item_code: r.item_code, qty: r.qty })),
      reason: issueType.value === 'Full Set Change' ? undefined : reason.value,
      issue_type: issueType.value,
      remarks: remarks.value || undefined,
    })
    result.value = r
    Object.keys(cart).forEach(k => delete cart[k])
    remarks.value = ''
    confirming.value = false
    window.scrollTo({ top: 0, behavior: 'smooth' })
    issueType.value = 'Broken / Bent Replacement'
    loadMachine()
    loadRecent()
  } catch (e) {
    submitError.value = e.message
    confirming.value = false
  } finally {
    submitting.value = false
  }
}

// ── formatting ──
function shortCode(code) {
  return String(code).replace('SPARES/KNIT MAC ', '')
}
function machineGroup(ws) {
  const p = String(ws).slice(0, 2).toUpperCase()
  return p === 'SJ' ? 'Single Jersey' : p === 'IL' ? 'Interlock' : p === 'FK' ? 'Flat / Collar' : ''
}
function fmtQty(n) { return (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 }) }
function fmtMoney(n) { return (Number(n) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(String(d).replace(' ', 'T'))
  return isNaN(dt) ? d : dt.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.si { max-width: 680px; margin: 0 auto; padding: 16px; }
.muted { color: var(--slate-500); }
.small { font-size: 12px; }
.center { text-align: center; }
.empty { padding: 16px 0; text-align: center; font-size: 13px; }
.card--dim { opacity: 0.6; }
.section-title--row { display: flex; align-items: center; justify-content: space-between; }
.src { margin: -8px 0 10px; }

.btn-link { background: none; border: none; color: var(--green-700); font-weight: 600; font-size: 13px; cursor: pointer; padding: 4px 0; }
.btn-icon { background: var(--slate-100); border: none; border-radius: 8px; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; color: var(--slate-700); cursor: pointer; }
.btn-icon:disabled { opacity: 0.5; }

.chip { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: var(--green-100); color: var(--green-900); border: 1px solid transparent; }
.chip--muted { background: var(--slate-100); color: var(--slate-700); }
.chip--btn { cursor: pointer; background: #fff; border-color: var(--slate-200); color: var(--slate-700); font: inherit; font-size: 13px; font-weight: 600; padding: 7px 12px; }
.chip--btn:disabled { opacity: 0.4; }
.chip--active { background: var(--green-700); border-color: var(--green-700); color: #fff; }

.machine { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.machine__meta { display: flex; gap: 6px; flex-wrap: wrap; }
.asset { border-radius: var(--radius-md); padding: 12px; }
.asset--ok { display: flex; align-items: center; gap: 12px; background: var(--green-50); border: 1px solid var(--green-100); }
.asset--ok > i { color: var(--green-700); font-size: 20px; }
.asset__text { flex: 1; min-width: 0; }
.asset__id { font-weight: 700; color: var(--slate-900); }
.asset__name { font-size: 12px; color: var(--slate-500); overflow: hidden; text-overflow: ellipsis; }
.asset--missing { background: var(--amber-100); display: flex; flex-direction: column; gap: 10px; }
.asset__warn { display: flex; gap: 8px; font-size: 13px; color: #92400e; align-items: flex-start; }
.asset__actions { display: flex; gap: 8px; justify-content: flex-end; }

.frequent { margin-bottom: 12px; }
.mode { margin-bottom: 10px; }
.small-alert { font-size: 12px; padding: 8px 12px; }
.life { display: flex; flex-direction: column; gap: 10px; border-top: 1px dashed var(--slate-200); padding-top: 10px; }
.life__row { display: flex; flex-direction: column; gap: 4px; }
.life__top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.life__code { font-weight: 700; font-size: 13px; }
.life__val { font-size: 12px; font-weight: 700; color: var(--emerald-700); white-space: nowrap; }
.life__val--warning { color: var(--amber-600); }
.life__val--max { color: var(--red-600); }
.life__bar { height: 6px; background: var(--slate-100); border-radius: 999px; overflow: hidden; }
.life__fill { height: 100%; background: var(--emerald-700); border-radius: 999px; }
.life__fill--warning { background: var(--amber-600); }
.life__fill--max { background: var(--red-600); }
.short { color: var(--red-600); }
.stock-row--out { opacity: 0.55; }
.stock-row__set { font-size: 12px; font-weight: 600; color: var(--green-700); margin-top: 3px; }
.stock-row__set.short { color: var(--red-600); }
.kind--warning { background: var(--amber-100); color: var(--amber-600); }
.kind--max { background: var(--red-100); color: var(--red-600); }
.chip--set { background: var(--blue-100); color: var(--blue-600); font-size: 10px; padding: 2px 8px; margin-left: 6px; }
.frequent__chips { display: flex; flex-wrap: wrap; gap: 6px; }
.filters { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.segmented { display: flex; background: var(--slate-100); border-radius: var(--radius-md); padding: 3px; }
.segmented__btn { flex: 1; border: none; background: none; padding: 8px; border-radius: 8px; font: inherit; font-size: 13px; font-weight: 600; color: var(--slate-500); cursor: pointer; }
.segmented__btn--active { background: #fff; color: var(--green-700); box-shadow: var(--shadow-sm); }

.stock-list { display: flex; flex-direction: column; gap: 8px; max-height: 60vh; overflow-y: auto; }
.stock-row { display: flex; gap: 10px; align-items: center; padding: 10px 12px; border: 1px solid var(--slate-200); border-radius: var(--radius-md); background: #fff; }
.stock-row--in { border-color: var(--green-700); background: var(--green-50); }
.stock-row__main { flex: 1; min-width: 0; cursor: pointer; }
.stock-row__top { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.stock-row__code { font-weight: 700; font-size: 14px; color: var(--slate-900); }
.stock-row__name { font-size: 12px; color: var(--slate-500); margin-top: 2px; line-height: 1.35; }
.stock-row__side { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0; }
.stock-row__qty { font-weight: 700; font-size: 14px; color: var(--slate-700); white-space: nowrap; }
.stock-row__qty small { font-weight: 500; color: var(--slate-400); }
.btn-add { padding: 6px 14px; font-size: 13px; }
.kind { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; padding: 2px 7px; border-radius: 6px; }
.kind--needle { background: var(--blue-100); color: var(--blue-600); }
.kind--sinker { background: var(--amber-100); color: var(--amber-600); }
.kind--batch { background: var(--slate-100); color: var(--slate-500); }

.stepper { display: flex; align-items: center; border: 1.5px solid var(--green-700); border-radius: 10px; overflow: hidden; }
.stepper button { width: 34px; height: 34px; border: none; background: #fff; color: var(--green-700); cursor: pointer; }
.stepper input { width: 58px; height: 34px; border: none; text-align: center; font: inherit; font-weight: 700; font-size: 15px; -moz-appearance: textfield; }
.stepper input::-webkit-outer-spin-button, .stepper input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }

.reasons { display: flex; flex-wrap: wrap; gap: 6px; }
textarea.form-input { resize: vertical; font-family: inherit; }
.summary { margin-top: 14px; border-top: 1px dashed var(--slate-200); padding-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.summary__row { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 14px; }
.summary__row span:first-child { flex: 1; font-weight: 600; }
.summary__total { display: flex; justify-content: space-between; font-weight: 700; padding-top: 6px; border-top: 1px solid var(--slate-100); }

.result { border-color: var(--emerald-100); background: var(--emerald-100); }
.result__head { font-weight: 700; color: var(--emerald-700); display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.result__docs { display: flex; flex-direction: column; gap: 4px; font-size: 14px; }

.recent { padding: 10px 0; border-top: 1px solid var(--slate-100); display: flex; flex-direction: column; gap: 6px; }
.recent:first-of-type { border-top: none; }
.recent__top { display: flex; justify-content: space-between; align-items: baseline; }
.recent__items { display: flex; flex-wrap: wrap; gap: 4px; }

.sheet-backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: flex-end; justify-content: center; z-index: 50; }
.sheet { background: #fff; width: 100%; max-width: 560px; border-radius: 20px 20px 0 0; padding: 20px 16px calc(16px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; gap: 10px; }
.sheet__title { font-size: 17px; font-weight: 700; }
.sheet__list { display: flex; flex-direction: column; gap: 6px; padding: 8px 0; border-top: 1px solid var(--slate-100); border-bottom: 1px solid var(--slate-100); }
.sheet__actions { display: flex; gap: 10px; }
.sheet__actions .btn { flex: 1; }
@media (min-width: 600px) { .sheet-backdrop { align-items: center; } .sheet { border-radius: 20px; } }
</style>
