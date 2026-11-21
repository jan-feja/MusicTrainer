import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './app/App'
import { DownloadsProvider } from './features/downloads/DownloadsProvider'
import './styles/global.css'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('index.html has no #root element')
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <DownloadsProvider>
        <App />
      </DownloadsProvider>
    </BrowserRouter>
  </StrictMode>,
)
