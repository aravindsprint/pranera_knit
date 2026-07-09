// src/stores/roll.js
// Mirrors create-roll.page.ts — roll session, breakdown tracking, submission
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { db } from '@/db'
import {
  saveRollOffline, saveRollSession,
  getRollSession, clearRollSession, enqueue, isOnline
} from '@/composables/useSync'
import { getMTMNo, submitRollPackingList } from '@/api/frappe'
import moment from 'moment'

export const useRollStore = defineStore('roll', () => {
  // ── Product / Job Card context ───────────────────────────────────────────
  const productData = ref(null)   // passed from home page via shared state

  // ── Form fields (mirrors CreateRollPage class fields) ────────────────────
  const rollWeight = ref(null)
  const totalQty = ref(null)
  const mistakeQty = ref(null)
  const shift = ref('')
  const batchNo = ref('')
  const currentRollNo = ref('')

  // ── Session state (persisted in IndexedDB via saveRollSession) ───────────
  const session = ref(null)
  const isRollActive = ref(false)
  const breakdowns = ref([])
  const totalBreakdownSeconds = ref(0)
  const showEndRollForm = ref(false)
  const showPrintButtons = ref(false)
  const lastCompletedRollData = ref(null)

  // ── Timers ────────────────────────────────────────────────────────────────
  let rollTimer = null
  const elapsedSeconds = ref(0)

  function startTimer() {
    rollTimer = setInterval(() => { elapsedSeconds.value++ }, 1000)
  }
  function stopTimer() {
    clearInterval(rollTimer)
    rollTimer = null
  }

  const elapsedFormatted = computed(() => {
    const h = Math.floor(elapsedSeconds.value / 3600)
    const m = Math.floor((elapsedSeconds.value % 3600) / 60)
    const s = elapsedSeconds.value % 60
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  })

  // ── Load / restore session from IndexedDB (survives tab close) ───────────
  async function restoreSession(jobCardId) {
    const saved = await getRollSession(jobCardId)
    if (saved && saved.isActive) {
      session.value = saved
      isRollActive.value = true
      currentRollNo.value = saved.rollNo
      shift.value = saved.shift
      batchNo.value = saved.batchNo || ''
      breakdowns.value = saved.breakdowns || []
      totalBreakdownSeconds.value = saved.totalBreakdownTime || 0
      // Reconstruct elapsed time from start
      const started = moment(saved.actualStartTimestamp)
      elapsedSeconds.value = moment().diff(started, 'seconds') - totalBreakdownSeconds.value
      startTimer()
    }
  }

  // ── Start Roll ────────────────────────────────────────────────────────────
  async function startRoll(jobCardId, rollNo, shiftVal, batchVal) {
    const now = new Date().toISOString()
    isRollActive.value = true
    currentRollNo.value = rollNo
    shift.value = shiftVal
    batchNo.value = batchVal
    elapsedSeconds.value = 0

    const sessionData = {
      rollNo,
      jobCardId,
      startTime: now,
      actualStartTimestamp: now,
      shift: shiftVal,
      batchNo: batchVal,
      isActive: true,
      runningTime: 0,
      totalBreakdownTime: 0,
      lastEndRollClick: null,
      breakdowns: [],
      showEndRollForm: false,
      showPrintButtons: false,
      lastCompletedRollData: null
    }

    await saveRollSession(jobCardId, sessionData)
    session.value = sessionData

    // Queue createKnitCCRollNoInDB equivalent (records start time in ERP)
    await enqueue('createKnitCCRollNoInDB', 'GET', { jobCardId, rollNo, startTime: now })

    startTimer()
  }

  // ── Record Breakdown ──────────────────────────────────────────────────────
  async function startBreakdown(jobCardId) {
    if (!session.value) return
    const bd = { startTime: new Date().toISOString(), endTime: null, duration: 0 }
    breakdowns.value.push(bd)
    stopTimer()
    await saveRollSession(jobCardId, { ...session.value, breakdowns: breakdowns.value })
    await enqueue('recordBreakdown', 'POST', { jobCardId, breakdownStart: bd.startTime })
  }

  async function endBreakdown(jobCardId) {
    if (!breakdowns.value.length) return
    const last = breakdowns.value[breakdowns.value.length - 1]
    last.endTime = new Date().toISOString()
    last.duration = moment(last.endTime).diff(moment(last.startTime), 'seconds')
    totalBreakdownSeconds.value += last.duration

    await saveRollSession(jobCardId, {
      ...session.value,
      breakdowns: breakdowns.value,
      totalBreakdownTime: totalBreakdownSeconds.value
    })
    startTimer()
  }

  // ── End Roll / Submit ─────────────────────────────────────────────────────
  async function submitRoll(jobCardId) {
    if (!productData.value) throw new Error('No product data loaded')
    stopTimer()

    const endTime = new Date().toISOString()
    const netSeconds = elapsedSeconds.value
    const efficiency = netSeconds > 0
      ? Math.min(100, ((netSeconds - totalBreakdownSeconds.value) / netSeconds) * 100).toFixed(2)
      : '0.00'

    const rollData = {
      job_card: jobCardId,
      item_code: productData.value.production_item,
      item_name: productData.value.item_name,
      commercial_name: productData.value.commercial_name,
      color: productData.value.color,
      width: productData.value.width,
      work_order: productData.value.work_order,
      roll_no: currentRollNo.value,
      roll_weight: rollWeight.value,
      total_qty: totalQty.value,
      mistake_qty: mistakeQty.value,
      shift: shift.value,
      batch: batchNo.value,
      start_time: session.value?.actualStartTimestamp,
      end_time: endTime,
      total_time_seconds: netSeconds,
      breakdown_time_seconds: totalBreakdownSeconds.value,
      net_production_time_seconds: netSeconds - totalBreakdownSeconds.value,
      efficiency_percentage: parseFloat(efficiency),
      docstatus: 0,
      knit_operator_name: localStorage.getItem('USERNAME'),
      date: moment().format('YYYY-MM-DD')
    }

    // Save locally first (works offline), queue ERP sync
    const localId = await saveRollOffline(rollData)

    lastCompletedRollData.value = {
      roll_no: currentRollNo.value,
      roll_weight: rollWeight.value,
      total_qty: totalQty.value,
      mistake_qty: mistakeQty.value,
      batch_no: batchNo.value
    }
    showPrintButtons.value = true
    showEndRollForm.value = false
    isRollActive.value = false

    // Queue packing list submission
    await enqueue('submitRollPackingList', 'GET', {
      jobcard: jobCardId,
      work_order: productData.value.work_order
    })

    await clearRollSession(jobCardId)

    // Reset form
    rollWeight.value = null
    totalQty.value = null
    mistakeQty.value = null

    return { localId, rollData }
  }

  function setProductData(data) {
    productData.value = data
    // Mirror SharedDataService + sessionStorage backup
    if (data) sessionStorage.setItem('currentProductData', JSON.stringify(data))
  }

  function loadProductDataFromSession() {
    if (!productData.value) {
      const stored = sessionStorage.getItem('currentProductData')
      if (stored) productData.value = JSON.parse(stored)
    }
  }

  function clearProductData() {
    productData.value = null
    sessionStorage.removeItem('currentProductData')
  }

  return {
    productData, rollWeight, totalQty, mistakeQty, shift, batchNo,
    currentRollNo, isRollActive, breakdowns, totalBreakdownSeconds,
    showEndRollForm, showPrintButtons, lastCompletedRollData,
    elapsedSeconds, elapsedFormatted, session,
    restoreSession, startRoll, startBreakdown, endBreakdown, submitRoll,
    setProductData, loadProductDataFromSession, clearProductData
  }
})
