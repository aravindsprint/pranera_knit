// src/stores/auth.js
// No login form needed — user is already logged in via ERPNext.
// This store reads the Frappe session and fetches employee details.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEmployeeDetails } from '@/api/frappe'

export const useAuthStore = defineStore('auth', () => {
  // Read from Frappe session injected in www/knit-app.html
  const frappeSession = window.__FRAPPE_SESSION__ || {}

  const username    = ref(localStorage.getItem('KNIT_USERNAME') || '')
  const designation = ref(localStorage.getItem('KNIT_DESIGNATION') || '')
  const employeeData = ref(JSON.parse(localStorage.getItem('KNIT_EMPLOYEE') || 'null'))
  const loading     = ref(false)
  const error       = ref('')

  // Frappe session user (email)
  const frappeUser  = frappeSession.user || ''

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
      const employees = await getEmployeeDetails(frappeUser)

      if (!employees.length) {
        error.value = 'No employee record found for your account'
        return false
      }

      const emp = employees[0]
      employeeData.value = emp
      username.value     = emp.employee_name || frappeUser
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

  return {
    frappeUser, username, designation, employeeData, employeeId,
    loading, error,
    isKnittingOperator, isSupervisor, canAccessKnittingApp,
    loadEmployeeDetails, clearCache
  }
})
