import { useEffect, useState } from 'react'
import TransactionCard from './TransactionCard'
import OwnershipExplorer from './OwnershipExplorer'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const TABS = [
  { action: 'PASS', label: 'Passed', emptyText: 'No passed transactions.' },
  { action: 'MANUAL_REVIEW', label: 'For Review', emptyText: 'No transactions awaiting review.' },
  { action: 'BLOCK', label: 'Blocked', emptyText: 'No blocked transactions.' },
]

function PaymentsView() {
  const [transactions, setTransactions] = useState([])
  const [activeTab, setActiveTab] = useState('MANUAL_REVIEW')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/transactions`)
      .then((res) => {
        if (!res.ok) throw new Error(`API returned ${res.status}`)
        return res.json()
      })
      .then((data) => setTransactions(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const counts = TABS.reduce((acc, tab) => {
    acc[tab.action] = transactions.filter((t) => t.recommended_action === tab.action).length
    return acc
  }, {})

  const visible = transactions.filter((t) => t.recommended_action === activeTab)

  return (
    <>
      <nav className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.action}
            className={`tab ${activeTab === tab.action ? 'active' : ''} tab-${tab.action}`}
            onClick={() => setActiveTab(tab.action)}
          >
            {tab.label}
            <span className="tab-count">{counts[tab.action] ?? 0}</span>
          </button>
        ))}
      </nav>

      <main className="content">
        {loading && <p className="status">Loading transactions…</p>}
        {error && (
          <p className="status error">
            Failed to load transactions: {error}. Is the API running at {API_URL}?
          </p>
        )}
        {!loading && !error && visible.length === 0 && (
          <p className="status">{TABS.find((t) => t.action === activeTab)?.emptyText}</p>
        )}
        <div className="card-grid">
          {visible.map((tx) => (
            <TransactionCard key={tx.id} tx={tx} />
          ))}
        </div>
      </main>
    </>
  )
}

const VIEWS = [
  { id: 'payments', label: 'Payments' },
  { id: 'ownership', label: 'Ownership (KYB)' },
]

function App() {
  const [view, setView] = useState('payments')

  return (
    <div className="page">
      <header className="page-header">
        <h1>AML Payment Screening</h1>
        <p className="subtitle">Layer A (sanctions) + Layer B (behavioral) + Layer C (ownership)</p>
      </header>

      <nav className="view-nav">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            className={`view-btn ${view === v.id ? 'active' : ''}`}
            onClick={() => setView(v.id)}
          >
            {v.label}
          </button>
        ))}
      </nav>

      {view === 'payments' ? <PaymentsView /> : <OwnershipExplorer />}
    </div>
  )
}

export default App
