<template>
  <div class="nt">
    <div class="nt__row">
      <span class="nt__icon">🔔</span>
      <div class="nt__text">
        <div class="nt__title">Notifications</div>
        <div class="nt__sub">{{ subtitle }}</div>
      </div>
      <button
        class="nt__switch" :class="{ 'nt__switch--on': on }" role="switch" :aria-checked="on"
        :disabled="busy" @click="toggle"
      >
        <span class="nt__knob"></span>
      </button>
    </div>
    <button v-if="on && !busy" class="nt__test" @click="test">Send test notification</button>
    <div v-if="message" class="nt__msg" :class="{ 'nt__msg--err': isError }">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// push.js (and Firebase with it) loads only when this is actually used.
const on = ref(false)
const busy = ref(false)
const message = ref('')
const isError = ref(false)

try {
  on.value = !!localStorage.getItem('knit_push_token') &&
    typeof Notification !== 'undefined' && Notification.permission === 'granted'
} catch { /* storage blocked */ }

const subtitle = computed(() =>
  busy.value ? 'Working…' : on.value ? 'On for this device' : 'Off — tap to get alerts on this phone'
)

async function toggle() {
  busy.value = true
  message.value = ''
  isError.value = false
  try {
    const push = await import('@/push')
    if (on.value) {
      await push.disablePush()
      on.value = false
      message.value = 'Notifications turned off for this device.'
    } else {
      await push.enablePush()
      on.value = true
      message.value = 'Notifications are on. Tap "Send test" to check.'
    }
  } catch (e) {
    isError.value = true
    message.value = e.message || String(e)
  } finally {
    busy.value = false
  }
}

async function test() {
  message.value = ''
  isError.value = false
  try {
    const push = await import('@/push')
    await push.sendTestPush()
    message.value = 'Test sent — it should arrive in a few seconds.'
  } catch (e) {
    isError.value = true
    message.value = e.message || String(e)
  }
}
</script>

<style scoped>
.nt { padding: 10px 12px; border-radius: 10px; background: #f8fafc; margin: 8px 0; }
.nt__row { display: flex; align-items: center; gap: 10px; }
.nt__icon { font-size: 18px; }
.nt__text { flex: 1; min-width: 0; }
.nt__title { font-size: 14px; font-weight: 600; color: #0f172a; }
.nt__sub { font-size: 12px; color: #64748b; }
.nt__switch {
  width: 44px; height: 26px; border-radius: 999px; border: none; background: #cbd5e1;
  position: relative; cursor: pointer; flex-shrink: 0; transition: background 0.2s; padding: 0;
}
.nt__switch--on { background: var(--app-primary, #0f6e56); }
.nt__switch:disabled { opacity: 0.6; cursor: wait; }
.nt__knob {
  position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%;
  background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.2); transition: transform 0.2s;
}
.nt__switch--on .nt__knob { transform: translateX(18px); }
.nt__test {
  margin-top: 8px; width: 100%; border: 1.5px solid var(--app-primary, #0f6e56); background: #fff;
  color: var(--app-primary, #0f6e56); border-radius: 8px; padding: 7px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.nt__msg { margin-top: 8px; font-size: 12px; color: #166534; line-height: 1.4; }
.nt__msg--err { color: #991b1b; }
</style>
