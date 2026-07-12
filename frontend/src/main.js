import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()))
}

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
