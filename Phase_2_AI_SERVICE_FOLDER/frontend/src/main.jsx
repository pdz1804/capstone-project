import React from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import App from './App.jsx'
import './index.css'

const storageUserId = import.meta.env.VITE_USER_ID || 'default'
axios.defaults.headers.common['X-User-Id'] = storageUserId

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
