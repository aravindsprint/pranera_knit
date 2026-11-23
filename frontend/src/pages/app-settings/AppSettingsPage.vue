<template>
  <div class="page">
    <AppHeader title="Settings" active="app-settings" :username="auth.username" :designation="auth.designation" />

    <div class="page-content">
      <div class="chips">
        <button v-for="t in TABS" :key="t.key" class="chip" :class="{ 'chip--active': tab === t.key }" @click="tab = t.key">
          {{ t.label }}
        </button>
      </div>

      <div v-if="error" class="banner banner--bad"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>
      <div v-if="saved" class="banner banner--ok"><i class="pi pi-check-circle"></i> {{ saved }}</div>
      <div v-if="!data && !error" class="empty"><i class="pi pi-spin pi-spinner"></i> Loading...</div>

      <template v-if="data">
        <!-- ══════════ OUTWARD REQUEST ══════════ -->
        <div v-if="tab === 'outward'" class="card">
          <template v-if="or">
            <h3 class="card-title">Outward Request</h3>
            <label class="form-label">Order deadline (day before the request date)</label>
            <input v-model="or.deadline" type="time" class="form-input" />
            <div class="hint">A request for a date must be created before this time on the day before. Later requests need approval.</div>

            <label class="switch-row">
              <input v-model="or.require_approval" type="checkbox" :true-value="1" :false-value="0" />
              <span>Send late requests for approval (off = allow them)</span>
            </label>

            <label class="form-label">Daily Kgs limit (per delivery date)</label>
            <input v-model.number="or.daily_kgs_limit" type="number" min="0" step="100" class="form-input" />
            <div class="hint">Fabric Kgs on all requests for one date together. Collar / cuff not counted. Over the limit needs approval. 0 = no limit.</div>

            <label class="form-label">Approvers</label>
            <div class="list">
              <div v-for="(a, i) in or.approvers" :key="a.user" class="list-row">
                <div><div class="strong">{{ a.full_name }}</div><div class="muted small">{{ a.user }}</div></div>
                <button class="icon-btn" @click="or.approvers.splice(i, 1)"><i class="pi pi-trash"></i></button>
              </div>
              <div v-if="!or.approvers.length" class="muted small">No approvers — late / over-limit requests can't be approved.</div>
            </div>
            <SearchPick :search="searchSettingsUsers" placeholder="Add approver: search name or email"
                        :label="u => `${u.full_name || u.user} · ${u.user}`" @pick="addOrApprover" />

            <button class="btn btn-primary btn-block" :disabled="saving" @click="saveOutward">
              <i class="pi" :class="saving ? 'pi-spin pi-spinner' : 'pi-save'"></i> Save Outward Request settings
            </button>
          </template>
          <div v-else class="muted">Outward Request Settings isn't installed.</div>
        </div>

        <!-- ══════════ KNIT DOWN ══════════ -->
        <div v-if="tab === 'knitdown'" class="card">
          <template v-if="kd">
            <h3 class="card-title">Knit Down approval</h3>
            <div class="hint" style="margin-top:0">A Knit Down Approver can only approve knit downs of Work Orders at their locations below. System Managers can approve everything.</div>

            <label class="switch-row">
              <input v-model="kd.require_gps" type="checkbox" :true-value="1" :false-value="0" />
              <span>Require GPS: approver must be at the unit</span>
            </label>
            <template v-if="kd.require_gps">
              <label class="form-label">GPS range (metres)</label>
              <input v-model.number="kd.gps_radius_m" type="number" min="20" max="5000" step="10" class="form-input" />
            </template>

            <label class="form-label">Approver locations</label>
            <div class="list">
              <div v-for="(r, i) in kd.approver_locations" :key="`${r.user}|${r.location}`" class="list-row">
                <div>
                  <div class="strong">{{ r.full_name }}</div>
                  <div class="muted small"><i class="pi pi-map-marker"></i> {{ r.location }}</div>
                </div>
                <button class="icon-btn" @click="kd.approver_locations.splice(i, 1)"><i class="pi pi-trash"></i></button>
              </div>
              <div v-if="!kd.approver_locations.length" class="muted small">None yet — only System Managers can approve knit downs.</div>
            </div>
            <div class="add-box">
              <div class="small strong">Add approver + location</div>
              <SearchPick :search="searchSettingsUsers" placeholder="Approver: search name or email"
                          :label="u => `${u.full_name || u.user} · ${u.user}`" :value="newKd.userLabel" @pick="u => { newKd.user = u.user; newKd.full_name = u.full_name || u.user; newKd.userLabel = newKd.full_name }" />
              <SearchPick :search="searchSettingsLocations" placeholder="Location: search"
                          :label="l => l" :value="newKd.location" @pick="l => (newKd.location = l)" />
              <button class="btn btn-outline" :disabled="!newKd.user || !newKd.location" @click="addKdRow">
                <i class="pi pi-plus"></i> Add
              </button>
            </div>

            <button class="btn btn-primary btn-block" :disabled="saving" @click="saveKnitDown">
              <i class="pi" :class="saving ? 'pi-spin pi-spinner' : 'pi-save'"></i> Save Knit Down settings
            </button>
          </template>
          <div v-else class="muted">Knit Down Settings isn't installed.</div>
        </div>

        <!-- ══════════ UNIT GPS ══════════ -->
        <template v-if="tab === 'gps'">
          <div class="card hint-card">
            <i class="pi pi-info-circle"></i>
            Stand inside the unit and tap <b>Use my location</b>, or type the coordinates from Google Maps (long-press → copy). Used for the knit down GPS check.
          </div>
          <div v-for="l in data.locations" :key="l.name" class="card loc">
            <div class="loc__head">
              <div>
                <div class="strong">{{ l.name }}</div>
                <div class="muted small">{{ l.open_work_orders }} open work orders</div>
              </div>
              <span class="pill" :class="l.has_coordinates ? 'pill--green' : 'pill--amber'">{{ l.has_coordinates ? 'Set' : 'Not set' }}</span>
            </div>
            <div class="loc__inputs">
              <input v-model="coords[l.name].lat" class="form-input" inputmode="decimal" placeholder="Latitude" />
              <input v-model="coords[l.name].lng" class="form-input" inputmode="decimal" placeholder="Longitude" />
            </div>
            <div v-if="coords[l.name].accuracy" class="muted small">Phone accuracy: ±{{ coords[l.name].accuracy }} m</div>
            <div class="loc__actions">
              <button class="btn btn-outline" :disabled="locating === l.name" @click="useMyLocation(l.name)">
                <i class="pi" :class="locating === l.name ? 'pi-spin pi-spinner' : 'pi-map-marker'"></i> Use my location
              </button>
              <a v-if="l.has_coordinates" class="btn btn-outline" target="_blank" rel="noopener"
                 :href="`https://www.google.com/maps?q=${l.latitude},${l.longitude}`"><i class="pi pi-external-link"></i> Map</a>
              <button class="btn btn-primary" :disabled="saving" @click="saveCoords(l.name)"><i class="pi pi-save"></i> Save</button>
            </div>
          </div>
          <div v-if="!data.locations.length" class="empty">No locations on open Work Orders yet.</div>
        </template>

        <!-- ══════════ PAGE ACCESS ══════════ -->
        <template v-if="tab === 'pages'">
          <div class="card hint-card">
            <i class="pi pi-info-circle"></i>
            No roles = everyone can open the page. With roles, only users having one of them. System Managers always see every page.
          </div>
          <div v-for="p in data.pages" :key="p.page" class="card page-row">
            <div class="page-row__head">
              <div class="strong">{{ p.title }}</div>
              <span class="muted small">{{ p.section }}</span>
            </div>
            <div class="tags">
              <span v-for="(r, i) in p.roles" :key="r" class="tag">
                {{ r }} <button class="tag__x" @click="removeRole(p, i)"><i class="pi pi-times"></i></button>
              </span>
              <span v-if="!p.roles.length" class="muted small">Everyone</span>
            </div>
            <SearchPick :search="searchSettingsRoles" placeholder="Add role" :label="r => r" @pick="r => addRole(p, r)" />
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, defineComponent, h, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import {
  getAppSettings, searchSettingsUsers, searchSettingsLocations, searchSettingsRoles,
  saveOutwardRequestSettings, saveKnitDownSettings, saveLocationCoordinates, savePageRoles,
} from '@/api/frappe'

const auth = useAuthStore()
const TABS = [
  { key: 'outward', label: 'Outward Request' },
  { key: 'knitdown', label: 'Knit Down' },
  { key: 'gps', label: 'Unit GPS' },
  { key: 'pages', label: 'Page Access' },
]
const tab = ref('outward')
const data = ref(null)
const error = ref('')
const saved = ref('')
const saving = ref(false)
const or = computed(() => data.value?.outward_request)
const kd = computed(() => data.value?.knit_down)
const coords = reactive({})
const newKd = reactive({ user: '', full_name: '', userLabel: '', location: '' })
const locating = ref('')

function apply(d) {
  data.value = d
  for (const l of d.locations || []) {
    coords[l.name] = { lat: l.has_coordinates ? String(l.latitude) : '', lng: l.has_coordinates ? String(l.longitude) : '', accuracy: 0 }
  }
}
async function load() {
  error.value = ''
  try { apply(await getAppSettings()) } catch (e) { error.value = e.message }
}
async function run(fn, msg) {
  saving.value = true
  error.value = ''
  saved.value = ''
  try {
    const res = await fn()
    if (res && res.outward_request !== undefined) apply(res)
    saved.value = msg
    setTimeout(() => { if (saved.value === msg) saved.value = '' }, 3000)
    return res
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
watch(tab, () => { saved.value = ''; error.value = '' })

// Outward Request
function addOrApprover(u) {
  if (!or.value.approvers.some(a => a.user === u.user)) or.value.approvers.push({ user: u.user, full_name: u.full_name || u.user })
}
const saveOutward = () => run(() => saveOutwardRequestSettings(or.value), 'Outward Request settings saved')

// Knit Down
function addKdRow() {
  const exists = kd.value.approver_locations.some(r => r.user === newKd.user && r.location === newKd.location)
  if (!exists) kd.value.approver_locations.push({ user: newKd.user, full_name: newKd.full_name, location: newKd.location })
  Object.assign(newKd, { user: '', full_name: '', userLabel: '', location: '' })
}
const saveKnitDown = () => run(() => saveKnitDownSettings(kd.value), 'Knit Down settings saved')

// Unit GPS
function useMyLocation(name) {
  if (!navigator.geolocation) { error.value = 'This browser can\'t share its location.'; return }
  locating.value = name
  error.value = ''
  navigator.geolocation.getCurrentPosition(
    p => {
      coords[name] = { lat: p.coords.latitude.toFixed(6), lng: p.coords.longitude.toFixed(6), accuracy: Math.round(p.coords.accuracy || 0) }
      locating.value = ''
    },
    err => {
      error.value = err.code === 1 ? 'Location permission is blocked for this site. Allow it in the browser settings.' : 'Could not get your location. Turn on GPS and try again.'
      locating.value = ''
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
  )
}
function parseCoord(v) {
  // Accepts "11.10850" or a pasted "11.10850, 77.34110" in the latitude box.
  return String(v || '').trim()
}
function saveCoords(name) {
  let { lat, lng } = coords[name]
  lat = parseCoord(lat)
  if (lat.includes(',') && !String(lng || '').trim()) [lat, lng] = lat.split(',').map(s => s.trim())
  return run(() => saveLocationCoordinates(name, lat, lng), `GPS saved for ${name}`)
}

// Page access
async function addRole(p, role) {
  if (p.roles.includes(role)) return
  const pages = await run(() => savePageRoles(p.page, [...p.roles, role]), `${p.title}: access updated`)
  if (Array.isArray(pages)) data.value.pages = pages
}
async function removeRole(p, i) {
  const roles = p.roles.filter((_, j) => j !== i)
  const pages = await run(() => savePageRoles(p.page, roles), `${p.title}: access updated`)
  if (Array.isArray(pages)) data.value.pages = pages
}

// ── Small server-search picker ───────────────────────────────────────────
const SearchPick = defineComponent({
  props: { search: Function, placeholder: String, label: Function, value: { type: String, default: '' } },
  emits: ['pick'],
  setup(props, { emit }) {
    const q = ref(props.value || '')
    const results = ref([])
    const open = ref(false)
    let timer = null
    watch(() => props.value, v => { q.value = v || '' })
    async function doSearch() {
      try { results.value = await props.search(q.value) } catch { results.value = [] }
      open.value = true
    }
    function onInput(e) {
      q.value = e.target.value
      clearTimeout(timer)
      timer = setTimeout(doSearch, 250)
    }
    function pick(r) {
      emit('pick', r)
      q.value = props.value !== undefined && props.value !== '' ? props.label(r) : ''
      open.value = false
    }
    return () => h('div', { class: 'sp' }, [
      h('input', {
        class: 'form-input', value: q.value, placeholder: props.placeholder,
        onInput, onFocus: doSearch, onBlur: () => setTimeout(() => (open.value = false), 150),
      }),
      open.value && results.value.length
        ? h('div', { class: 'sp__panel' }, results.value.map(r =>
            h('div', { class: 'sp__opt', onMousedown: (e) => { e.preventDefault(); pick(r) } }, props.label(r))))
        : null,
    ])
  },
})

onMounted(load)
</script>

<style scoped>
.page-content { padding: 16px; max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 8px; }
.card-title { margin: 0 0 4px; font-size: 16px; }
.form-label { font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: .03em; margin-top: 8px; }
.form-input { width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; font-size: 15px; box-sizing: border-box; min-height: 42px; background: #fff; }
.hint { font-size: 12px; color: #64748b; }
.hint-card { flex-direction: row; gap: 8px; font-size: 13px; color: #334155; background: #f0fdf4; }
.switch-row { display: flex; gap: 10px; align-items: center; font-size: 14px; margin-top: 8px; }
.switch-row input { width: 20px; height: 20px; }
.btn { border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 600; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; text-decoration: none; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-outline { background: #fff; border: 1px solid #cbd5e1; color: #0f172a; }
.btn:disabled { opacity: .55; }
.btn-block { width: 100%; margin-top: 12px; }
.icon-btn { background: none; border: 0; color: #dc2626; padding: 6px; }
.list { display: flex; flex-direction: column; gap: 6px; }
.list-row { display: flex; justify-content: space-between; align-items: center; border: 1px solid #f1f5f9; border-radius: 10px; padding: 8px 10px; }
.add-box { border: 1px dashed #cbd5e1; border-radius: 10px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.strong { font-weight: 600; }
.muted { color: #64748b; }
.small { font-size: 12px; }
.empty { text-align: center; color: #94a3b8; padding: 24px; }
.banner { border-radius: 10px; padding: 10px 12px; font-size: 13px; }
.banner--bad { background: #fee2e2; color: #991b1b; }
.banner--ok { background: #dcfce7; color: #166534; }
.chips { display: flex; gap: 6px; overflow-x: auto; }
.chip { border: 1px solid #e2e8f0; background: #fff; border-radius: 999px; padding: 7px 14px; font-size: 13px; white-space: nowrap; }
.chip--active { background: #0f6e56; border-color: #0f6e56; color: #fff; }
.pill { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.pill--green { background: #dcfce7; color: #166534; }
.pill--amber { background: #fef3c7; color: #92400e; }
.loc__head, .page-row__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.loc__inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.loc__actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: #eef2ff; color: #3730a3; border-radius: 999px; padding: 3px 4px 3px 10px; font-size: 12px; display: inline-flex; align-items: center; gap: 2px; }
.tag__x { background: none; border: 0; color: #6366f1; padding: 2px 4px; font-size: 10px; }
:deep(.sp) { position: relative; }
:deep(.sp__panel) { position: absolute; left: 0; right: 0; top: 100%; z-index: 20; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; margin-top: 4px; max-height: 240px; overflow-y: auto; box-shadow: 0 8px 20px rgba(0,0,0,.08); }
:deep(.sp__opt) { padding: 10px 12px; font-size: 14px; border-bottom: 1px solid #f8fafc; cursor: pointer; }
:deep(.sp__opt:hover) { background: #f0fdf4; }
</style>
