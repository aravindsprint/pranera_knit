import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

// NOTE: a previous version of this file unconditionally unregistered every
// service worker on load. That raced against registerSW.js (injected by
// vite-plugin-pwa, a classic script that runs before this deferred module
// script) which had just registered a fresh one — so depending on timing,
// the app would sometimes keep running on a stale precached build
// (old header, missing menu items, missing buttons) with no visible error.
// Removed: let vite-plugin-pwa's own autoUpdate flow own the SW lifecycle.

function getCookie(name) {
  return document.cookie.split('; ').find(r => r.startsWith(name + '='))?.split('=')[1] || ''
}

window.__FRAPPE_SESSION__ = {
  user: decodeURIComponent(getCookie('user_id') || 'Guest'),
  csrf_token: getCookie('csrftoken'),
  base_url: ''
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
