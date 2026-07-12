<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <img :src="logoUrl" alt="Knitting" class="logo-img" />
        <h1>Knitting</h1>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label class="form-label">Email</label>
          <input
            v-model="email"
            type="email"
            class="form-input"
            placeholder="Enter your email"
            autocomplete="email"
            required
          />
        </div>

        <div class="form-group" style="position:relative">
          <label class="form-label">Password</label>
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            class="form-input"
            placeholder="Enter your password"
            autocomplete="current-password"
            required
          />
          <button type="button" class="eye-toggle" @click="showPassword = !showPassword" :aria-label="showPassword ? 'Hide password' : 'Show password'">
            <svg v-if="!showPassword" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a19.66 19.66 0 0 1 5.06-5.94M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 11 8 11 8a19.7 19.7 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
              <line x1="1" y1="1" x2="23" y2="23"/>
            </svg>
          </button>
        </div>

        <div v-if="errorMsg" class="error-box">
          ⚠️ {{ errorMsg }}
        </div>

        <button type="submit" class="btn btn-primary btn-full" :disabled="loading || !isOnline">
          <span v-if="loading" class="btn-spinner"></span>
          <span>{{ loading ? loadingMsg : (isOnline ? 'Login' : 'Offline') }}</span>
        </button>
      </form>

      <div class="offline-note" v-if="!isOnline">
        📵 Offline — login requires network
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isOnline } from '@/composables/useSync'

const route = useRoute()
const auth = useAuthStore()

// Served by Frappe at runtime from the app's own public/images/ folder —
// deliberately a plain string, not a static template src=, so Vite doesn't
// try to resolve/bundle it as a frontend build asset (it isn't one).
const logoUrl = '/assets/pranera_knit/images/logo.svg'

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const loadingMsg = ref('Logging in...')
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  loading.value = true
  loadingMsg.value = 'Logging in...'

  try {
    await auth.login(email.value, password.value)
    loadingMsg.value = 'Redirecting...'
    const dest = typeof route.query.redirect === 'string' ? route.query.redirect : '/knit-app/home'
    // Full page reload on purpose — re-runs main.js against the fresh
    // session cookie from scratch, same as a manual browser refresh
    // (which is the one thing that's proven to reliably pick up a brand
    // new login). An SPA router.replace() here was the unreliable path.
    window.location.href = dest
  } catch (err) {
    errorMsg.value = err.message || 'Login failed'
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f6e56 0%, #1d9e75 100%);
  padding: 24px;
}
.login-card {
  background: white;
  border-radius: 16px;
  padding: 32px 24px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}
.login-logo {
  text-align: center;
  margin-bottom: 28px;
}
.logo-img {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  margin: 0 auto 12px;
  display: block;
}
.login-logo h1 { font-size: 22px; font-weight: 700; color: #1e293b; }

.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: btn-spin 0.7s linear infinite;
  margin-right: 6px;
  vertical-align: -2px;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }

.eye-toggle {
  position: absolute;
  right: 12px;
  bottom: 10px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  display: flex;
  align-items: center;
  padding: 2px;
}
.eye-toggle:hover { color: #64748b; }
.error-box {
  background: #fee2e2;
  color: #991b1b;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.offline-note {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
</style>
