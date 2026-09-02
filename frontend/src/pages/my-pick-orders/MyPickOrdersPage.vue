<template>
  <div class="page">
    <AppHeader title="My Pick Orders" active="my-pick-orders" :username="auth.username" :designation="auth.designation" :show-back="true" />
    <div class="page-content">

      <div v-if="store.listLoading" class="card state-msg">
        <i class="pi pi-spin pi-spinner"></i> Loading your pick orders...
      </div>

      <div v-else-if="store.listError" class="card state-msg error">
        <i class="pi pi-exclamation-triangle"></i> {{ store.listError }}
      </div>

      <div v-else-if="!store.myOrders.length" class="card state-msg">
        <i class="pi pi-check-circle"></i> No pick orders assigned to you right now.
      </div>

      <div v-else class="order-list">
        <button
          v-for="o in store.myOrders" :key="o.name"
          class="order-card" @click="openOrder(o.name)"
        >
          <div class="order-card__top">
            <span class="order-card__name">{{ o.name }}</span>
            <span class="status-badge" :class="statusClass(o.status)">{{ o.status }}</span>
          </div>
          <div class="order-card__doc">
            {{ o.pick_type }}<span v-if="o.work_order"> · {{ o.work_order }}</span><span v-if="o.sales_order"> · {{ o.sales_order }}</span>
          </div>
          <div class="order-card__wh">
            <span>{{ o.source_warehouse }}</span>
            <i class="pi pi-arrow-right"></i>
            <span>{{ o.target_warehouse }}</span>
          </div>
          <div class="order-card__meta">
            <span>{{ o.picked_rolls || 0 }} roll(s)</span>
            <span>{{ fmt(o.picked_qty) }} / {{ fmt(o.pick_qty) }} kg</span>
            <span>{{ o.posting_date }}</span>
          </div>
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePickOrderStore } from '@/stores/pickOrder'
import AppHeader from '@/components/AppHeader.vue'

const auth = useAuthStore()
const store = usePickOrderStore()
const router = useRouter()

onMounted(() => store.loadMyOrders())

function openOrder(name) {
  router.push({ path: '/knit-app/roll-wise-pick-order-execution', query: { order: name } })
}

function statusClass(status) {
  return status === 'In Progress' ? 'status-badge--progress' : 'status-badge--pending'
}

function fmt(n) {
  return (Number(n) || 0).toFixed(2)
}
</script>

<style scoped>
.page-content { padding: 16px; max-width: 640px; margin: 0 auto; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.state-msg {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  color: #64748b; padding: 32px 16px; text-align: center;
}
.state-msg.error { color: #991b1b; }

.order-list { display: flex; flex-direction: column; gap: 10px; }
.order-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px;
  text-align: left; cursor: pointer; display: flex; flex-direction: column; gap: 6px;
  font: inherit;
}
.order-card:active { background: #f8fafc; }
.order-card__top { display: flex; justify-content: space-between; align-items: center; }
.order-card__name { font-weight: 700; color: #0f172a; font-size: 15px; }
.order-card__doc { font-size: 13px; color: #475569; }
.order-card__wh { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #64748b; }
.order-card__meta { display: flex; gap: 14px; font-size: 12px; color: #94a3b8; margin-top: 2px; }

.status-badge {
  font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; text-transform: uppercase;
}
.status-badge--pending { background: #fef3c7; color: #92400e; }
.status-badge--progress { background: #dbeafe; color: #1e40af; }
</style>
