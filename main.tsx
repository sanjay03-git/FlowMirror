import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import './camera-grid.css'
import './response.css'
import './scenario.css'
import { App } from './App'

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
