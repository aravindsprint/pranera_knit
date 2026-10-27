<template>
  <div class="page">
    <AppHeader
      :title="mode === 'list' ? 'Vehicle Inward' : (form.name || 'New Vehicle Inward')"
      active="vehicle-inward" :username="auth.username" :designation="auth.designation" :show-back="true"
    />

    <!-- ══════════════════════ LIST ══════════════════════ -->
    <div v-if="mode === 'list'" class="page-content">
      <button class="btn btn-primary btn-full" @click="openNew">
        <i class="pi pi-plus"></i> New Vehicle Inward
      </button>

      <div class="card card--tight">
        <div class="chips">
          <button
            v-for="f in FILTERS" :key="f.value" class="chip"
            :class="{ 'chip--active': listState === f.value }" @click="setState(f.value)"
          >{{ f.label }}</button>
        </div>
        <input
          v-model="listSearch" class="form-input" style="margin-top:10px"
          placeholder="Search vehicle no, driver, mobile, location..." @input="onListSearch"
        />
      </div>

      <div v-if="loadingList && !rows.length" class="empty"><i class="pi pi-spin pi-spinner"></i> Loading...</div>
      <div v-else-if="!rows.length" class="empty">No vehicles logged yet.</div>

      <div v-for="r in rows" :key="r.name" class="vi-card" @click="openExisting(r.name)">
        <div class="vi-card__top">
          <span class="vi-card__vno">{{ r.vehicle_no }}</span>
          <span class="pill" :class="r.purpose === 'Pick Up' ? 'pill--blue' : 'pill--violet'">{{ r.purpose }}</span>
        </div>
        <div class="vi-card__route">
          <i class="pi" :class="r.purpose === 'Pick Up' ? 'pi-arrow-up-right' : 'pi-arrow-down-left'"></i>
          {{ r.purpose === 'Pick Up' ? 'From' : 'To' }} {{ r.from_location || r.to_location }}
        </div>
        <div class="vi-card__meta">
          <span>{{ r.driver_name }} · {{ r.mobile_no }}</span>
          <span>{{ r.capacity }}</span>
        </div>
        <div class="vi-card__foot">
          <span class="muted">In {{ fmtDateTime(r.arrival_datetime) }}</span>
          <span v-if="r.departure_datetime" class="muted">Out {{ fmtDateTime(r.departure_datetime) }}</span>
          <button v-else class="btn-depart" :disabled="departing === r.name" @click.stop="depart(r.name)">
            <i class="pi" :class="departing === r.name ? 'pi-spin pi-spinner' : 'pi-sign-out'"></i> Mark Departed
          </button>
        </div>
      </div>
    </div>

    <!-- ══════════════════════ FORM ══════════════════════ -->
    <div v-else class="page-content">
      <div class="card">
        <div class="grid-2">
          <div>
            <label class="form-label">Date <span class="req">*</span></label>
            <input v-model="form.date" type="date" class="form-input" />
          </div>
          <div>
            <label class="form-label">Vehicle No <span class="req">*</span></label>
            <input v-model="form.vehicle_no" class="form-input upper" placeholder="TN39AB1234" autocapitalize="characters" />
          </div>
          <div>
            <label class="form-label">Driver Name <span class="req">*</span></label>
            <input v-model="form.driver_name" class="form-input" placeholder="Driver name" />
          </div>
          <div>
            <label class="form-label">Mobile No <span class="req">*</span></label>
            <input v-model="form.mobile_no" type="tel" inputmode="numeric" maxlength="14" class="form-input" placeholder="10-digit mobile" />
          </div>
          <div>
            <label class="form-label">Capacity <span class="req">*</span></label>
            <select v-model="form.capacity" class="form-input">
              <option value="" disabled>Select capacity</option>
              <option v-for="c in options.capacities" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="grid-2">
          <div>
            <label class="form-label">Arrival Date and Time <span class="req">*</span></label>
            <input v-model="form.arrival" type="datetime-local" class="form-input" />
          </div>
          <div>
            <label class="form-label">Departure Date and Time</label>
            <div class="dt-row">
              <input v-model="form.departure" type="datetime-local" class="form-input" :min="form.arrival" />
              <button class="btn btn-outline btn-now" title="Set to now" @click="form.departure = nowLocal()">Now</button>
            </div>
          </div>
        </div>

        <label class="form-label" style="margin-top:14px">Purpose <span class="req">*</span></label>
        <div class="segmented">
          <button
            v-for="p in ['Pick Up', 'Drop']" :key="p" class="segmented__btn"
            :class="{ 'segmented__btn--active': form.purpose === p }" @click="form.purpose = p"
          >
            <i class="pi" :class="p === 'Pick Up' ? 'pi-arrow-up-right' : 'pi-arrow-down-left'"></i> {{ p }}
          </button>
        </div>

        <template v-if="form.purpose">
          <label class="form-label" style="margin-top:14px">
            {{ form.purpose === 'Pick Up' ? 'From' : 'To' }} <span class="req">*</span>
          </label>
          <select v-model="form.location" class="form-input">
            <option value="" disabled>Select {{ form.purpose === 'Pick Up' ? 'from' : 'to' }} location</option>
            <optgroup label="Buildings">
              <option v-for="l in buildingOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
            </optgroup>
            <optgroup label="Other">
              <option v-for="l in otherOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
            </optgroup>
          </select>
        </template>
      </div>

      <div v-if="form.name" class="card meta-card">
        <div>
          <div class="form-label">Created By</div>
          <div class="value">{{ form.created_by_name || '—' }}</div>
        </div>
        <div>
          <div class="form-label">Status</div>
          <span class="pill" :class="savedDeparture ? 'pill--grey' : 'pill--green'">{{ savedDeparture ? 'Departed' : 'Inside' }}</span>
        </div>
      </div>

      <div class="card">
        <button class="btn btn-primary btn-full" :disabled="!canSave || saving" @click="save">
          <i v-if="saving" class="pi pi-spin pi-spinner"></i>
          {{ saving ? 'Saving...' : (form.name ? 'Update Vehicle Inward' : 'Save Vehicle Inward') }}
        </button>
        <div v-if="!canSave && missing.length" class="hint-text">
          <i class="pi pi-info-circle"></i><span>Still needed: {{ missing.join(', ') }}</span>
        </div>
      </div>

      <div v-if="error" class="error-banner"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>
    </div>

    <div v-if="mode === 'list' && error" class="page-content" style="padding-top:0">
      <div class="error-banner"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>
    </div>

    <transition name="modal-fade">
      <div v-if="savedName" class="modal-overlay" @click.self="savedName = ''">
        <div class="modal-box">
          <i class="pi pi-check-circle modal-icon"></i>
          <h3 class="modal-title">Vehicle Inward Saved</h3>
          <div class="modal-docno">{{ savedName }}</div>
          <button class="btn btn-primary btn-full" @click="savedName = ''">OK</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getVehicleInwardOptions, saveVehicleInward, getVehicleInward, markVehicleDeparted, listVehicleInwards,
} from '@/api/frappe'
import AppHeader from '@/components/AppHeader.vue'

const FILTERS = [
  { label: 'All', value: '' },
  { label: 'Inside', value: 'inside' },
  { label: 'Departed', value: 'departed' },
]

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const options = reactive({ capacities: [], locations: [] })
const rows = ref([])
const listState = ref('')
const listSearch = ref('')
const loadingList = ref(false)
const departing = ref('')
const saving = ref(false)
const error = ref('')
const savedName = ref('')
const savedDeparture = ref('')

const form = reactive(blankForm())

function pad(n) { return String(n).padStart(2, '0') }
function nowLocal() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function blankForm() {
  return {
    name: '', date: nowLocal().slice(0, 10), vehicle_no: '', driver_name: '', mobile_no: '',
    capacity: '', arrival: nowLocal(), departure: '', purpose: '', location: '', created_by_name: '',
  }
}
// Frappe "YYYY-MM-DD HH:MM:SS" <-> <input type="datetime-local"> "YYYY-MM-DDTHH:MM"
const toLocal = (dt) => (dt ? String(dt).replace(' ', 'T').slice(0, 16) : '')
const toFrappe = (v) => (v ? `${v.replace('T', ' ')}:00` : null)

const mode = computed(() => (route.query.name || route.query.new ? 'form' : 'list'))
const buildingOptions = computed(() => options.locations.filter(l => l.group === 'Building'))
const otherOptions = computed(() => options.locations.filter(l => l.group !== 'Building'))

const missing = computed(() => {
  const m = []
  if (!form.date) m.push('Date')
  if (!form.vehicle_no.trim()) m.push('Vehicle No')
  if (!form.driver_name.trim()) m.push('Driver Name')
  if (form.mobile_no.replace(/\D/g, '').length < 10) m.push('Mobile No')
  if (!form.capacity) m.push('Capacity')
  if (!form.arrival) m.push('Arrival')
  if (!form.purpose) m.push('Purpose')
  else if (!form.location) m.push(form.purpose === 'Pick Up' ? 'From' : 'To')
  return m
})
const canSave = computed(() => missing.value.length === 0)

// Switching purpose: keep the chosen location (it moves from From to To),
// the server clears whichever side doesn't apply.
watch(() => form.purpose, () => { error.value = '' })

onMounted(async () => {
  try {
    const o = await getVehicleInwardOptions()
    options.capacities = o.capacities
    options.locations = o.locations
  } catch (e) { error.value = e.message }
  syncWithRoute()
})
watch(() => [route.query.name, route.query.new], syncWithRoute)

async function syncWithRoute() {
  error.value = ''
  if (route.query.name) {
    if (form.name !== route.query.name) await open(route.query.name)
  } else if (route.query.new) {
    Object.assign(form, blankForm())
    savedDeparture.value = ''
  } else {
    loadList()
  }
}

async function loadList() {
  loadingList.value = true
  try {
    rows.value = await listVehicleInwards({ txt: listSearch.value, state: listState.value })
  } catch (e) {
    error.value = e.message
  } finally {
    loadingList.value = false
  }
}
let searchTimer = null
function onListSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadList, 300)
}
function setState(v) { listState.value = v; loadList() }

function openNew() { router.push({ query: { new: '1' } }) }
function openExisting(name) { router.push({ query: { name } }) }

function applyDoc(d) {
  Object.assign(form, {
    name: d.name, date: d.date, vehicle_no: d.vehicle_no, driver_name: d.driver_name,
    mobile_no: d.mobile_no, capacity: d.capacity, arrival: toLocal(d.arrival_datetime),
    departure: toLocal(d.departure_datetime), purpose: d.purpose,
    location: d.purpose === 'Pick Up' ? d.from_location : d.to_location,
    created_by_name: d.created_by_name,
  })
  savedDeparture.value = d.departure_datetime || ''
}

async function open(name) {
  try { applyDoc(await getVehicleInward(name)) } catch (e) { error.value = e.message }
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''
  const wasNew = !form.name
  try {
    const d = await saveVehicleInward({
      name: form.name || undefined,
      date: form.date,
      vehicle_no: form.vehicle_no,
      driver_name: form.driver_name.trim(),
      mobile_no: form.mobile_no,
      capacity: form.capacity,
      arrival_datetime: toFrappe(form.arrival),
      departure_datetime: toFrappe(form.departure) || '',
      purpose: form.purpose,
      from_location: form.purpose === 'Pick Up' ? form.location : '',
      to_location: form.purpose === 'Drop' ? form.location : '',
    })
    applyDoc(d)
    savedName.value = d.name
    if (wasNew) router.replace({ query: { name: d.name } })
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function depart(name) {
  departing.value = name
  error.value = ''
  try {
    const d = await markVehicleDeparted(name)
    const i = rows.value.findIndex(r => r.name === name)
    if (i >= 0) rows.value[i] = { ...rows.value[i], departure_datetime: d.departure_datetime }
    if (listState.value === 'inside') rows.value = rows.value.filter(r => r.name !== name)
  } catch (e) {
    error.value = e.message
  } finally {
    departing.value = ''
  }
}

function fmtDateTime(dt) {
  if (!dt) return '—'
  const [d, t = ''] = String(dt).split(' ')
  const [y, m, day] = d.split('-')
  return `${day}-${m}-${y} ${t.slice(0, 5)}`
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
  font-size: 14px; box-sizing: border-box; font-family: inherit; background: #fff; min-height: 42px;
}
select.form-input {
  appearance: none; -webkit-appearance: none; padding-right: 34px; cursor: pointer;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E") no-repeat right 12px center;
}
.upper { text-transform: uppercase; }
.muted { color: #64748b; }
.value { font-size: 14px; color: #0f172a; font-weight: 600; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 520px) { .grid-2 { grid-template-columns: 1fr; } }
.dt-row { display: flex; gap: 8px; }
.dt-row .form-input { flex: 1; min-width: 0; }
.btn-now { padding: 0 12px; }

.segmented { display: flex; background: #f1f5f9; border-radius: 10px; padding: 3px; }
.segmented__btn {
  flex: 1; border: none; background: none; padding: 10px; border-radius: 8px;
  font-size: 14px; font-weight: 600; color: #475569; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.segmented__btn--active { background: #fff; color: var(--app-primary, #0f6e56); box-shadow: 0 1px 2px rgba(0,0,0,0.08); }

.meta-card { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hint-text { font-size: 12px; color: #64748b; margin-top: 8px; display: flex; gap: 6px; align-items: flex-start; }
.hint-text i { margin-top: 1px; }

.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid #e2e8f0; background: #fff; color: #475569; border-radius: 999px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.chip--active { background: var(--app-primary, #0f6e56); border-color: var(--app-primary, #0f6e56); color: #fff; }

.vi-card { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 6px; cursor: pointer; }
.vi-card__top, .vi-card__meta, .vi-card__foot { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.vi-card__vno { font-weight: 800; font-size: 16px; color: #0f172a; letter-spacing: 0.5px; }
.vi-card__route { font-size: 14px; color: #334155; display: flex; align-items: center; gap: 6px; }
.vi-card__meta, .vi-card__foot { font-size: 12px; color: #64748b; }
.btn-depart {
  border: 1.5px solid #0f6e56; color: #0f6e56; background: #fff; border-radius: 999px;
  padding: 4px 10px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; gap: 6px; align-items: center;
}

.pill { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap; display: inline-block; }
.pill--blue { background: #dbeafe; color: #1e40af; }
.pill--violet { background: #ede9fe; color: #5b21b6; }
.pill--green { background: #dcfce7; color: #166534; }
.pill--grey { background: #f1f5f9; color: #475569; }

.empty { text-align: center; color: #94a3b8; padding: 28px 12px; font-size: 14px; }

.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; }
.btn-full { width: 100%; padding: 12px; }

.error-banner { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 20px; }
.modal-box { background: #fff; border-radius: 14px; padding: 28px 24px; width: 100%; max-width: 360px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.modal-icon { font-size: 40px; color: #16a34a; margin-bottom: 10px; display: block; }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 12px; color: #0f172a; }
.modal-docno { font-size: 15px; font-weight: 700; color: #0f6e56; background: #f0fdf4; border-radius: 8px; padding: 10px 14px; margin-bottom: 18px; }
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>
