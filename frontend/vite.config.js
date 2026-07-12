import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig(({ command }) => ({
  base: command === 'serve' ? '/' : '/assets/pranera_knit/knit_app/',

  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },

  server: {
    port: 3000,
    // Dev-server only — vite build never reads this (production always talks
    // to erp.pranera.in directly since it's served from that same origin).
    // Needed so `npm run dev` (localhost:3000) can reach the live backend;
    // without it every /api/* call 404s against Vite's own dev server and
    // returns HTML instead of JSON.
    proxy: command === 'serve' ? {
      '/api': {
        target: 'https://erp.pranera.in',
        changeOrigin: true,
        secure: false,
        ws: true,
        cookieDomainRewrite: 'localhost',
        headers: {
          'Origin': 'https://erp.pranera.in',
          'Referer': 'https://erp.pranera.in'
        },
        // Frappe marks its session cookie (sid) as Secure because
        // erp.pranera.in is HTTPS. Vite's dev server itself is plain HTTP
        // (localhost:3000), and browsers silently refuse to store *any*
        // Secure cookie over a non-HTTPS connection — no error, no warning,
        // it just never lands. cookieDomainRewrite only touches the
        // Domain= attribute, not Secure, so login would appear to succeed
        // (the login POST itself returns 200) while the session cookie
        // that request needed to persist for every call after it never
        // actually got stored. Strip Secure (dev only) so the cookie sticks.
        configure(proxy) {
          // node-http-proxy has a long-standing quirk: for POST/PUT requests
          // with no body (like our logout call — POST, no payload), it can
          // forward a stray `Expect` header through to the backend. nginx
          // (which fronts erp.pranera.in) responds to that with a flat
          // "417 Expectation Failed" instead of actually processing the
          // request — so frappe.auth.logout never runs server-side even
          // though the browser gets back what looks like a real HTTP
          // response. Stripping the header before it's forwarded is the
          // standard fix.
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.removeHeader('expect')
          })
          proxy.on('proxyRes', (proxyRes) => {
            const setCookie = proxyRes.headers['set-cookie']
            if (setCookie) {
              proxyRes.headers['set-cookie'] = setCookie.map(c =>
                c.replace(/;\s*Secure/gi, '').replace(/;\s*SameSite=None/gi, '; SameSite=Lax')
              )
            }
          })
        }
      },
      '/assets': {
        target: 'https://erp.pranera.in',
        changeOrigin: true,
        secure: false
      },
      '/files': {
        target: 'https://erp.pranera.in',
        changeOrigin: true,
        secure: false
      }
    } : undefined
  },

  build: {
    outDir: path.resolve(__dirname, '../pranera_knit/public/knit_app'),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
      output: {
        entryFileNames: 'index.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: (info) => {
          if (info.name?.endsWith('.css')) return 'index.css'
          return 'assets/[name]-[hash][extname]'
        }
      }
    }
  },

  plugins: [
    vue(),
    VitePWA({
      base: '/assets/pranera_knit/knit_app/',
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,woff2}'],
        // Serve the cached SPA shell for in-app navigations when offline,
        // so reloading /knit-app/home works with no network. Exclude /api and
        // /files so those still hit the network (and their own caches below).
        navigateFallback: '/assets/pranera_knit/knit_app/index.html',
        // Only the offline-critical pages (home, create-roll, create-qi, rolls,
        // stock-entry, work-order — see router/index.js "eager" section) should
        // fall back to the cached shell so operators can reload them with no
        // network. The report/dashboard pages are online-only by design and
        // must always hit the server: only the server-rendered /knit-app page
        // (www/knit-app.py) injects window.csrf_token, and the cached static
        // index.html never has it — serving these from cache silently breaks
        // every POST call (call()/ensureCSRF()).
        navigateFallbackDenylist: [
          /^\/api/, /^\/files/, /^\/app/,
          /^\/knit-app\/dashboard/,
          /^\/knit-app\/collar-cuff-dashboard/,
          /^\/knit-app\/roll-wise-pick-list/,
          /^\/knit-app\/roll-wise-pick-order-execution/,
          /^\/knit-app\/production-roll-summary/,
          /^\/knit-app\/production-report/,
          /^\/knit-app\/process-loss/,
          /^\/knit-app\/no-access/,
        ],
        runtimeCaching: [
          {
            // Cache read-only GET list/report data so it's available offline.
            urlPattern: ({ url, request }) =>
              request.method === 'GET' && url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'knit-api-get',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      manifest: {
        name: 'Pranera Knit App',
        short_name: 'KnitApp',
        theme_color: '#0f6e56',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/knit-app',
        scope: '/knit-app',
        icons: [
          { src: '/assets/pranera_knit/knit_app/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/assets/pranera_knit/knit_app/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/assets/pranera_knit/knit_app/icons/icon-192-maskable.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/assets/pranera_knit/knit_app/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
        ]
      }
    })
  ]
}))
