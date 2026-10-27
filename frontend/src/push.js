// Push notifications for the Knit App, via Frappe's Push Notification Relay.
//
// Flow (mirrors Frappe HR's frappe-push-notification.js):
//   1. Ask the server for the relay URL + project name (api/push.get_push_config).
//   2. Fetch that project's Firebase web config + VAPID key from the relay.
//   3. Register our own push service worker (public/push/knit-push-sw.js) in
//      its own scope, separate from the offline app-shell service worker.
//   4. Get an FCM token for that registration and hand it to Frappe
//      (frappe.push_notification.subscribe), which registers it with the
//      relay for the logged-in user.
// The server then sends with PushNotification(project).send_notification_to_user.
//
// Firebase is loaded lazily, only when someone turns notifications on (or the
// app checks a device that already did), so it stays out of the main bundle.
import { call } from '@/api/frappe'

const SW_URL = '/assets/pranera_knit/knit_app/push/knit-push-sw.js'
const SW_SCOPE = '/assets/pranera_knit/knit_app/push/'
const TOKEN_KEY = 'knit_push_token'

let configPromise = null
async function serverConfig() {
  if (!configPromise) {
    configPromise = call('pranera_knit.api.push.get_push_config')
      .then(r => r.message)
      .catch((e) => { configPromise = null; throw e })
  }
  return configPromise
}

async function relayConfig(cfg) {
  const url = `${cfg.relay_url}/api/method/notification_relay.api.get_config?project_name=${encodeURIComponent(cfg.project)}`
  let res
  try {
    res = await fetch(url)
  } catch {
    throw new Error("Couldn't reach the notification service. Check the internet connection and try again.")
  }
  const json = await res.json().catch(() => ({}))
  if (!res.ok || !json.config || !json.vapid_public_key) {
    throw new Error(`The notification relay has no setup for "${cfg.project}". Ask the admin to check knit_push_project in site config.`)
  }
  return json
}

export function isSupportedBrowser() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export function isIosNeedingInstall() {
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent)
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone
  return ios && !standalone
}

export function isEnabledOnThisDevice() {
  return !!localStorage.getItem(TOKEN_KEY) &&
    typeof Notification !== 'undefined' && Notification.permission === 'granted'
}

async function firebaseMessaging(webConfig) {
  const [{ initializeApp, getApps }, messagingMod] = await Promise.all([
    import('firebase/app'),
    import('firebase/messaging'),
  ])
  if (!(await messagingMod.isSupported())) {
    throw new Error('This browser does not support push notifications.')
  }
  const app = getApps().find(a => a.name === 'knit-push') || initializeApp(webConfig, 'knit-push')
  return { messaging: messagingMod.getMessaging(app), mod: messagingMod }
}

async function subscribeOnServer(token, project) {
  const q = new URLSearchParams({ fcm_token: token, project_name: project })
  const res = await fetch(`/api/method/frappe.push_notification.subscribe?${q}`, { credentials: 'include' })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || json.message?.success === false) {
    throw new Error(json.message?.message || 'The server could not register this device for notifications.')
  }
}

async function unsubscribeOnServer(token, project) {
  const q = new URLSearchParams({ fcm_token: token, project_name: project })
  await fetch(`/api/method/frappe.push_notification.unsubscribe?${q}`, { credentials: 'include' }).catch(() => {})
}

// navigator.serviceWorker.ready tracks the worker controlling *this page*
// (the app shell's), never ours — wait on our own registration instead.
function waitUntilActive(registration, timeoutMs = 15000) {
  if (registration.active) return Promise.resolve(registration)
  const worker = registration.installing || registration.waiting
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('The notification service worker did not start. Reload and try again.')), timeoutMs)
    worker?.addEventListener('statechange', () => {
      if (worker.state === 'activated') { clearTimeout(timer); resolve(registration) }
    })
  })
}

// Turn notifications on for this device. Must be called from a tap (iOS).
export async function enablePush() {
  if (!isSupportedBrowser()) throw new Error('This browser does not support push notifications.')
  if (isIosNeedingInstall()) {
    throw new Error('On iPhone, first add the Knit App to your Home Screen (Share → Add to Home Screen), then open it from there.')
  }
  const cfg = await serverConfig()
  if (!cfg.enabled) throw new Error('Push notifications are not enabled on the server yet.')

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error('Notifications are blocked. Allow them for this site in your browser settings, then try again.')
  }

  const relay = await relayConfig(cfg)
  const registration = await navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE })
  await waitUntilActive(registration)
  const { messaging, mod } = await firebaseMessaging(relay.config)
  let token
  try {
    token = await mod.getToken(messaging, {
      vapidKey: relay.vapid_public_key,
      serviceWorkerRegistration: registration,
    })
  } catch (e) {
    if (String(e.code || '').includes('permission')) {
      throw new Error('Notifications are blocked. Allow them for this site in your browser settings, then try again.')
    }
    throw new Error(`Could not register this device for notifications (${e.code || e.message}).`)
  }
  if (!token) throw new Error('Could not get a notification token for this device.')

  const old = localStorage.getItem(TOKEN_KEY)
  if (old && old !== token) await unsubscribeOnServer(old, cfg.project)
  await subscribeOnServer(token, cfg.project)
  localStorage.setItem(TOKEN_KEY, token)
  return true
}

// Turn notifications off for this device.
export async function disablePush() {
  const token = localStorage.getItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_KEY)
  if (!token) return
  try {
    const cfg = await serverConfig()
    await unsubscribeOnServer(token, cfg.project)
    const relay = await relayConfig(cfg)
    const { messaging, mod } = await firebaseMessaging(relay.config)
    await mod.deleteToken(messaging).catch(() => {})
  } catch (e) {
    console.warn('disablePush:', e)
  }
  const reg = await navigator.serviceWorker.getRegistration(SW_SCOPE)
  await reg?.unregister()
}

export async function sendTestPush() {
  await call('pranera_knit.api.push.send_test_notification')
}
