// src/stores/auth.js
// No login form needed — user is already logged in via ERPNext.
// This store reads the Frappe session and fetches employee details.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEmployeeDetails, ensureCSRF, resetCSRF } from '@/api/frappe'

export const useAuthStore = defineStore('auth', () => {
  // Read from Frappe session injected in www/knit-app.html
  const frappeSession = window.__FRAPPE_SESSION__ || {}

  const username    = ref(localStorage.getItem('KNIT_USERNAME') || '')
  const designation = ref(localStorage.getItem('KNIT_DESIGNATION') || '')
  const employeeData = ref(JSON.parse(localStorage.getItem('KNIT_EMPLOYEE') || 'null'))
  const loading     = ref(false)
  const error       = ref('')

  // Frappe session user (email). window.__FRAPPE_SESSION__ is a plain global
  // object, not a Vue-reactive source — a computed() reading it would only
  // ever re-run if Vue could detect the mutation, which it can't, so it'd
  // freeze on whatever value it happened to see on its first access. Use a
  // plain ref instead and update it explicitly at the points the session
  // actually changes (refreshSession(), login(), logout()).
  const frappeUser = ref(window.__FRAPPE_SESSION__?.user || frappeSession.user || '')
  const isLoggedIn = ref(!!frappeUser.value && frappeUser.value !== 'Guest')

  // Re-sync frappeUser/isLoggedIn from window.__FRAPPE_SESSION__. Call this
  // any time something else (initCSRF, login, logout) has just changed the
  // session, so the store's reactive state doesn't drift from reality.
  function refreshSession() {
    const u = window.__FRAPPE_SESSION__?.user || ''
    frappeUser.value = u
    isLoggedIn.value = !!u && u !== 'Guest'
  }

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
  // Deliberately does NOT try to re-init CSRF / load the employee record in
  // this same page lifecycle afterwards — that immediate-reuse path proved
  // unreliable (fails right after login, but the exact same calls succeed
  // on the very next hard page reload). The caller is expected to do a full
  // navigation on success, which re-runs main.js from scratch against the
  // now-valid session cookie — the same sequence a manual browser refresh
  // does, which is why refreshing "fixes" it.
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
    frappeUser.value = 'Guest'
    isLoggedIn.value = false
  }

  return {
    frappeUser, username, designation, employeeData, employeeId,
    loading, error, isLoggedIn,
    isKnittingOperator, isSupervisor, canAccessKnittingApp,
    loadEmployeeDetails, clearCache, login, logout, refreshSession
  }
})
