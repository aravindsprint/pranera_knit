<template>
  <div class="page">
    <AppHeader
      :title="mode === 'list' ? page.title : (form.name || `New ${page.title}`)"
      :active="page.key" :username="auth.username" :designation="auth.designation" :show-back="true"
    />

    <!-- ══════════════════════ LIST ══════════════════════ -->
    <div v-if="mode === 'list'" class="page-content">
      <button v-if="setup.can_create" class="btn btn-primary btn-full" @click="openNew()">
        <i class="pi pi-plus"></i> New Knit Down
      </button>

      <div class="card card--tight">
        <div class="chips">
          <button
            v-for="f in FILTERS" :key="f.value" class="chip"
            :class="{ 'chip--active': listStatus === f.value }" @click="setStatus(f.value)"
          >{{ f.label }}</button>
        </div>
        <input
          v-model="listSearch" class="form-input" style="margin-top:10px"
          placeholder="Search WO, machine, item..." @input="onListSearch"
        />
      </div>

      <div v-if="loadingList && !rows.length" class="empty"><i class="pi pi-spin pi-spinner"></i> Loading...</div>
      <div v-else-if="!rows.length" class="empty">No knit downs here.</div>

      <div v-for="r in rows" :key="r.name" class="kd-card" @click="openExisting(r.name)">
        <div class="kd-card__top">
          <span class="kd-card__fabric">{{ shortName(r.item_name) }}</span>
          <span class="pill" :class="statusClass(r.status)">{{ r.status }}</span>
        </div>
        <div class="kd-card__ids">
          <span><i class="pi pi-file"></i> {{ r.work_order }}</span>
          <span><i class="pi pi-cog"></i> {{ r.workstation }}</span>
        </div>

        <div class="spec-grid">
          <div v-for="s in specRows(r)" :key="s.label" class="spec" :class="{ 'spec--off': s.off }">
            <span class="spec__label">{{ s.label }}</span>
            <span class="spec__value">{{ s.actual }}</span>
            <span v-if="s.required" class="spec__req">req {{ s.required }}</span>
          </div>
        </div>

        <div v-if="r.yarns && r.yarns.length" class="yarn-lines">
          <div v-for="y in r.yarns" :key="y.item_code" class="yarn-line">
            <span class="yarn-line__name">{{ y.item_name || y.item_code }}</span>
            <span class="yarn-line__pct" :class="{ 'yarn-line__pct--off': pctOff(y) }">
              {{ fmtPct(y.actual_percent) }}<small v-if="pctOff(y)"> (BOM {{ fmtPct(y.bom_percent) }})</small>
            </span>
          </div>
        </div>

        <div v-if="r.approver_remarks" class="remark" :class="r.status === 'Rejected' ? 'remark--bad' : ''">
          <i class="pi pi-comment"></i> {{ r.approver_remarks }}
        </div>

        <div class="kd-card__foot">
          <span class="muted">
            {{ r.requested_by_name || r.requested_by }} · {{ fmtDateTime(r.requested_on) }}
            <template v-if="r.approved_by"> · {{ r.status === 'Approved' ? '✔' : '✖' }} {{ r.approved_by_name }} {{ fmtTime(r.approved_on) }}</template>
          </span>
        </div>

        <div v-if="r.status === 'Pending' && setup.can_approve" class="decide-row" @click.stop>
          <button class="btn btn-reject" @click="startDecision(r, 'Rejected')"><i class="pi pi-times"></i> Reject</button>
          <button class="btn btn-approve" @click="startDecision(r, 'Approved')"><i class="pi pi-check"></i> Approve</button>
        </div>
      </div>
    </div>

    <!-- ══════════════════════ FORM ══════════════════════ -->
    <div v-else class="page-content">
      <div v-if="form.name" class="card status-card">
        <div>
          <div class="form-label">Status</div>
          <span class="pill pill--lg" :class="statusClass(form.status)">{{ form.status }}</span>
        </div>
        <div>
          <div class="form-label">Posted By</div>
          <div class="value">{{ form.requested_by_name || '—' }}</div>
          <div class="muted small">{{ fmtDateTime(form.requested_on) }}</div>
        </div>
        <div v-if="form.approved_by" class="status-card__full">
          <div class="form-label">{{ form.status === 'Approved' ? 'Approved' : 'Rejected' }} By</div>
          <div class="value">{{ form.approved_by_name }} <span class="muted small">· {{ fmtDateTime(form.approved_on) }}</span></div>
          <div v-if="form.approver_remarks" class="remark" :class="form.status === 'Rejected' ? 'remark--bad' : ''">
            <i class="pi pi-comment"></i> {{ form.approver_remarks }}
          </div>
        </div>
      </div>

      <!-- Work Order + machine -->
      <div class="card">
        <label class="form-label">Work Order <span class="req">*</span></label>
        <div v-if="form.work_order" class="wo-picked">
          <div class="wo-picked__main">
            <div class="wo-picked__name">{{ form.work_order }}</div>
            <div class="wo-picked__sub">{{ form.item_name }}</div>
          </div>
          <button v-if="editable && !form.name" class="btn-remove" title="Change" @click="clearWorkOrder"><i class="pi pi-times"></i></button>
        </div>
        <template v-else>
          <div class="search-box">
            <i class="pi pi-search"></i>
            <input
              v-model="woSearch" class="form-input" placeholder="Search WO, item or machine..."
              @input="onWoSearch" @focus="loadWos(woSearch)"
            />
          </div>
          <div v-if="woLoading" class="muted small" style="margin-top:8px"><i class="pi pi-spin pi-spinner"></i> Searching...</div>
          <div v-else-if="woResults.length" class="results">
            <button v-for="w in woResults" :key="w.name" class="result" @click="pickWorkOrder(w.name)">
              <i class="pi pi-plus-circle"></i>
              <span class="result__main">
                <span><strong>{{ w.name }}</strong> · {{ shortName(w.item_name) }}</span>
                <small>{{ w.machines }} · {{ w.status }}</small>
              </span>
            </button>
          </div>
          <div v-else-if="woSearched" class="muted small" style="margin-top:8px">{{ page.noWo }}</div>
        </template>

        <template v-if="form.work_order">
          <label class="form-label" style="margin-top:14px">Machine <span class="req">*</span></label>
          <div v-if="form.name || !editable" class="value">{{ form.workstation }}<span v-if="form.job_card" class="muted small"> · {{ form.job_card }}</span></div>
          <div v-else-if="!machines.length" class="muted small">No knitting machine planned on this work order.</div>
          <div v-else class="machine-list">
            <button
              v-for="m in machines" :key="m.workstation" class="machine"
              :class="{ 'machine--active': form.workstation === m.workstation, 'machine--blocked': machineBlocked(m) }"
              :disabled="machineBlocked(m)" @click="pickMachine(m)"
            >
              <span class="machine__name">{{ m.workstation }}</span>
              <small v-if="m.job_card">{{ m.job_card }}</small>
              <span v-if="m.knit_down" class="pill" :class="statusClass(m.knit_down.status)">{{ m.knit_down.status }}</span>
            </button>
          </div>
        </template>
      </div>

      <!-- Knit down values -->
      <div v-if="form.work_order" class="card">
        <div class="grid-2">
          <div v-for="f in specInputs" :key="f.key">
            <label class="form-label">
              {{ f.label }} <span class="req">*</span>
              <span v-if="f.req && form[f.req] && +form[f.req] !== 0" class="req-hint">req {{ fmtNum(form[f.req]) }}</span>
            </label>
            <input
              v-model="form[f.key]" class="form-input" :class="{ 'form-input--off': specOff(f) }"
              :type="f.text ? 'text' : 'number'" :inputmode="f.text ? 'text' : 'decimal'"
              :placeholder="f.placeholder" :disabled="!editable"
            />
            <div v-if="specOff(f)" class="off-note">{{ specOffText(f) }}</div>
          </div>
        </div>
      </div>

      <!-- Yarn % -->
      <div v-if="form.work_order" class="card">
        <div class="row-head">
          <label class="form-label" style="margin:0">Yarn %</label>
          <span class="small" :class="yarnTotalOk ? 'ok' : 'bad'">Total {{ fmtPct(yarnTotal) }}</span>
        </div>
        <div v-if="!form.yarns.length" class="muted small">No yarns on this work order's BOM.</div>
        <div v-for="y in form.yarns" :key="y.item_code" class="yarn-row">
          <div class="yarn-row__main">
            <div class="yarn-row__name">{{ y.item_name || y.item_code }}</div>
            <div class="muted small">{{ y.item_code }} · BOM {{ fmtPct(y.bom_percent) }}</div>
          </div>
          <div class="pct-input">
            <input v-model="y.actual_percent" type="number" inputmode="decimal" step="0.01" class="form-input" :disabled="!editable" />
            <span>%</span>
          </div>
        </div>
      </div>

      <!-- Photo + remarks -->
      <div v-if="form.work_order" class="card">
        <label class="form-label">Knit Down Photo</label>
        <div v-if="form.photo" class="photo">
          <a :href="form.photo" target="_blank"><img :src="form.photo" alt="Knit down" /></a>
          <button v-if="editable" class="btn-remove photo__remove" @click="form.photo = ''"><i class="pi pi-times"></i></button>
        </div>
        <label v-else-if="editable" class="photo-pick">
          <input type="file" accept="image/*" capture="environment" hidden @change="onPhoto" />
          <i class="pi" :class="uploading ? 'pi-spin pi-spinner' : 'pi-camera'"></i>
          {{ uploading ? 'Uploading...' : 'Take / choose photo' }}
        </label>
        <div v-else class="muted small">No photo</div>

        <label class="form-label" style="margin-top:14px">Remarks</label>
        <textarea v-model="form.knitting_remarks" class="form-input" rows="2" placeholder="Anything production should know" :disabled="!editable"></textarea>
      </div>

      <div v-if="editable" class="card">
        <button class="btn btn-primary btn-full" :disabled="!canSave || saving || uploading" @click="save">
          <i v-if="saving" class="pi pi-spin pi-spinner"></i>
          {{ saving ? 'Saving...' : (form.name ? 'Update Knit Down' : 'Send for Approval') }}
        </button>
        <div v-if="!canSave && missing.length" class="hint-text">
          <i class="pi pi-info-circle"></i><span>Still needed: {{ missing.join(', ') }}</span>
        </div>
      </div>

      <div v-if="form.name && form.can_approve" class="card decide-card">
        <button class="btn btn-reject" @click="startDecision(form, 'Rejected')"><i class="pi pi-times"></i> Reject</button>
        <button class="btn btn-approve" @click="startDecision(form, 'Approved')"><i class="pi pi-check"></i> Approve</button>
      </div>

      <div v-if="form.name && form.status === 'Rejected' && setup.can_create" class="card">
        <button class="btn btn-outline btn-full" @click="openNew({ work_order: form.work_order, workstation: form.workstation })">
          <i class="pi pi-refresh"></i> Post a new knit down for {{ form.workstation }}
        </button>
      </div>

      <div v-if="error" class="error-banner"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>
    </div>

    <div v-if="mode === 'list' && error" class="page-content" style="padding-top:0">
      <div class="error-banner"><i class="pi pi-exclamation-triangle"></i> {{ error }}</div>
    </div>

    <!-- Approve / Reject -->
    <transition name="modal-fade">
      <div v-if="decision" class="modal-overlay" @click.self="decision = null">
        <div class="modal-box">
          <h3 class="modal-title">{{ decision.status === 'Approved' ? 'Approve' : 'Reject' }} {{ decision.name }}</h3>
          <div class="modal-sub">{{ decision.work_order }} · {{ decision.workstation }}</div>
          <textarea
            v-model="decision.remarks" class="form-input" rows="3"
            :placeholder="decision.status === 'Approved' ? 'Remarks (optional)' : 'Why is it rejected? (required)'"
          ></textarea>
          <div v-if="decisionError" class="error-banner" style="margin-top:10px">{{ decisionError }}</div>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="decision = null">Cancel</button>
            <button
              class="btn" :class="decision.status === 'Approved' ? 'btn-approve' : 'btn-reject'"
              :disabled="deciding || (decision.status === 'Rejected' && !decision.remarks.trim())"
              @click="confirmDecision"
            >
              <i v-if="deciding" class="pi pi-spin pi-spinner"></i>
              {{ decision.status === 'Approved' ? 'Approve' : 'Reject' }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="savedName" class="modal-overlay" @click.self="savedName = ''">
        <div class="modal-box" style="text-align:center">
          <i class="pi pi-check-circle modal-icon"></i>
          <h3 class="modal-title">Sent for Approval</h3>
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
  getKnitDownSetup, searchKnitWorkOrders, getKnitDownDefaults, saveKnitDown, getKnitDown,
  listKnitDowns, approveKnitDown, rejectKnitDown, uploadFile,
} from '@/api/frappe'
import AppHeader from '@/components/AppHeader.vue'

const FILTERS = [
  { label: 'Pending', value: 'Pending' },
  { label: 'Approved', value: 'Approved' },
  { label: 'Rejected', value: 'Rejected' },
  { label: 'All', value: '' },
]
const COLLAR_CUFF = 'Collar Cuff'
// One component, two Knit App pages (router props: knitType).
const PAGE_INFO = {
  Fabric: { key: 'knit-down', title: 'Fabric Knit Down', noWo: 'No open fabric knitting work orders found.' },
  [COLLAR_CUFF]: { key: 'collar-cuff-knit-down', title: 'Collar Cuff Knit Down', noWo: 'No open collar / cuff knitting work orders found.' },
}
const SPEC_INPUTS = {
  Fabric: [
    { key: 'dia', req: 'required_dia', label: 'Dia', placeholder: '34' },
    { key: 'gauge', req: 'required_gg', label: 'Gauge', placeholder: '28' },
    { key: 'gsm', req: 'required_gsm', label: 'GSM', placeholder: '154', tolerance: 5 },
    { key: 'loop_length', req: 'required_ll', label: 'Loop Length (cm)', placeholder: '21/13', text: true },
  ],
  [COLLAR_CUFF]: [
    { key: 'size', req: 'required_size', label: 'Size', placeholder: '16.75X3.5', text: true },
    { key: 'no_of_needles', req: 'required_needles', label: 'No of Needles', placeholder: '305' },
    { key: 'no_of_course', req: 'required_course', label: 'Courses', placeholder: '133' },
    { key: 'texture', label: 'Texture', placeholder: '16.5', text: true },
    { key: 'loop_length', req: 'required_ll', label: 'Loop Length', placeholder: '85', text: true },
    { key: 'no_of_ply', req: 'required_ply', label: 'No of Ply', placeholder: '5' },
    { key: 'gauge', req: 'required_gg', label: 'GG', placeholder: '14' },
  ],
}

const props = defineProps({ knitType: { type: String, default: 'Fabric' } })
const page = computed(() => PAGE_INFO[props.knitType] || PAGE_INFO.Fabric)

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const setup = reactive({ can_approve: false, can_create: false })
const rows = ref([])
const listStatus = ref('Pending')
const listSearch = ref('')
const loadingList = ref(false)
const saving = ref(false)
const uploading = ref(false)
const error = ref('')
const savedName = ref('')
const machines = ref([])

const form = reactive(blankForm())

function blankForm() {
  return {
    name: '', status: 'Pending', work_order: '', item_name: '', workstation: '', job_card: '',
    dia: '', gauge: '', gsm: '', loop_length: '', photo: '', knitting_remarks: '',
    required_dia: null, required_gg: null, required_gsm: null, required_ll: null,
    size: '', no_of_needles: '', no_of_course: '', texture: '', no_of_ply: '',
    required_size: null, required_needles: null, required_course: null, required_ply: null,
    knit_type: props.knitType,
    yarns: [], requested_by_name: '', requested_on: '', approved_by: '', approved_by_name: '',
    approved_on: '', approver_remarks: '', can_edit: true, can_approve: false,
  }
}

const mode = computed(() => (route.query.name || route.query.new ? 'form' : 'list'))
const editable = computed(() => (form.name ? form.can_edit : setup.can_create))

const yarnTotal = computed(() => form.yarns.reduce((s, y) => s + (parseFloat(y.actual_percent) || 0), 0))
const yarnTotalOk = computed(() => Math.abs(yarnTotal.value - 100) <= 1)

// A record keeps its own type even if opened from the other page.
const specInputs = computed(() => SPEC_INPUTS[form.knit_type] || SPEC_INPUTS[props.knitType] || SPEC_INPUTS.Fabric)

const missing = computed(() => {
  const m = []
  if (!form.work_order) m.push('Work Order')
  if (!form.workstation) m.push('Machine')
  for (const f of specInputs.value) {
    const ok = f.text ? String(form[f.key] ?? '').trim() : parseFloat(form[f.key]) > 0
    if (!ok) m.push(f.label)
  }
  if (form.yarns.length && !yarnTotalOk.value) m.push('Yarn % totalling 100')
  return m
})
const canSave = computed(() => missing.value.length === 0)

// ── Display helpers ──────────────────────────────────────────────────────
// "...Knitted Fabric(NEO SOFT 150)" → "NEO SOFT 150"
function shortName(name) {
  const m = String(name || '').match(/\(([^()]+)\)\s*$/)
  return m ? m[1].trim() : String(name || '').trim()
}
function fmtNum(v) {
  const n = parseFloat(v)
  return Number.isNaN(n) ? (v ?? '') : String(+n.toFixed(2))
}
function fmtPct(v) { return `${fmtNum(v || 0)}%` }
function pctOff(y) { return Math.abs((parseFloat(y.actual_percent) || 0) - (parseFloat(y.bom_percent) || 0)) > 0.5 }
function statusClass(s) {
  return { Pending: 'pill--amber', Approved: 'pill--green', Rejected: 'pill--red' }[s] || 'pill--grey'
}
function deviation(actual, required) {
  const a = parseFloat(actual), r = parseFloat(required)
  if (!(a > 0) || !(r > 0)) return null
  return ((a - r) / r) * 100
}
function specOff(f) {
  if (f.text || !f.req) return false
  const d = deviation(form[f.key], form[f.req])
  return d !== null && Math.abs(d) > (f.tolerance ?? 0)
}
function specOffText(f) {
  const d = deviation(form[f.key], form[f.req])
  return `${d > 0 ? '+' : ''}${d.toFixed(1)}% vs required`
}
function specRows(r) {
  if (r.knit_type === COLLAR_CUFF) {
    const row = (label, actual, required) => {
      const off = !!required && +required !== 0 && +required !== +actual
        && String(required).trim().toUpperCase() !== String(actual ?? '').trim().toUpperCase()
      return { label, actual: actual ?? '', required: off ? `${required}` : '', off }
    }
    return [
      row('Size', r.size, r.required_size),
      row('Needles', fmtNum(r.no_of_needles), r.required_needles),
      row('Course', fmtNum(r.no_of_course), r.required_course),
      { label: 'Texture', actual: r.texture || '', required: '', off: false },
      { label: 'LL', actual: r.loop_length, required: r.required_ll ? `${r.required_ll}` : '', off: false },
      row('Ply', fmtNum(r.no_of_ply), r.required_ply),
      { label: 'GG', actual: fmtNum(r.gauge), required: '', off: false },
    ]
  }
  const gsmDev = deviation(r.gsm, r.required_gsm)
  return [
    { label: 'Dia', actual: fmtNum(r.dia), required: r.required_dia && +r.required_dia !== +r.dia ? fmtNum(r.required_dia) : '', off: r.required_dia && +r.required_dia !== +r.dia },
    { label: 'GG', actual: fmtNum(r.gauge), required: r.required_gg && +r.required_gg !== +r.gauge ? fmtNum(r.required_gg) : '', off: r.required_gg && +r.required_gg !== +r.gauge },
    { label: 'GSM', actual: fmtNum(r.gsm), required: r.required_gsm ? fmtNum(r.required_gsm) : '', off: gsmDev !== null && Math.abs(gsmDev) > 5 },
    { label: 'LL', actual: r.loop_length, required: r.required_ll ? `${r.required_ll}` : '', off: false },
  ]
}
function machineBlocked(m) {
  return !!(m.knit_down && ['Pending', 'Approved'].includes(m.knit_down.status))
}
function fmtDateTime(dt) {
  if (!dt) return ''
  const [d, t = ''] = String(dt).split(' ')
  const [y, mo, day] = d.split('-')
  return `${day}-${mo}-${y} ${t.slice(0, 5)}`
}
function fmtTime(dt) { return dt ? String(dt).split(' ')[1]?.slice(0, 5) || '' : '' }

// ── List ─────────────────────────────────────────────────────────────────
async function loadList() {
  loadingList.value = true
  try {
    rows.value = await listKnitDowns({ status: listStatus.value, txt: listSearch.value, knitType: props.knitType })
  } catch (e) {
    error.value = e.message
  } finally {
    loadingList.value = false
  }
}
let listTimer = null
function onListSearch() { clearTimeout(listTimer); listTimer = setTimeout(loadList, 300) }
function setStatus(v) { listStatus.value = v; loadList() }

function openNew(prefill = {}) { router.push({ query: { new: '1', ...prefill } }) }
function openExisting(name) { router.push({ query: { name } }) }

// ── Work Order + machine ─────────────────────────────────────────────────
const woSearch = ref('')
const woResults = ref([])
const woLoading = ref(false)
const woSearched = ref(false)
async function loadWos(txt) {
  woLoading.value = true
  try {
    woResults.value = await searchKnitWorkOrders(txt, props.knitType)
    woSearched.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    woLoading.value = false
  }
}
let woTimer = null
function onWoSearch() { clearTimeout(woTimer); woTimer = setTimeout(() => loadWos(woSearch.value), 250) }

async function pickWorkOrder(name, workstation = '') {
  error.value = ''
  try {
    const d = await getKnitDownDefaults(name)
    const wo = d.work_order
    Object.assign(form, {
      work_order: wo.name, item_name: wo.item_name,
      required_dia: wo.required_dia ?? null, required_gg: wo.required_gg ?? null,
      required_gsm: wo.required_gsm ?? null, required_ll: wo.required_ll ?? null,
      required_size: wo.required_size ?? null, required_needles: wo.required_needles ?? null,
      required_course: wo.required_course ?? null, required_ply: wo.required_ply ?? null,
      knit_type: wo.knit_type || props.knitType,
      // Dia / Gauge are the machine's — start from the WO's values.
      dia: form.dia || (+wo.required_dia ? wo.required_dia : ''),
      gauge: form.gauge || (+wo.required_gg ? wo.required_gg : ''),
      yarns: d.yarns.map(y => ({ ...y, actual_percent: y.bom_percent })),
      workstation: '', job_card: '',
    })
    machines.value = d.machines
    const pre = d.machines.find(m => m.workstation === workstation && !machineBlocked(m))
      || (d.machines.length === 1 && !machineBlocked(d.machines[0]) ? d.machines[0] : null)
    if (pre) pickMachine(pre)
    woSearch.value = ''
  } catch (e) {
    error.value = e.message
  }
}
function pickMachine(m) {
  form.workstation = m.workstation
  form.job_card = m.job_card || ''
}
function clearWorkOrder() {
  Object.assign(form, blankForm())
  machines.value = []
  loadWos('')
}

// ── Photo ────────────────────────────────────────────────────────────────
// Downscale to ≤1280px JPEG before upload: phone photos are 3–8 MB.
function shrink(file, max = 1280) {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height))
      const c = document.createElement('canvas')
      c.width = Math.round(img.width * scale)
      c.height = Math.round(img.height * scale)
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height)
      URL.revokeObjectURL(url)
      c.toBlob(b => resolve(b || file), 'image/jpeg', 0.82)
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file) }
    img.src = url
  })
}
async function onPhoto(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const blob = await shrink(file)
    const stamp = new Date().toISOString().replace(/\D/g, '').slice(0, 14)
    form.photo = await uploadFile(blob, `knit-down-${(form.work_order || 'wo').replace(/\W+/g, '-')}-${stamp}.jpg`)
  } catch (err) {
    error.value = err.message
  } finally {
    uploading.value = false
  }
}

// ── Save ─────────────────────────────────────────────────────────────────
function applyDoc(d) {
  Object.assign(form, blankForm(), {
    ...d,
    item_name: d.item_name || '',
    photo: d.photo || '',
    knitting_remarks: d.knitting_remarks || '',
    yarns: (d.yarns || []).map(y => ({
      item_code: y.item_code, item_name: y.item_name, bom_percent: y.bom_percent, actual_percent: y.actual_percent,
    })),
  })
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''
  const wasNew = !form.name
  try {
    const d = await saveKnitDown({
      name: form.name || undefined,
      work_order: form.work_order,
      workstation: form.workstation,
      job_card: form.job_card || '',
      dia: form.dia, gauge: form.gauge, gsm: form.gsm,
      loop_length: String(form.loop_length ?? '').trim(),
      size: String(form.size ?? '').trim(), texture: String(form.texture ?? '').trim(),
      no_of_needles: form.no_of_needles, no_of_course: form.no_of_course, no_of_ply: form.no_of_ply,
      photo: form.photo || '',
      knitting_remarks: form.knitting_remarks || '',
      yarns: form.yarns.map(y => ({ item_code: y.item_code, actual_percent: y.actual_percent })),
    })
    applyDoc(d)
    if (wasNew) {
      savedName.value = d.name
      router.replace({ query: { name: d.name } })
    }
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

// ── Approve / Reject ─────────────────────────────────────────────────────
const decision = ref(null)
const deciding = ref(false)
const decisionError = ref('')
function startDecision(r, status) {
  decisionError.value = ''
  decision.value = { name: r.name, work_order: r.work_order, workstation: r.workstation, status, remarks: '' }
}
async function confirmDecision() {
  const d = decision.value
  deciding.value = true
  decisionError.value = ''
  try {
    const doc = d.status === 'Approved'
      ? await approveKnitDown(d.name, d.remarks.trim())
      : await rejectKnitDown(d.name, d.remarks.trim())
    decision.value = null
    if (mode.value === 'form' && form.name === doc.name) applyDoc(doc)
    const i = rows.value.findIndex(r => r.name === doc.name)
    if (i >= 0) {
      if (listStatus.value === 'Pending') rows.value.splice(i, 1)
      else rows.value[i] = { ...rows.value[i], ...doc, yarns: rows.value[i].yarns }
    }
  } catch (e) {
    decisionError.value = e.message
  } finally {
    deciding.value = false
  }
}

// ── Routing ──────────────────────────────────────────────────────────────
async function syncWithRoute() {
  error.value = ''
  if (route.query.name) {
    if (form.name !== route.query.name) {
      try { applyDoc(await getKnitDown(route.query.name)) } catch (e) { error.value = e.message }
    }
  } else if (route.query.new) {
    Object.assign(form, blankForm())
    machines.value = []
    woResults.value = []
    woSearched.value = false
    if (route.query.work_order) await pickWorkOrder(route.query.work_order, route.query.workstation || '')
    else loadWos('')
  } else {
    loadList()
  }
}

onMounted(async () => {
  try { Object.assign(setup, await getKnitDownSetup()) } catch (e) { error.value = e.message }
  // Knitting team mostly wants to see everything they posted; approvers the queue.
  if (!setup.can_approve) listStatus.value = ''
  syncWithRoute()
})
watch(() => [route.query.name, route.query.new, route.query.work_order], syncWithRoute)
// Fabric ↔ Collar Cuff reuses this component (same view, new props): start clean.
watch(() => props.knitType, () => {
  Object.assign(form, blankForm())
  machines.value = []
  rows.value = []
  woResults.value = []
  woSearched.value = false
  woSearch.value = ''
  listSearch.value = ''
  syncWithRoute()
})
</script>

<style scoped>
.page-content { padding: 16px; max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.card--tight { padding: 12px; }
.form-label { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
.req { color: #dc2626; }
.req-hint { margin-left: auto; text-transform: none; font-weight: 600; color: #0f6e56; background: #f0fdf4; border-radius: 6px; padding: 1px 6px; }
.form-input {
  width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px;
  font-size: 15px; box-sizing: border-box; font-family: inherit; background: #fff; min-height: 42px;
}
.form-input:disabled { background: #f8fafc; color: #0f172a; }
.form-input--off { border-color: #f59e0b; background: #fffbeb; }
.off-note { font-size: 12px; color: #b45309; margin-top: 4px; font-weight: 600; }
textarea.form-input { resize: vertical; }
.muted { color: #64748b; }
.small { font-size: 12px; }
.ok { color: #166534; font-weight: 700; }
.bad { color: #dc2626; font-weight: 700; }
.value { font-size: 14px; color: #0f172a; font-weight: 600; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 1px solid #e2e8f0; background: #fff; color: #475569; border-radius: 999px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.chip--active { background: var(--app-primary, #0f6e56); border-color: var(--app-primary, #0f6e56); color: #fff; }

.kd-card { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; flex-direction: column; gap: 8px; cursor: pointer; }
.kd-card__top { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.kd-card__fabric { font-weight: 800; font-size: 16px; color: #0f172a; }
.kd-card__ids { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: #334155; font-weight: 600; }
.kd-card__ids .pi { font-size: 12px; color: #64748b; margin-right: 3px; }
.kd-card__foot { font-size: 12px; color: #64748b; }

.spec-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.spec { background: #f8fafc; border-radius: 8px; padding: 6px 8px; display: flex; flex-direction: column; }
.spec--off { background: #fffbeb; box-shadow: inset 0 0 0 1px #f59e0b; }
.spec__label { font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; }
.spec__value { font-size: 15px; font-weight: 800; color: #0f172a; }
.spec__req { font-size: 10px; color: #64748b; }

.yarn-lines { display: flex; flex-direction: column; gap: 3px; }
.yarn-line { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; color: #334155; }
.yarn-line__name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.yarn-line__pct { font-weight: 700; white-space: nowrap; }
.yarn-line__pct--off { color: #b45309; }
.yarn-line__pct small { font-weight: 500; }

.remark { font-size: 13px; color: #166534; background: #f0fdf4; border-radius: 8px; padding: 6px 10px; margin-top: 4px; }
.remark--bad { color: #991b1b; background: #fee2e2; }

.decide-row, .decide-card { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.decide-row .btn, .decide-card .btn { padding: 11px; font-weight: 700; }

.status-card { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.status-card__full { grid-column: 1 / -1; }

.wo-picked { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; }
.wo-picked__main { flex: 1; min-width: 0; }
.wo-picked__name { font-weight: 800; color: #0f172a; }
.wo-picked__sub { font-size: 12px; color: #64748b; overflow-wrap: anywhere; }

.search-box { position: relative; }
.search-box .pi { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #94a3b8; font-size: 13px; }
.search-box .form-input { padding-left: 34px; }
.results { margin-top: 8px; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; max-height: 340px; overflow-y: auto; }
.result { width: 100%; display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; background: #fff; border: none; border-bottom: 1px solid #f1f5f9; text-align: left; cursor: pointer; font-family: inherit; font-size: 13px; color: #334155; }
.result:last-child { border-bottom: none; }
.result:hover { background: #f0fdf4; }
.result .pi { color: #0f6e56; margin-top: 2px; }
.result__main { display: flex; flex-direction: column; gap: 2px; min-width: 0; overflow-wrap: anywhere; }
.result__main small { color: #64748b; font-size: 12px; }

.machine-list { display: flex; flex-wrap: wrap; gap: 8px; }
.machine { border: 1.5px solid #e2e8f0; background: #fff; border-radius: 10px; padding: 8px 12px; cursor: pointer; display: flex; flex-direction: column; align-items: flex-start; gap: 3px; font-family: inherit; }
.machine__name { font-weight: 800; color: #0f172a; font-size: 14px; }
.machine small { color: #64748b; font-size: 11px; }
.machine--active { border-color: #0f6e56; background: #f0fdf4; }
.machine--blocked { opacity: 0.6; cursor: not-allowed; }

.row-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.yarn-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
.yarn-row:last-child { border-bottom: none; }
.yarn-row__main { flex: 1; min-width: 0; }
.yarn-row__name { font-size: 14px; font-weight: 600; color: #0f172a; }
.pct-input { display: flex; align-items: center; gap: 4px; width: 110px; }
.pct-input .form-input { text-align: right; }

.photo { position: relative; display: inline-block; }
.photo img { max-width: 100%; max-height: 260px; border-radius: 10px; display: block; }
.photo__remove { position: absolute; top: 6px; right: 6px; background: rgba(255,255,255,0.9); border-radius: 999px; }
.photo-pick { display: flex; align-items: center; justify-content: center; gap: 8px; border: 1.5px dashed #94a3b8; border-radius: 10px; padding: 18px; color: #475569; font-weight: 600; cursor: pointer; }

.btn-remove { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px 6px; font-size: 14px; }
.btn-remove:hover { color: #dc2626; }

.pill { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap; display: inline-block; }
.pill--lg { font-size: 13px; padding: 5px 12px; }
.pill--green { background: #dcfce7; color: #166534; }
.pill--grey { background: #f1f5f9; color: #475569; }
.pill--amber { background: #fef3c7; color: #92400e; }
.pill--red { background: #fee2e2; color: #991b1b; }

.empty { text-align: center; color: #94a3b8; padding: 28px 12px; font-size: 14px; }
.hint-text { font-size: 12px; color: #64748b; margin-top: 8px; display: flex; gap: 6px; align-items: flex-start; }

.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-family: inherit; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { background: #94a3b8; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; padding: 10px 14px; }
.btn-approve { background: #16a34a; color: #fff; padding: 10px 14px; }
.btn-reject { background: #fff; border: 1.5px solid #dc2626; color: #dc2626; padding: 10px 14px; }
.btn-full { width: 100%; padding: 12px; }

.error-banner { background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); display: flex; align-items: center; justify-content: center; z-index: 500; padding: 20px; }
.modal-box { background: #fff; border-radius: 14px; padding: 22px 20px; width: 100%; max-width: 400px; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.modal-icon { font-size: 40px; color: #16a34a; margin-bottom: 10px; display: block; }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 4px; color: #0f172a; }
.modal-sub { font-size: 13px; color: #64748b; margin-bottom: 12px; }
.modal-docno { font-size: 15px; font-weight: 700; color: #0f6e56; background: #f0fdf4; border-radius: 8px; padding: 10px 14px; margin: 10px 0 18px; }
.modal-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }

@media (max-width: 520px) {
  .spec-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
