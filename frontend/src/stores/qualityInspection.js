// src/stores/qualityInspection.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { db } from '@/db'
import { saveQIOffline, isOnline } from '@/composables/useSync'
import { getQIParameters, getDoc } from '@/api/frappe'

export const useQIStore = defineStore('qualityInspection', () => {
  const parameters = ref([])
  const loading = ref(false)
  const productData = ref(null)

  async function loadParameters(itemCode) {
    loading.value = true
    try {
      // Try local cache first
      const local = await db.quality_inspection_parameters
        .where('item_code').equals(itemCode).toArray()
      if (local.length) parameters.value = local

      if (isOnline.value) {
        const res = await getQIParameters(itemCode)
        const fresh = Array.isArray(res) ? res : (res?.data?.data || res?.data || res?.message || [])
        if (fresh.length) {
          await db.quality_inspection_parameters.bulkPut(
            fresh.map(p => ({ ...p, id: p.name }))
          )
          parameters.value = fresh
        }
      }
    } catch (err) {
      console.error('loadParameters error:', err)
    } finally {
      loading.value = false
    }
  }

  async function submitQI(qiData) {
    // Save offline first, queued for ERP sync
    const localId = await saveQIOffline(qiData)
    return localId
  }

  function setProductData(data) {
    productData.value = data
    if (data) sessionStorage.setItem('currentProductData', JSON.stringify(data))
  }

  function loadProductDataFromSession() {
    if (!productData.value) {
      const stored = sessionStorage.getItem('currentProductData')
      if (stored) productData.value = JSON.parse(stored)
    }
  }

  return { parameters, loading, productData, loadParameters, submitQI, setProductData, loadProductDataFromSession }
})
