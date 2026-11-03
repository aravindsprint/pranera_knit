<template>
  <div class="page">
    <AppHeader title="Create Pick Order" active="create-pick-order" :username="auth.username" :designation="auth.designation" :show-back="true" />
    <div class="page-content">

      <div class="card">
        <label class="form-label">Pick Type <span class="req">*</span></label>
        <select v-model="store.pickType" class="form-input" @change="onPickTypeChange">
          <option value="" disabled>Select pick type</option>
          <option value="From Work Order">From Work Order</option>
          <option value="To Work Order">To Work Order</option>
          <option value="From Batch">From Batch</option>
          <option value="Manual Roll Pick">Manual Roll Pick</option>
          <option value="To Sales Order">To Sales Order</option>
        </select>

        <label class="form-label" style="margin-top:14px">Roll Source <span class="req">*</span></label>
        <select v-model="store.rollSource" class="form-input">
          <option value="Roll">Roll (new stickers)</option>
          <option value="QI Report Details">QI Report Details (old rolls)</option>
        </select>
        <div v-if="store.rollSource === 'QI Report Details'" class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span>For old rolls with stickers like item#batch#lot#roll_no — weight and UOM come from the QI Report Details roll row.</span>
        </div>

        <template v-if="store.needsDocument">
          <label class="form-label" style="margin-top:14px">Work Order <span class="req">*</span></label>
          <input
            v-model="store.documentName" list="wo-list" class="form-input"
            placeholder="Search work order..."
          />
          <datalist id="wo-list">
            <option v-for="wo in store.workOrders" :key="wo.name" :value="wo.name">{{ wo.production_item }}</option>
          </datalist>
          <div v-if="store.pickType === 'To Work Order'" class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Rolls scanned for this Order must belong to the same Project as this Work Order.</span>
          </div>
          <label v-if="store.offersBatchRestriction" class="checkbox-row" style="margin-top:10px">
            <input type="checkbox" v-model="store.restrictToBatches" />
            <span>Restrict this pick to specific batch(es)</span>
          </label>
          <div v-if="store.offersBatchRestriction && !store.restrictToBatches" class="hint-text">
            <i class="pi pi-info-circle"></i>
            <span>Off by default — the worker can scan any batch this Work Order actually produced. Turn this on to name the exact batch(es) allowed instead.</span>
          </div>
        </template>

        <template v-if="store.needsSalesOrder">
          <label class="form-label" style="margin-top:14px">Sales Order <span class="req">*</span></label>
          <input
            v-model="store.salesOrder" list="so-list" class="form-input"
            placeholder="Search sales order..." @input="onSalesOrderSearch"
          />
          <datalist id="so-list">
            <option v-for="so in store.salesOrders" :key="so.name" :value="so.name">{{ so.customer }}</option>
          </datalist>
        </template>
      </div>

      <div class="card">
        <label class="form-label">Source Warehouse <span class="req">*</span></label>
        <AutoComplete
          v-model="store.sourceWarehouse"
          :options="store.sourceWarehouses"
          placeholder="Search warehouse..."
        />
        <div class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span><template v-if="store.userBuilding">Warehouses of your building ({{ store.userBuilding }}). </template>This is a starting default — the worker can adjust it in the app if needed before scanning.</span>
        </div>

        <label class="form-label" style="margin-top:14px">Target Warehouse <span class="req">*</span></label>
        <AutoComplete
          v-model="store.targetWarehouse"
          :options="store.targetWarehouses"
          placeholder="Search warehouse..."
        />
      </div>

      <div class="card" v-if="store.needsBatchItems">
        <label class="form-label">Batch Items <span class="req">*</span></label>
        <div v-for="(row, i) in store.batchItems" :key="i" class="batch-item">
          <div class="batch-row">
            <input
              v-model="row.batch" list="batch-list" class="form-input"
              placeholder="Search batch..." @input="onBatchSearch(row, $event)" @change="store.loadBatchInfo(row)"
            />
            <input v-model.number="row.qty" type="number" min="0" step="0.01" class="form-input batch-row__qty"
                   :placeholder="row.uom ? `Qty (${row.uom})` : 'Qty'" />
            <button class="btn-remove" @click="store.removeBatchItemRow(i)" title="Remove row">
              <i class="pi pi-times"></i>
            </button>
          </div>
          <div v-if="row.loading" class="batch-meta"><i class="pi pi-spin pi-spinner"></i> Loading batch…</div>
          <div v-else-if="row.error" class="batch-meta batch-meta--err">{{ row.error }}</div>
          <template v-else-if="row.item">
            <div class="batch-meta">
              <span class="batch-meta__item">{{ row.item }}</span>
              <span v-if="row.uom" class="batch-meta__uom">{{ row.uom }}</span>
            </div>
            <AutoComplete
              v-model="row.warehouse"
              :options="row.whOptions"
              placeholder="Warehouse for this batch..."
            />
          </template>
        </div>
        <datalist id="batch-list">
          <option v-for="b in store.batches" :key="b.name" :value="b.name">{{ b.item }}</option>
        </datalist>
        <button class="btn btn-outline btn-full" style="margin-top:6px" @click="store.addBatchItemRow()">
          <i class="pi pi-plus"></i> Add Row
        </button>
        <div class="hint-text" style="margin-top:10px">
          <i class="pi pi-info-circle"></i>
          <span>Item and UOM come from the batch. Warehouse lists your building's warehouses, ones holding the batch first — add another row for the same batch to split it across warehouses. Pick Qty is set automatically from the total below: <strong>{{ fmt(store.batchItemsTotal) }} kg</strong> (±3% tolerance: {{ toleranceRange }}).</span>
        </div>
      </div>

      <div class="card" v-else>
        <label class="form-label">Pick Qty (kg) <span class="req">*</span></label>
        <input v-model.number="store.pickQty" type="number" min="0" step="0.01" class="form-input" placeholder="e.g. 100" />
        <div class="hint-text">
          <i class="pi pi-info-circle"></i>
          <span>The worker will scan rolls until the total falls within ±3% of this target ({{ toleranceRange }}).</span>
        </div>
      </div>

      <div class="card">
        <label class="form-label">Assigned To <span class="req">*</span></label>
        <input
          v-model="assignedToLabel" list="user-list" class="form-input"
          placeholder="Search user..." @input="onUserSearch"
        />
        <datalist id="user-list">
          <option v-for="u in store.users" :key="u.name" :value="u.full_name">{{ u.name }}</option>
        </datalist>

        <label class="form-label" style="margin-top:14px">Remarks <span class="optional">(optional)</span></label>
        <textarea v-model="store.remarks" class="form-input" rows="2" placeholder="Any notes for the worker"></textarea>
      </div>

      <div class="card">
        <button class="btn btn-primary btn-full" @click="submit" :disabled="!store.canSubmit || store.submitting">
          <i v-if="store.submitting" class="pi pi-spin pi-spinner"></i>
          {{ store.submitting ? 'Creating...' : 'Create Pick Order' }}
        </button>
        <div v-if="store.error" class="error-banner" style="margin-top:12px">
          <i class="pi pi-exclamation-triangle"></i> {{ store.error }}
        </div>
      </div>

    </div>

    <transition name="modal-fade">
      <div v-if="showSuccessModal" class="modal-overlay" @click.self="closeSuccessModal">
        <div class="modal-box">
          <i class="pi pi-check-circle modal-icon"></i>
          <h3 class="modal-title">Pick Order Created</h3>
          <p class="modal-msg">Assigned successfully.</p>
          <div v-if="createdName" class="modal-docno">{{ createdName }}</div>
          <button class="btn btn-primary btn-full" @click="closeSuccessModal">OK</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCreatePickOrderStore } from '@/stores/createPickOrder'
import AppHeader from '@/components/AppHeader.vue'
import AutoComplete from '@/components/AutoComplete.vue'

const auth = useAuthStore()
const store = useCreatePickOrderStore()
const router = useRouter()

const assignedToLabel = ref('')
const showSuccessModal = ref(false)
const createdName = ref('')

onMounted(() => store.loadLookups())
onBeforeUnmount(() => store.reset())

function onPickTypeChange() {
  store.documentName = ''
  store.salesOrder = ''
  store.restrictToBatches = false
}

function onUserSearch() {
  const match = store.users.find(u => u.full_name === assignedToLabel.value)
  store.assignedTo = match ? match.name : ''
  store.searchUsers(assignedToLabel.value)
}

function onSalesOrderSearch(e) {
  store.searchSalesOrders(e.target.value)
}

function onBatchSearch(row, e) {
  const v = e.target.value
  // Picked from the suggestions → load its item / warehouses straight away.
  if (store.batches.some(b => b.name === v)) store.loadBatchInfo(row)
  store.searchBatches(v)
}

const toleranceRange = computed(() => {
  const qty = Number(store.pickQty) || 0
  if (!qty) return '—'
  return `${(qty * 0.97).toFixed(2)} – ${(qty * 1.03).toFixed(2)} kg`
})

function fmt(n) {
  return (Number(n) || 0).toFixed(2)
}

async function submit() {
  const result = await store.submit()
  if (result?.name) {
    createdName.value = result.name
    showSuccessModal.value = true
  }
}

function closeSuccessModal() {
  showSuccessModal.value = false
  router.push('/knit-app/my-pick-orders')
}
</script>

<style scoped>
.page-content { padding: 16px; max-width: 640px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }

.form-label { display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 8px; }
.req { color: #dc2626; }
.optional { color: #94a3b8; font-weight: 400; text-transform: none; font-size: 11px; }
.form-input {
  width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px;
  font-size: 14px; box-sizing: border-box; font-family: inherit; background: #fff;
}
textarea.form-input { resize: vertical; }

.batch-item { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; margin-bottom: 8px; }
.batch-item .batch-row { margin-bottom: 0; flex-wrap: wrap; }
.batch-item .batch-row > .form-input:first-child { flex: 1 1 100%; }
.batch-item .batch-row__qty { flex: 1 1 auto; }
.batch-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #475569; margin: 8px 0 6px; overflow-wrap: anywhere; }
.batch-meta__item { font-weight: 600; color: #0f172a; }
.batch-meta__uom { background: #f1f5f9; border-radius: 6px; padding: 1px 6px; font-weight: 600; }
.batch-meta--err { color: #991b1b; }
.batch-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.batch-row .form-input { flex: 1; min-width: 0; }
.batch-row__qty { flex: 0 0 90px; }
.btn-remove {
  background: none; border: none; color: #94a3b8; cursor: pointer;
  padding: 4px 6px; flex-shrink: 0; font-size: 14px;
}
.btn-remove:hover { color: #dc2626; }

.hint-text {
  font-size: 12px; color: #64748b; margin-top: 8px; display: flex; align-items: flex-start; gap: 6px;
}
.hint-text i { margin-top: 1px; flex-shrink: 0; }
.hint-text span { flex: 1; min-width: 0; overflow-wrap: anywhere; line-height: 1.5; }

.checkbox-row {
  display: flex; align-items: center; gap: 8px; font-size: 13px; color: #334155; cursor: pointer;
}
.checkbox-row input { width: 16px; height: 16px; flex-shrink: 0; }

.btn { border: none; border-radius: 10px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #0f6e56; color: #fff; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-outline { background: #fff; border: 1.5px solid #0f6e56; color: #0f6e56; padding: 10px; }
.btn-full { width: 100%; padding: 12px; }

.error-banner {
  background: #fee2e2; color: #991b1b; padding: 10px; border-radius: 8px; text-align: center;
  display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 13px;
}

.modal-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 500; padding: 20px;
}
.modal-box {
  background: #fff; border-radius: 14px; padding: 28px 24px; width: 100%; max-width: 360px;
  text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
}
.modal-icon { font-size: 40px; color: #16a34a; margin-bottom: 10px; display: block; }
.modal-title { font-size: 17px; font-weight: 700; margin: 0 0 8px; color: #0f172a; }
.modal-msg { font-size: 13px; color: #475569; margin: 0 0 14px; }
.modal-docno {
  font-size: 15px; font-weight: 700; color: #0f6e56; background: #f0fdf4;
  border-radius: 8px; padding: 10px 14px; margin-bottom: 18px; word-break: break-all;
}
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>
