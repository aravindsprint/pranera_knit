<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <div class="logo-circle">PK</div>
        <h1>Pranera Knit</h1>
        <p>Production Floor App</p>
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
          <button type="button" class="eye-toggle" @click="showPassword = !showPassword">
            <i :class="showPassword ? 'pi pi-eye-slash' : 'pi pi-eye'"></i>
          </button>
        </div>

        <div v-if="errorMsg" class="error-box">
          <i class="pi pi-exclamation-triangle"></i> {{ errorMsg }}
        </div>

        <button type="submit" class="btn btn-primary btn-full" :disabled="loading">
          <i v-if="loading" class="pi pi-spin pi-spinner"></i>
          <span>{{ loading ? loadingMsg : 'Login' }}</span>
        </button>
      </form>

      <div class="offline-note" v-if="!isOnline">
        <i class="pi pi-wifi"></i> Offline — login requires network
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isOnline } from '@/composables/useSync'

const router = useRouter()
const auth = useAuthStore()

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
    loadingMsg.value = 'Loading employee details...'
    await auth.login(email.value, password.value)
    router.replace('/home')
  } catch (err) {
    errorMsg.value = err.message || 'Login failed'
  } finally {
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
.logo-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #0f6e56;
  color: white;
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
}
.login-logo h1 { font-size: 22px; font-weight: 700; color: #1e293b; }
.login-logo p  { font-size: 13px; color: #64748b; margin-top: 2px; }

.eye-toggle {
  position: absolute;
  right: 12px;
  bottom: 10px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  font-size: 18px;
}
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
