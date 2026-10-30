import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Capacitor } from '@capacitor/core'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// PWA: permite instalar la app en el telefono y abrirla sin conexion.
// Solo en produccion: en desarrollo un service worker sirviendo archivos
// guardados pelea con la recarga en caliente de Vite. En la app Android los
// archivos ya vienen dentro del APK: un service worker solo dejaria versiones viejas.
if ('serviceWorker' in navigator && import.meta.env.PROD && !Capacitor.isNativePlatform()) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Sin service worker la app funciona igual, solo pierde el modo sin conexion.
    })
  })
}
