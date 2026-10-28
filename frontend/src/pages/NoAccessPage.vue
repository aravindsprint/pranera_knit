<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;text-align:center">
    <div style="max-width:360px">
      <div style="font-size:56px;margin-bottom:16px">🔒</div>

      <!-- One page blocked by its roles (Desk → Knit App Page) -->
      <template v-if="pageLabel">
        <h1 style="font-size:20px;font-weight:700;color:#1e293b;margin-bottom:8px">No access to {{ pageLabel }}</h1>
        <p style="color:#64748b;margin-bottom:24px">
          Your role doesn't allow this page. Ask your administrator if you need it.
        </p>
        <button v-if="firstAllowed" class="na-btn" @click="router.replace(firstAllowed.path)">
          Go to {{ firstAllowed.label }}
        </button>
      </template>

      <!-- No access to the app at all -->
      <template v-else>
        <h1 style="font-size:20px;font-weight:700;color:#1e293b;margin-bottom:8px">Access Denied</h1>
        <p style="color:#64748b;margin-bottom:24px">
          Your account does not have permission to access the Knitting App.<br>
          Please contact your ERPNext administrator to enable access.
        </p>
        <a href="/app" style="color:#0f6e56;font-weight:600">← Back to ERPNext</a>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PAGES } from '@/pages'
import { usePageAccessStore } from '@/stores/pageAccess'

const route = useRoute()
const router = useRouter()
const access = usePageAccessStore()

const pageLabel = computed(() => PAGES.find(p => p.key === route.query.page)?.label || '')
const firstAllowed = computed(() => access.visiblePages[0] || null)
</script>

<style scoped>
.na-btn {
  background: #0f6e56; color: #fff; border: none; border-radius: 10px;
  padding: 12px 20px; font-size: 14px; font-weight: 600; cursor: pointer;
}
</style>
