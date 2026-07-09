// src/stores/home.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { db } from '@/db'
import { fetchJobCards, fetchJobCardAssignments } from '@/api/frappe'
import { isOnline } from '@/composables/useSync'

export const useHomeStore = defineStore('home', () => {
  const jobCards = ref([])
  const loading = ref(false)
  const error = ref('')

  // Status badge colour — mirrors getStatusColor() in home.page.ts
  const STATUS_COLOURS = {
    'Completed': 'success',
    'Work In Progress': 'warning',
    'Pending': 'secondary',
    'Cancelled': 'danger',
    'Open': 'info',
    'Draft': 'secondary'
  }

  function statusColour(status) {
    return STATUS_COLOURS[status] || 'secondary'
  }

  // Load from local IndexedDB first, then refresh from ERP if online
  async function loadJobCards(username, designation, employeeId) {
    loading.value = true
    error.value = ''

    try {
      // Serve local cache immediately so the UI is never blank offline
      const local = await db.job_cards.toArray()
      if (local.length) {
        jobCards.value = local
      }

      if (isOnline.value) {
        const res = await fetchJobCards(username, designation, employeeId)
        const fresh = Array.isArray(res) ? res : (res?.data?.data || res?.data || [])

        // Only replace the cache when the server actually returned rows.
        // A blank/errored response must never wipe a good offline cache.
        if (Array.isArray(fresh) && fresh.length) {
          await db.job_cards.clear()
          await db.job_cards.bulkPut(fresh.map(jc => ({ ...jc, id: jc.name })))
          jobCards.value = fresh

          // Cache every card's assignment so "Currently assigned" works
          // offline for ALL cards — whether or not the operator opens them.
          // Awaited with the fresh list so it never races the job_cards write.
          await refreshAssignments(fresh)
        } else if (!local.length) {
          // Genuinely no job cards for this user
          jobCards.value = []
        }
        // else: keep showing cache, nothing fresh to apply
      } else if (!local.length) {
        error.value = 'Offline — no cached job cards available'
      }
    } catch (err) {
      console.error('loadJobCards error:', err)
      // Network failed — fall back to whatever cache we already loaded.
      if (!jobCards.value.length) {
        const local = await db.job_cards.toArray().catch(() => [])
        if (local.length) {
          jobCards.value = local
        } else {
          error.value = 'Failed to load job cards. Please try again.'
        }
      }
    } finally {
      loading.value = false
    }
  }

  // Standalone assignment cache — callable independent of loadJobCards'
  // online-gate. Fetches assignments for whatever job cards are cached and
  // writes them to rollSessions. Always attempts the network directly (the
  // caller decides when to call it), so a stale isOnline ref can't block it.
  async function refreshAssignments(cardList = null) {
    try {
      let names
      if (Array.isArray(cardList) && cardList.length) {
        names = cardList.map(c => c.name || c.id).filter(Boolean)
      } else {
        const cards = await db.job_cards.toArray()
        names = cards.map(c => c.name || c.id).filter(Boolean)
      }
      if (!names.length) return { cached: 0 }
      const assignMap = await fetchJobCardAssignments(names)
      let count = 0
      for (const [jobCardId, a] of Object.entries(assignMap)) {
        const existing = await db.rollSessions.get(jobCardId).catch(() => null)
        await db.rollSessions.put({
          ...(existing || {}),
          jobCardId,
          _hasAssignment: true,
          _assignedId: a.employee || '',
          _assignedName: a.custom_employee_name || a.employee || '',
          _updatedAt: new Date().toISOString()
        })
        count++
      }
      console.log(`Cached ${count} job card assignments`)
      return { cached: count }
    } catch (e) {
      console.warn('refreshAssignments failed:', e.message)
      return { cached: 0, error: e.message }
    }
  }

  return { jobCards, loading, error, loadJobCards, statusColour, refreshAssignments }
})
