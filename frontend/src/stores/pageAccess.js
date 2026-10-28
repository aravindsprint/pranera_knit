// Which Knit App pages the logged-in user may open (pranera_knit/api/page_access.py).
// The server returns the pages that are DENIED, so any page not configured
// in Desk stays open. The last answer is cached per user so menus and the
// router keep working offline; with no cache and no network nothing is hidden.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { call } from '@/api/frappe'
import { PAGES } from '@/pages'

const CACHE_KEY = 'KNIT_PAGE_ACCESS'

function currentUser() {
  return window.__FRAPPE_SESSION__?.user || ''
}

function readCache() {
  try {
    const c = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null')
    return c && c.user === currentUser() ? c.denied : null
  } catch { return null }
}

export const usePageAccessStore = defineStore('pageAccess', () => {
  const denied = ref(readCache() || [])
  const loadedFor = ref('')
  let inflight = null

  const visiblePages = computed(() => PAGES.filter(p => !denied.value.includes(p.key)))

  function can(key) {
    return !key || !denied.value.includes(key)
  }

  // Resolves once access is known for the current user (server, else cache).
  function ensureLoaded() {
    const user = currentUser()
    if (!user || user === 'Guest') return Promise.resolve()
    if (loadedFor.value === user) return Promise.resolve()
    if (!inflight) {
      inflight = call('pranera_knit.api.page_access.get_page_access')
        .then((r) => {
          denied.value = r.message?.denied || []
          try { localStorage.setItem(CACHE_KEY, JSON.stringify({ user, denied: denied.value })) } catch { /* ignore */ }
        })
        .catch(() => { denied.value = readCache() || [] })
        .finally(() => { loadedFor.value = user; inflight = null })
    }
    return inflight
  }

  function reset() {
    denied.value = []
    loadedFor.value = ''
    try { localStorage.removeItem(CACHE_KEY) } catch { /* ignore */ }
  }

  return { denied, visiblePages, can, ensureLoaded, reset }
})
