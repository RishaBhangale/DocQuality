import { defineConfig } from 'vite'
import path from 'path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      // Serve monitor.html at the root URL in dev mode
      name: 'monitor-root-redirect',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/' || req.url === '') {
            req.url = '/monitor.html'
          }
          next()
        })
      },
    },
  ],
  resolve: {
    alias: {
      '@monitor': path.resolve(__dirname, './src/monitor'),
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  root: '.',
  build: {
    outDir: 'dist-monitor',
    rollupOptions: {
      input: 'monitor.html',
    },
  },
})

