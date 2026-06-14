import { useEffect, useMemo, useState } from 'react'
import TransactionCard from './TransactionCard'
import OwnershipExplorer from './OwnershipExplorer'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const CURRENT_USER = {
  name: 'Danijela Ivovic',
  role: 'Senior Compliance Reviewer',
  initials: 'DI',
}

const HISTORY_TABS = [
  { outcome: 'PASS', label: 'Passed', emptyText: 'No passed transactions.' },
  { outcome: 'BLOCK', label: 'Blocked', emptyText: 'No blocked transactions.' },
]

const SUPPORTING_DOCUMENTS = [
  'KYB extract - beneficiary ownership.pdf',
  'OFAC candidate comparison.pdf',
  'Customer payment instruction.pdf',
]

const COMPLETED_REVIEWS = {
  6: {
    type: 'manual',
    outcome: 'BLOCK',
    reviewer: CURRENT_USER.name,
    title: 'Analyst verdict',
    verdict: 'Block',
    reasoning:
      'KYB graph shows a sanctioned UBO with material effective ownership. Payment remains blocked pending compliance escalation.',
    document: 'KYB extract - beneficiary ownership.pdf',
    reviewedAt: 'Today, 10:42',
  },
}

const DEFAULT_REVIEW_FORM = {
  verdict: 'BLOCK',
  reasoning: '',
  document: SUPPORTING_DOCUMENTS[0],
}

const LAYER_LABELS = {
  layer_a_sanctions: 'Sanctions match',
  layer_b_behavioral: 'Behavioral risk',
  layer_c_ownership: 'Ownership exposure',
}

const RULE_LABELS = {
  amt_large: 'Large payment',
  geo_high_risk: 'High-risk jurisdiction',
  structuring_7d: 'Structuring pattern',
  velocity_24h: 'High velocity',
  pass_through: 'Pass-through activity',
  amount_baseline_spike: 'Amount spike',
  initiation_country_mismatch: 'Country mismatch',
  beneficiary_account_name_mismatch: 'Name mismatch',
}

function humanizeTag(value) {
  return value
    .replace(/^layer_[abc]_/, '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function automaticDecision(tx) {
  return {
    type: 'automatic',
    outcome: tx.recommended_action,
    title: tx.recommended_action === 'PASS' ? 'Automatically passed' : 'Automatically blocked',
    reasoning: tx.explanation,
  }
}

function manualDecisionFromDraft(draft) {
  return {
    type: 'manual',
    outcome: draft.verdict === 'RELEASE' ? 'PASS' : 'BLOCK',
    reviewer: CURRENT_USER.name,
    title: 'Analyst verdict',
    verdict: draft.verdict === 'RELEASE' ? 'Release' : draft.verdict === 'ESCALATE' ? 'Escalate' : 'Block',
    reasoning: draft.reasoning,
    document: draft.document,
    reviewedAt: 'Just now',
  }
}

function getHistoryDecision(tx, reviewDrafts) {
  if (reviewDrafts[tx.id]) return manualDecisionFromDraft(reviewDrafts[tx.id])
  if (COMPLETED_REVIEWS[tx.id]) return COMPLETED_REVIEWS[tx.id]
  return automaticDecision(tx)
}

function ReviewQueueItem({ tx, active, draft, onSelect }) {
  const layerTags = tx.triggered_layers.map((layer) => LAYER_LABELS[layer] ?? humanizeTag(layer))
  const ruleTags = tx.layer_b.rules_fired.map((rule) => RULE_LABELS[rule.rule_id] ?? humanizeTag(rule.rule_id))
  const tags = [...layerTags, ...ruleTags]

  return (
    <button className={`review-case ${active ? 'active' : ''}`} type="button" onClick={onSelect}>
      <span className="review-case-title">{tx.label}</span>
      <span className="review-case-meta">
        {tx.beneficiary} · {(tx.confidence * 100).toFixed(0)}% confidence
      </span>
      <span className="review-case-tags">
        {tags.length > 0 ? tags.map((tag) => <span key={tag}>{tag}</span>) : <span>Manual review</span>}
        {draft && <span className="draft-tag">draft verdict</span>}
      </span>
    </button>
  )
}

function ReviewVerdictForm({ tx, draft, onSave }) {
  const [form, setForm] = useState(draft ?? DEFAULT_REVIEW_FORM)

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function submitReview(event) {
    event.preventDefault()
    const reasoning = form.reasoning.trim()
    if (!reasoning) return
    onSave(tx.id, { ...form, reasoning })
  }

  return (
    <form className="review-form" onSubmit={submitReview}>
      <div className="review-form-row">
        <label>
          Reviewer
          <input
            value={CURRENT_USER.name}
            readOnly
          />
        </label>
        <label>
          Supporting document
          <select
            value={form.document}
            onChange={(event) => updateField('document', event.target.value)}
          >
            {SUPPORTING_DOCUMENTS.map((document) => (
              <option key={document}>{document}</option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="verdict-options">
        <legend>Verdict</legend>
        {[
          { value: 'BLOCK', label: 'Block' },
          { value: 'RELEASE', label: 'Release' },
          { value: 'ESCALATE', label: 'Escalate' },
        ].map((option) => (
          <label key={option.value} className={form.verdict === option.value ? 'selected' : ''}>
            <input
              type="radio"
              name="review-verdict"
              value={option.value}
              checked={form.verdict === option.value}
              onChange={(event) => updateField('verdict', event.target.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <label>
        Reasoning
        <textarea
          value={form.reasoning}
          placeholder="Write the analyst rationale for the final decision."
          onChange={(event) => updateField('reasoning', event.target.value)}
        />
      </label>

      <div className="evidence-upload">
        <span className="evidence-upload-icon">DOC</span>
        <span>
          Attached evidence: <strong>{form.document}</strong>
        </span>
      </div>

      <button className="primary-action" type="submit" disabled={!form.reasoning.trim()}>
        Save verdict
      </button>
    </form>
  )
}

function TransactionHistory({ transactions, reviewDrafts }) {
  const [activeOutcome, setActiveOutcome] = useState('PASS')

  const closedTransactions = useMemo(() => {
    return transactions
      .filter((tx) => tx.recommended_action !== 'MANUAL_REVIEW' || reviewDrafts[tx.id])
      .map((tx) => ({ ...tx, decision: getHistoryDecision(tx, reviewDrafts) }))
  }, [transactions, reviewDrafts])

  const counts = HISTORY_TABS.reduce((acc, tab) => {
    acc[tab.outcome] = closedTransactions.filter((tx) => tx.decision.outcome === tab.outcome).length
    return acc
  }, {})

  const visible = closedTransactions.filter((tx) => tx.decision.outcome === activeOutcome)

  return (
    <section className="workspace-section" aria-labelledby="history-title">
      <div className="section-heading">
        <div>
          <h2 id="history-title">Transaction History</h2>
          <p>Closed payment decisions with automatic reasoning or analyst verdicts.</p>
        </div>
      </div>

      <nav className="tabs" aria-label="Transaction history filters">
        {HISTORY_TABS.map((tab) => (
          <button
            key={tab.outcome}
            className={`tab ${activeOutcome === tab.outcome ? 'active' : ''} tab-${tab.outcome}`}
            onClick={() => setActiveOutcome(tab.outcome)}
          >
            {tab.label}
            <span className="tab-count">{counts[tab.outcome] ?? 0}</span>
          </button>
        ))}
      </nav>

      {visible.length === 0 ? (
        <p className="status">{HISTORY_TABS.find((tab) => tab.outcome === activeOutcome)?.emptyText}</p>
      ) : (
        <div className="card-grid history-grid">
          {visible.map((tx) => (
            <TransactionCard key={tx.id} tx={tx} decision={tx.decision} />
          ))}
        </div>
      )}
    </section>
  )
}

function ReviewTool({ transactions, reviewDrafts, onSaveReview }) {
  const reviewTransactions = useMemo(
    () => transactions.filter((tx) => tx.recommended_action === 'MANUAL_REVIEW'),
    [transactions],
  )
  const [activeReviewId, setActiveReviewId] = useState(null)
  const activeTx =
    reviewTransactions.find((tx) => tx.id === activeReviewId) ?? reviewTransactions[0] ?? null

  return (
    <section className="workspace-section" aria-labelledby="review-title">
      <div className="section-heading">
        <div>
          <h2 id="review-title">Review Tool</h2>
          <p>Review pending verdicts, attach supporting evidence, and record the final decision.</p>
        </div>
        <span className="queue-count">{reviewTransactions.length} for review</span>
      </div>

      <div className="review-workbench">
        <div className="review-column">
          <h3>Verdicts for Review</h3>
          {reviewTransactions.length === 0 ? (
            <p className="status">No transactions awaiting review.</p>
          ) : (
            <div className="review-list">
              {reviewTransactions.map((tx) => (
                <ReviewQueueItem
                  key={tx.id}
                  tx={tx}
                  active={tx.id === activeTx?.id}
                  draft={reviewDrafts[tx.id]}
                  onSelect={() => setActiveReviewId(tx.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="review-column review-detail">
          {activeTx ? (
            <>
              <TransactionCard tx={activeTx} decision={reviewDrafts[activeTx.id] ? manualDecisionFromDraft(reviewDrafts[activeTx.id]) : null} />
              <ReviewVerdictForm
                key={activeTx.id}
                tx={activeTx}
                draft={reviewDrafts[activeTx.id]}
                onSave={onSaveReview}
              />
            </>
          ) : (
            <p className="status">Select a review case to write a verdict.</p>
          )}
        </div>
      </div>
    </section>
  )
}

function PaymentsWorkspace() {
  const [transactions, setTransactions] = useState([])
  const [reviewDrafts, setReviewDrafts] = useState({})
  const [activeWindow, setActiveWindow] = useState('review')
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

  function saveReview(transactionId, draft) {
    setReviewDrafts((current) => ({ ...current, [transactionId]: draft }))
  }

  if (loading) return <p className="status">Loading transactions...</p>
  if (error) {
    return (
      <p className="status error">
        Failed to load transactions: {error}. Is the API running at {API_URL}?
      </p>
    )
  }

  return (
    <main className="content window-layout">
      <nav className="window-nav" aria-label="Payment screening workspace">
        <button
          className={`window-tab ${activeWindow === 'history' ? 'active' : ''}`}
          type="button"
          onClick={() => setActiveWindow('history')}
        >
          Transaction History
        </button>
        <button
          className={`window-tab ${activeWindow === 'review' ? 'active' : ''}`}
          type="button"
          onClick={() => setActiveWindow('review')}
        >
          Review Tool
        </button>
        <button
          className={`window-tab ${activeWindow === 'ownership' ? 'active' : ''}`}
          type="button"
          onClick={() => setActiveWindow('ownership')}
        >
          Ownership (KYB)
        </button>
      </nav>

      <div className="workspace-window">
        {activeWindow === 'history' && (
          <TransactionHistory transactions={transactions} reviewDrafts={reviewDrafts} />
        )}
        {activeWindow === 'review' && (
          <ReviewTool
            transactions={transactions}
            reviewDrafts={reviewDrafts}
            onSaveReview={saveReview}
          />
        )}
        {activeWindow === 'ownership' && <OwnershipExplorer />}
      </div>
    </main>
  )
}

function App() {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Veritas Screening</h1>
        </div>
        <div className="user-profile" aria-label="Signed-in reviewer">
          <span className="user-avatar">{CURRENT_USER.initials}</span>
          <span>
            <strong>{CURRENT_USER.name}</strong>
            <small>{CURRENT_USER.role}</small>
          </span>
        </div>
      </header>

      <PaymentsWorkspace />
    </div>
  )
}

export default App
