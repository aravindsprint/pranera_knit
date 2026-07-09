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
    proxy: {
      '/api': {
        target: 'https://erp.pranera.in',
        changeOrigin: true,
        secure: false,
        ws: true,
        cookieDomainRewrite: 'localhost',
        headers: {
          'Origin': 'https://erp.pranera.in',
          'Referer': 'https://erp.pranera.in'
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
    }
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
        navigateFallbackDenylist: [/^\/api/, /^\/files/, /^\/app/],
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
