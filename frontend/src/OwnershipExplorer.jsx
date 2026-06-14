import { useState } from 'react'
import OwnershipGraph from './OwnershipGraph'
import './Ownership.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const DEMO_NAMES = ['Blue Horizon Trading LLC', 'Milan Textile GmbH']

const VERDICT_LABEL = { MATCH: 'MATCH', REVIEW: 'REVIEW', NO_MATCH: 'NO MATCH' }
const RISK_LABEL = {
  SANCTIONS_MATCH: 'Sanctioned',
  SANCTIONS_REVIEW: 'Possible sanctions',
  PEP_MATCH: 'PEP',
}

function VerdictBadge({ verdict }) {
  return <span className={`badge verdict-${verdict}`}>{VERDICT_LABEL[verdict] ?? verdict}</span>
}

function PathCard({ p }) {
  return (
    <li className={`kyb-path risk-${p.risk}`}>
      <div className="kyb-path-head">
        <span className="kyb-chain">{p.path.join('  →  ')}</span>
        <span className={`badge risk-badge risk-${p.risk}`}>{RISK_LABEL[p.risk] ?? p.risk}</span>
      </div>
      <div className="kyb-path-meta">
        <span>depth {p.depth}</span>
        {p.ownership_pct != null && <span>{p.ownership_pct}% direct</span>}
        {p.effective_pct != null && <span>{p.effective_pct}% effective</span>}
        {p.is_ubo && <span className="tag-ubo">UBO ≥ 25%</span>}
        <span className="kyb-via">{p.matched_via === 'live_screen' ? 'live screen' : 'seeded'} · {p.source}</span>
        <span className="kyb-score">score {p.score}</span>
      </div>
      <p className="kyb-explanation">{p.explanation}</p>
    </li>
  )
}

function ExposurePanel({ exposure, loading }) {
  if (loading) return <p className="status">Tracing controlled companies…</p>
  if (!exposure) return null
  return (
    <div className="kyb-exposure">
      <h4>
        Reverse exposure — companies <strong>{exposure.party}</strong> stands behind
        <span className="kyb-exposure-count">{exposure.controls_count}</span>
      </h4>
      {exposure.error && <p className="status error">Failed: {exposure.error}</p>}
      {!exposure.error && exposure.controls_count === 0 && (
        <p className="status">This party does not control any other company in the graph.</p>
      )}
      {exposure.controls?.length > 0 && (
        <ul className="kyb-exposure-list">
          {exposure.controls.map((c, i) => (
            <li key={i}>
              <span className="kyb-exposure-co">{c.company}</span>
              <span className="kyb-exposure-meta">
                depth {c.depth}
                {c.ownership_pct != null && ` · ${c.ownership_pct}% direct`}
                {c.effective_pct != null && ` · ${c.effective_pct}% effective`}
                {c.is_ubo && ' · UBO'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function OwnershipExplorer() {
  const [name, setName] = useState('Blue Horizon Trading LLC')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [selectedName, setSelectedName] = useState(null)
  const [exposure, setExposure] = useState(null)
  const [exposureLoading, setExposureLoading] = useState(false)

  async function runScreen(targetName) {
    const query = (targetName ?? name).trim()
    if (!query) return
    if (targetName != null) setName(targetName)
    setLoading(true)
    setError(null)
    setExposure(null)
    setSelectedName(null)
    try {
      const res = await fetch(`${API_URL}/screen/ownership?name=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  async function loadExposure(node) {
    setSelectedName(node.name)
    setExposureLoading(true)
    setExposure(null)
    try {
      const res = await fetch(`${API_URL}/ownership/exposure?name=${encodeURIComponent(node.name)}`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setExposure(await res.json())
    } catch (e) {
      setExposure({ party: node.name, error: e.message, controls: [], controls_count: 0 })
    } finally {
      setExposureLoading(false)
    }
  }

  return (
    <main className="content kyb">
      <p className="kyb-intro">
        Screen a beneficiary by name, then trace the beneficial-ownership graph. A clean
        company name can still be <strong>REVIEW</strong> when a risky party hides behind it.
        Click any node to see what it controls.
      </p>

      <form
        className="kyb-search"
        onSubmit={(e) => {
          e.preventDefault()
          runScreen()
        }}
      >
        <input
          className="kyb-input"
          type="text"
          value={name}
          placeholder="Beneficiary name, e.g. Blue Horizon Trading LLC"
          onChange={(e) => setName(e.target.value)}
        />
        <button className="kyb-btn" type="submit" disabled={loading}>
          {loading ? 'Tracing…' : 'Trace ownership'}
        </button>
      </form>

      <div className="kyb-chips">
        <span className="kyb-chips-label">Try:</span>
        {DEMO_NAMES.map((n) => (
          <button key={n} type="button" className="kyb-chip" onClick={() => runScreen(n)}>
            {n}
          </button>
        ))}
      </div>

      {error && (
        <p className="status error">
          Failed to trace ownership: {error}. Is the API running at {API_URL}? Seed demo data with{' '}
          <code>python manage.py seed-ownership</code>.
        </p>
      )}

      {result && !error && (
        <div className="kyb-result">
          <div className={`kyb-verdict-card verdict-card-${result.verdict}`}>
            <div className="kyb-verdict-head">
              <h3>{result.beneficiary}</h3>
              <VerdictBadge verdict={result.verdict} />
            </div>
            <p className="kyb-reason">{result.reason}</p>
            <div className="kyb-verdict-meta">
              <span>Risk score <strong>{result.score}</strong> / 100</span>
              <span>{result.related_parties_traced} related parties traced</span>
              <span>{result.duration_ms} ms</span>
            </div>
          </div>

          <section className="kyb-section">
            <h4>Ownership graph</h4>
            <OwnershipGraph graph={result.graph} onNodeClick={loadExposure} selectedName={selectedName} />
          </section>

          {(exposure || exposureLoading) && (
            <section className="kyb-section">
              <ExposurePanel exposure={exposure} loading={exposureLoading} />
            </section>
          )}

          <section className="kyb-section">
            <h4>Risky ownership paths</h4>
            {result.paths.length === 0 ? (
              <p className="status">No risky related parties found — beneficiary is clean by ownership.</p>
            ) : (
              <ul className="kyb-paths">
                {result.paths.map((p, i) => (
                  <PathCard key={i} p={p} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  )
}
