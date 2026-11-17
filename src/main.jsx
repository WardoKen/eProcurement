import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Legacy styles, both wrapped in `@layer legacy`.
import './index.css'
import './styles/design-system.css'
// Design system (unlayered, so it wins over legacy). See DESIGN.md.
import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/shell.css'
import './styles/screens.css'
import './styles/screens-admin.css'
import './styles/screens-supplier.css'
import './styles/screens-enduser.css'
import './styles/screens-public.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
