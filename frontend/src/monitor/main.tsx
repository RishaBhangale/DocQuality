import React from 'react'
import ReactDOM from 'react-dom/client'
import { MonitorApp } from './MonitorApp'
import './monitor.css'

ReactDOM.createRoot(document.getElementById('monitor-root')!).render(
  <React.StrictMode>
    <MonitorApp />
  </React.StrictMode>
)
