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
    port: 3000
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
        icons: []
      }
    })
  ]
}))
