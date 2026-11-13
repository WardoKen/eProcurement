import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
// Loaded last so its tokens and accessibility rules win the cascade.
import './styles/design-system.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
