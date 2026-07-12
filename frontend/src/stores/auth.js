// src/stores/auth.js
// No login form needed — user is already logged in via ERPNext.
// This store reads the Frappe session and fetches employee details.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEmployeeDetails, ensureCSRF, resetCSRF, initCSRF } from '@/api/frappe'

export const useAuthStore = defineStore('auth', () => {
  // Read from Frappe session injected in www/knit-app.html
  const frappeSession = window.__FRAPPE_SESSION__ || {}

  const username    = ref(localStorage.getItem('KNIT_USERNAME') || '')
  const designation = ref(localStorage.getItem('KNIT_DESIGNATION') || '')
  const employeeData = ref(JSON.parse(localStorage.getItem('KNIT_EMPLOYEE') || 'null'))
  const loading     = ref(false)
  const error       = ref('')

  // Frappe session user (email) — kept live via window.__FRAPPE_SESSION__ so
  // it reflects the *current* session even after login()/logout() mutate it.
  const frappeUser  = computed(() => window.__FRAPPE_SESSION__?.user || frappeSession.user || '')

  const isLoggedIn = computed(() => {
    const u = window.__FRAPPE_SESSION__?.user
    return !!u && u !== 'Guest'
  })

  const employeeId = computed(() => employeeData.value?.name || '')

  const isKnittingOperator = computed(() =>
    designation.value === 'Knitting Operator' ||
    designation.value === 'Senior Knitting Operator'
  )

  const isSupervisor = computed(() =>
    designation.value === 'Knitting Supervisor' ||
    designation.value === 'System Manager' ||
    designation.value === 'Sr. Software Analyst' ||
    employeeData.value?.custom_is_knitting_supervisor === 1
  )

  const canAccessKnittingApp = computed(() =>
    employeeData.value?.custom_can_access_knitting_app === 1
  )

  // Called once on app boot — loads employee record from ERPNext
  async function loadEmployeeDetails() {
    if (employeeData.value) return true   // already loaded

    loading.value = true
    error.value = ''

    try {
      const employees = await getEmployeeDetails(frappeUser.value)

      if (!employees.length) {
        error.value = 'No employee record found for your account'
        return false
      }

      const emp = employees[0]
      employeeData.value = emp
      username.value     = emp.employee_name || frappeUser.value
      designation.value  = emp.designation   || 'Unknown'

      localStorage.setItem('KNIT_USERNAME',   username.value)
      localStorage.setItem('KNIT_DESIGNATION', designation.value)
      localStorage.setItem('KNIT_EMPLOYEE',   JSON.stringify(emp))

      if (emp.custom_can_access_knitting_app !== 1) {
        error.value = 'You do not have access to the Knitting App'
        return false
      }

      return true
    } catch (err) {
      error.value = err.message || 'Failed to load employee details'
      return false
    } finally {
      loading.value = false
    }
  }

  function clearCache() {
    localStorage.removeItem('KNIT_USERNAME')
    localStorage.removeItem('KNIT_DESIGNATION')
    localStorage.removeItem('KNIT_EMPLOYEE')
    employeeData.value = null
    username.value     = ''
    designation.value  = ''
  }

  // Explicit email/password login against Frappe's own login endpoint.
  // On success this establishes a real Frappe session (sid cookie), so we
  // have to throw away the old (Guest-scoped) CSRF token and fetch a fresh
  // one before any authenticated call — otherwise the very next request
  // fails with a silent CSRFTokenError.
  async function login(email, password) {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/method/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ usr: email, pwd: password }).toString(),
        credentials: 'include'
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok || data.message !== 'Logged In') {
        let msg = 'Incorrect email or password'
        try {
          const msgs = JSON.parse(data._server_messages || '[]')
          if (msgs.length) msg = JSON.parse(msgs[msgs.length - 1]).message || msg
        } catch { /* keep default */ }
        throw new Error(msg)
      }

      resetCSRF()
      await initCSRF()               // re-reads user_id cookie + fetches a fresh CSRF token

      clearCache()                   // drop any stale employee record from a previous user
      const ok = await loadEmployeeDetails()
      if (!ok) throw new Error(error.value || 'Login succeeded but access check failed')
      return true
    } catch (err) {
      error.value = err.message || 'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  // Explicit logout: invalidates the Frappe session server-side, then clears
  // all local state. Always call this (not a raw fetch) so the CSRF token is
  // read correctly — window.__FRAPPE_SESSION__.csrf_token was previously
  // always empty here, which made the logout POST fail silently.
  async function logout() {
    try {
      const token = await ensureCSRF()
      await fetch('/api/method/frappe.auth.logout', {
        method: 'POST',
        headers: { 'X-Frappe-CSRF-Token': token },
        credentials: 'include'
      })
    } catch (_) {
      // Network failure during logout — still clear local state below so the
      // app doesn't appear "logged in" on this device even if the server
      // call didn't land.
    }
    clearCache()
    resetCSRF()
    if (window.__FRAPPE_SESSION__) window.__FRAPPE_SESSION__.user = 'Guest'
  }

  return {
    frappeUser, username, designation, employeeData, employeeId,
    loading, error, isLoggedIn,
    isKnittingOperator, isSupervisor, canAccessKnittingApp,
    loadEmployeeDetails, clearCache, login, logout
  }
})
