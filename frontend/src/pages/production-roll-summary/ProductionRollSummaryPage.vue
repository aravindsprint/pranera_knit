<template>
  <div class="page">
    <AppHeader title="Production Summary" active="production-summary" :username="auth.username" :designation="auth.designation" :show-back="true" />
    <div class="page-content">
      <div class="card"><p style="color:#64748b;padding:24px;text-align:center">Page ready for implementation — mirrors Ionic Production Roll Summary page.</p></div>
    </div>
  </div>
</template>
<script setup>
import { useAuthStore } from '@/stores/auth'
import AppHeader from '@/components/AppHeader.vue'
import { useRouter } from "vue-router"
const auth = useAuthStore()
const router = useRouter()
</script>
<style scoped>
.icon-btn { background: rgba(255,255,255,0.2); border: none; color: white; width: 36px; height: 36px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
</style>
