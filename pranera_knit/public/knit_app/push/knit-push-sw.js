/*
 * Knit App push service worker.
 *
 * Registered by src/push.js with its own scope
 * (/assets/pranera_knit/knit_app/push/) so it never touches the offline
 * service worker that vite-plugin-pwa generates for the app shell. A push
 * subscription belongs to the registration that created it, so pushes for
 * this app arrive here regardless of which page is open.
 *
 * Messages come from Frappe's Push Notification Relay via Firebase Cloud
 * Messaging. Frappe puts title / body / click_action / notification_icon
 * in the `data` block; a `notification` block is handled too, just in case.
 */
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { data: { title: 'Knit App', body: event.data ? event.data.text() : '' } }
  }
  const data = payload.data || {}
  const note = payload.notification || {}
  const title = data.title || note.title || 'Knit App'
  const options = {
    body: data.body || note.body || '',
    icon: data.notification_icon || note.icon || '/assets/pranera_knit/knit_app/icons/icon-192.png',
    badge: '/assets/pranera_knit/knit_app/icons/icon-192.png',
    tag: data.tag || undefined,
    renotify: !!data.tag,
    data: { url: data.click_action || note.click_action || '/knit-app/home' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url || '/knit-app/home', self.location.origin)
  // Knit App pages are controlled by the app's main service worker, not this
  // one, so client.navigate() isn't available here — open the target page
  // (an installed PWA opens it in the app window).
  event.waitUntil(self.clients.openWindow(target.href))
})
