<template>
  <div class="page">
    <AppHeader
      :title="gate ? `Loading · ${gate.vehicle_no || gate.name}` : 'Loading Scan'"
      active="loading-scan" :username="auth.username" :designation="auth.designation" :show-back="true"
    />

    <!-- ══════════════ PICK A VEHICLE ══════════════ -->
    <div v-if="!gateEntry" class="page-content">
      <div class="card card--tight">
        <input
          v-model="search" class="form-input" placeholder="Search vehicle no, gate entry or outward request..."
          @input="onSearch"
        />
      </div>
      <div v-if="loadingList && !entries.length" class="empty"><i class="pi pi-spin pi-spinner"></i> Loading...</div>
      <div v-else-if="!entries.length" class="empty">No pick-up vehicles with outward requests.</div>
      <button v-for="g in entries" :key="g.name" class="vg-card" @click="openGate(g.name)">
        <div class="vg-card__top">
          <span class="vg-card__vehicle"><i class="pi pi-truck"></i> {{ g.vehicle_no }}</span>
          <span class="pill" :class="g.departure_datetime ? 'pill--grey' : 'pill--green'">
            {{ g.departure_datetime ? 'Departed' : 'At gate' }}
          </span>
        </div>
        <div class="muted small">{{ g.name }} · {{ fmtDate(g.date) }}<template v-if="g.driver_name"> · {{ g.driver_name }}</template></div>
        <div class="small">{{ g.outward_requests }}</div>
        <div v-if="g.scanned" class="small ok"><i class="pi pi-check-circle"></i> {{ g.scanned }} rolls scanned</div>
      </button>
    </div>

    <!-- ══════════════ SCANNING ══════════════ -->
    <div v-else class="page-content">
      <div v-if="error" class="banner banner--bad"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>

      <template v-if="data">
        <!-- Totals -->
        <div class="card totals" :class="{ 'totals--done': data.totals.complete }">
          <div class="totals__nums">
            <div><strong>{{ data.totals.scanned }}</strong><span>of {{ data.totals.expected }} scanned</span></div>
            <div :class="{ bad: data.totals.pending }"><strong>{{ data.totals.pending }}</strong><span>not scanned</span></div>
            <div :class="{ bad: data.totals.wrong }"><strong>{{ data.totals.wrong }}</strong><span>wrong rolls</span></div>
          </div>
          <div class="bar"><div class="bar__fill" :style="{ width: pct(data.totals.scanned, data.totals.expected) }"></div></div>
          <div v-if="data.totals.complete" class="ok small"><i class="pi pi-verified"></i> All rolls scanned — loading matches the stock entries.</div>
          <div v-else-if="!data.totals.expected" class="muted small">No picked rolls found for this vehicle's outward requests yet.</div>
        </div>

        <!-- Scan input -->
        <div class="card">
          <div class="scan-row">
            <input
              ref="scanInput" v-model="manual" class="form-input" placeholder="Scan or type roll no, then Enter"
              autocomplete="off" autocapitalize="off" @keydown.enter.prevent="submitManual"
            />
            <button class="btn btn-primary" :disabled="scanning" @click="cameraOn ? stopCamera() : startCamera()">
              <i class="pi" :class="cameraOn ? 'pi-stop-circle' : 'pi-camera'"></i> {{ cameraOn ? 'Stop' : 'Camera' }}
            </button>
          </div>
          <div v-show="cameraOn" id="loading-scan-camera" class="camera"></div>
          <div v-if="cameraError" class="bad small">{{ cameraError }}</div>
          <div v-if="last" class="last" :class="`last--${lastClass}`">
            <i class="pi" :class="lastIcon"></i>
            <div>
              <div class="last__msg">{{ last.message }}</div>
              <div v-if="lastLine" class="small">{{ lastLine.item_code }} · {{ lastLine.batch }} · {{ fmtNum(lastLine.qty) }} {{ lastLine.uom }}</div>
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <div class="chips">
          <button v-for="t in tabs" :key="t.key" class="chip" :class="{ 'chip--active': tab === t.key }" @click="tab = t.key">
            {{ t.label }} <span class="chip__n">{{ t.count }}</span>
          </button>
        </div>

        <!-- By stock entry -->
        <template v-if="tab === 'entries'">
          <div v-for="se in data.stock_entries" :key="se.pick_list" class="card se-card">
            <div class="se-card__head">
              <div>
                <div class="se-card__name">{{ se.stock_entry || 'No stock entry yet' }}
                  <span class="pill pill--soft" :class="se.stock_entry_status === 'Submitted' ? 'pill--green' : 'pill--amber'">{{ se.stock_entry_status }}</span>
                </div>
                <div class="muted small">{{ se.outward_request }} · {{ se.pick_list }} → {{ se.to_building }}</div>
              </div>
              <div class="se-card__count" :class="{ ok: se.rolls && se.scanned === se.rolls }">{{ se.scanned }}/{{ se.rolls }}</div>
            </div>
            <div class="bar"><div class="bar__fill" :style="{ width: pct(se.scanned, se.rolls) }"></div></div>
            <table class="lines">
              <thead><tr><th>Item / Batch</th><th>Stock Entry</th><th>Scanned</th></tr></thead>
              <tbody>
                <tr v-for="l in se.lines" :key="`${l.item_code}|${l.batch}`" :class="{ 'row-off': lineOff(l) }">
                  <td><div>{{ l.item_code }}</div><div class="muted small">{{ l.batch }}</div></td>
                  <td>{{ fmtNum(l.stock_entry_qty) }} {{ l.uom }}<div class="muted small">{{ l.rolls }} rolls</div></td>
                  <td>{{ fmtNum(l.scanned_qty) }} {{ l.uom }}<div class="muted small">{{ l.scanned_rolls }}/{{ l.rolls }} rolls</div></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!data.stock_entries.length" class="empty">No pick lists for this vehicle's outward requests yet.</div>
        </template>

        <!-- Roll lists -->
        <template v-else>
          <div v-if="!shownRolls.length" class="empty">{{ emptyText }}</div>
          <div v-for="r in shownRolls" :key="r.roll_no + (r.name || '')" class="roll" :class="rollClass(r)">
            <div class="roll__main">
              <div class="roll__no">{{ r.roll_no }}</div>
              <div class="small">{{ r.item_code || 'Unknown item' }}<template v-if="r.batch"> · {{ r.batch }}</template></div>
              <div class="muted small">
                <template v-if="tab === 'wrong'">Not on this vehicle's stock entries · {{ r.scanned_by_name }} {{ fmtTime(r.scanned_at) }}</template>
                <template v-else>{{ r.stock_entry || r.pick_list }}<template v-if="r.scanned"> · {{ r.scanned_by_name }} {{ fmtTime(r.scanned_at) }}</template></template>
              </div>
            </div>
            <div class="roll__side">
              <span class="roll__qty">{{ fmtNum(r.qty) }} {{ r.uom }}</span>
              <button v-if="tab !== 'pending'" class="btn-link" @click="undo(r.roll_no)">Undo</button>
            </div>
          </div>
        </template>
      </template>
      <div v-else class="empty"><i class="pi pi-spin pi-spinner"></i> Loading...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Html5Qrcode } from 'html5-qrcode'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { listLoadingGateEntries, getLoadingChecklist, scanLoadingRoll, undoLoadingScan } from '@/api/frappe'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const gateEntry = computed(() => route.query.gate_entry || '')

// ── Vehicle list ─────────────────────────────────────────────────────────
const entries = ref([])
const search = ref('')
const loadingList = ref(false)
let searchTimer = null
async function loadEntries() {
  loadingList.value = true
  try { entries.value = await listLoadingGateEntries(search.value) } catch (e) { error.value = e.message }
  finally { loadingList.value = false }
}
function onSearch() { clearTimeout(searchTimer); searchTimer = setTimeout(loadEntries, 300) }
function openGate(name) { router.push({ query: { gate_entry: name } }) }

// ── Checklist ────────────────────────────────────────────────────────────
const data = ref(null)
const error = ref('')
const gate = computed(() => data.value?.gate_entry || null)
const tab = ref('pending')
const rolls = computed(() => data.value?.rolls || [])
const tabs = computed(() => [
  { key: 'pending', label: 'Not scanned', count: rolls.value.filter(r => !r.scanned).length },
  { key: 'scanned', label: 'Scanned', count: rolls.value.filter(r => r.scanned).length },
  { key: 'wrong', label: 'Wrong', count: (data.value?.extras || []).length },
  { key: 'entries', label: 'By stock entry', count: (data.value?.stock_entries || []).length },
])
const shownRolls = computed(() => {
  if (tab.value === 'wrong') return data.value?.extras || []
  if (tab.value === 'scanned') return rolls.value.filter(r => r.scanned)
    .sort((a, b) => String(b.scanned_at).localeCompare(String(a.scanned_at)))
  return rolls.value.filter(r => !r.scanned)
})
const emptyText = computed(() => ({
  pending: 'Every roll is scanned.', scanned: 'Nothing scanned yet.', wrong: 'No wrong rolls scanned.',
}[tab.value]))

async function loadChecklist() {
  if (!gateEntry.value) return
  error.value = ''
  try { data.value = await getLoadingChecklist(gateEntry.value) } catch (e) { error.value = e.message }
}

// ── Scanning ─────────────────────────────────────────────────────────────
const manual = ref('')
const scanInput = ref(null)
const scanning = ref(false)
const last = ref(null)
const lastLine = computed(() => {
  if (!last.value) return null
  const all = [...rolls.value, ...(data.value?.extras || [])]
  return all.find(r => r.roll_no === last.value.roll_no) || null
})
const lastClass = computed(() => ({ Matched: 'ok', Duplicate: 'warn' }[last.value?.result] || 'bad'))
const lastIcon = computed(() => ({ Matched: 'pi-check-circle', Duplicate: 'pi-info-circle' }[last.value?.result] || 'pi-times-circle'))

let lastCode = ''
let lastCodeAt = 0
async function submitCode(code) {
  code = String(code || '').trim()
  if (!code || !gateEntry.value) return
  // The camera reads the same sticker many times a second: ignore repeats.
  const now = Date.now()
  if (code === lastCode && now - lastCodeAt < 3000) return
  lastCode = code
  lastCodeAt = now
  scanning.value = true
  try {
    const res = await scanLoadingRoll(gateEntry.value, code)
    data.value = res.checklist
    last.value = res
    buzz(res.result)
  } catch (e) {
    last.value = { result: 'Error', message: e.message }
    buzz('Error')
  } finally {
    scanning.value = false
  }
}
function submitManual() {
  const v = manual.value
  manual.value = ''
  lastCode = ''
  submitCode(v)
  nextTick(() => scanInput.value?.focus())
}
function buzz(result) {
  try {
    if (!navigator.vibrate) return
    navigator.vibrate(result === 'Matched' ? 60 : result === 'Duplicate' ? [60, 80, 60] : [250, 100, 250])
  } catch { /* not supported */ }
}

async function undo(rollNo) {
  if (!confirm(`Remove the scan of roll ${rollNo}?`)) return
  try { data.value = await undoLoadingScan(gateEntry.value, rollNo) } catch (e) { error.value = e.message }
}

// ── Camera (continuous) ──────────────────────────────────────────────────
const cameraOn = ref(false)
const cameraError = ref('')
let qr = null
async function startCamera() {
  cameraError.value = ''
  cameraOn.value = true
  await nextTick()
  try {
    qr = new Html5Qrcode('loading-scan-camera')
    await qr.start({ facingMode: 'environment' }, { fps: 10, qrbox: { width: 240, height: 240 } },
      (text) => submitCode(text), () => {})
  } catch (err) {
    cameraError.value = 'Could not access the camera: ' + (err?.message || err)
    cameraOn.value = false
  }
}
async function stopCamera() {
  cameraOn.value = false
  if (!qr) return
  try { if (qr.isScanning) await qr.stop(); qr.clear() } catch { /* already stopped */ }
  qr = null
}

// ── Helpers ──────────────────────────────────────────────────────────────
function pct(a, b) { return b ? `${Math.min(100, Math.round((a / b) * 100))}%` : '0%' }
function fmtNum(v) { const n = Number(v); return Number.isFinite(n) ? String(+n.toFixed(3)) : (v ?? '') }
function fmtDate(d) { if (!d) return ''; const [y, m, dd] = String(d).split('-'); return `${dd}-${m}-${y}` }
function fmtTime(dt) { return dt ? String(dt).split(' ')[1]?.slice(0, 5) || '' : '' }
function lineOff(l) {
  return l.rolls > 0 && l.scanned_rolls === l.rolls && Math.abs(l.scanned_qty - l.stock_entry_qty) > 0.01
}
function rollClass(r) {
  if (tab.value === 'wrong') return 'roll--bad'
  return r.scanned ? 'roll--ok' : ''
}

// ── Routing ──────────────────────────────────────────────────────────────
async function sync() {
  await stopCamera()
  data.value = null
  last.value = null
  tab.value = 'pending'
  if (gateEntry.value) await loadChecklist()
  else loadEntries()
}
watch(gateEntry, sync)
onMounted(sync)
onBeforeUnmount(stopCamera)
</script>

<style scoped>
.page-content { padding: 16px; max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
.card { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card--tight { padding: 12px; }
.form-input { width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; font-size: 15px; box-sizing: border-box; min-height: 42px; }
.btn { border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 600; font-size: 14px; display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { opacity: .6; }
.btn-link { background: none; border: 0; color: #dc2626; font-size: 12px; font-weight: 600; padding: 4px 0; }
.empty { text-align: center; color: #94a3b8; padding: 28px 8px; font-size: 14px; }
.muted { color: #64748b; }
.small { font-size: 12px; }
.ok { color: #15803d; }
.bad { color: #b91c1c; }
.pill { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.pill--green { background: #dcfce7; color: #166534; }
.pill--amber { background: #fef3c7; color: #92400e; }
.pill--grey { background: #f1f5f9; color: #475569; }
.pill--soft { margin-left: 6px; }
.banner { border-radius: 10px; padding: 10px 12px; font-size: 13px; }
.banner--bad { background: #fee2e2; color: #991b1b; }

.vg-card { text-align: left; background: #fff; border: 0; border-radius: 12px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 4px; }
.vg-card__top { display: flex; justify-content: space-between; align-items: center; }
.vg-card__vehicle { font-weight: 700; font-size: 16px; }

.totals__nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; margin-bottom: 10px; }
.totals__nums strong { display: block; font-size: 22px; }
.totals__nums span { font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 700; }
.totals--done { box-shadow: inset 0 0 0 2px #22c55e; }
.bar { height: 8px; background: #f1f5f9; border-radius: 999px; overflow: hidden; margin-bottom: 8px; }
.bar__fill { height: 100%; background: #22c55e; transition: width .3s; }

.scan-row { display: flex; gap: 8px; }
.camera { margin-top: 10px; border-radius: 10px; overflow: hidden; }
.last { margin-top: 10px; border-radius: 10px; padding: 10px 12px; display: flex; gap: 10px; align-items: flex-start; }
.last .pi { font-size: 22px; }
.last__msg { font-weight: 700; }
.last--ok { background: #dcfce7; color: #14532d; }
.last--warn { background: #fef3c7; color: #78350f; }
.last--bad { background: #fee2e2; color: #7f1d1d; }

.chips { display: flex; gap: 6px; overflow-x: auto; }
.chip { border: 1px solid #e2e8f0; background: #fff; border-radius: 999px; padding: 6px 12px; font-size: 13px; white-space: nowrap; }
.chip--active { background: #0f6e56; border-color: #0f6e56; color: #fff; }
.chip__n { font-weight: 700; margin-left: 4px; }

.se-card__head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.se-card__name { font-weight: 700; }
.se-card__count { font-size: 20px; font-weight: 800; }
.lines { width: 100%; border-collapse: collapse; font-size: 13px; }
.lines th { text-align: left; font-size: 11px; color: #64748b; text-transform: uppercase; padding: 4px; }
.lines td { padding: 6px 4px; border-top: 1px solid #f1f5f9; vertical-align: top; }
.row-off td { background: #fffbeb; }

.roll { background: #fff; border-radius: 10px; padding: 10px 12px; display: flex; justify-content: space-between; gap: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border-left: 4px solid #cbd5e1; }
.roll--ok { border-left-color: #22c55e; }
.roll--bad { border-left-color: #ef4444; background: #fef2f2; }
.roll__no { font-weight: 700; font-size: 15px; }
.roll__side { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.roll__qty { font-weight: 600; font-size: 13px; white-space: nowrap; }
</style>
