import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import BankApp from './bank/BankApp'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{window.location.pathname.startsWith('/bank') ? <BankApp /> : <App />}</React.StrictMode>)
