const RULE_LABELS = {
  structuring_7d: 'Structuring — 7-day window',
  structuring_30d: 'Structuring — 30-day window',
  rapid_movement: 'Rapid Fund Movement',
  high_value_single: 'High-Value Single Transfer',
  round_amount: 'Round-Amount Transaction',
  velocity_24h: 'High Velocity (24h)',
  dormant_account: 'Dormant Account Activity',
  cross_border_high: 'High-Risk Cross-Border Transfer',
  pep_exposure: 'Politically Exposed Person Exposure',
}

function ruleLabel(id) {
  if (RULE_LABELS[id]) return RULE_LABELS[id]
  return id
    .replace(/_(\d+[a-z]+)/g, ' ($1)')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const LAYER_LABELS = {
  layer_a_sanctions: 'Watchlist Screening',
  layer_b_behavioral: 'Behavioral Analysis',
  layer_c_ownership: 'Ownership Analysis',
}

function layerLabel(id) {
  return LAYER_LABELS[id] ?? id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const VERDICT_LABEL = {
  MATCH: 'MATCH',
  REVIEW: 'REVIEW',
  NO_MATCH: 'NO MATCH',
}

function VerdictBadge({ verdict }) {
  return <span className={`badge verdict-${verdict}`}>{VERDICT_LABEL[verdict] ?? verdict}</span>
}

function PartyResult({ role, party }) {
  return (
    <div className="party">
      <div className="party-head">
        <span className="party-role">{role}</span>
        <VerdictBadge verdict={party.verdict} />
        <span className="party-confidence">{(party.confidence * 100).toFixed(0)}%</span>
      </div>
      {party.matched_name && (
        <div className="party-match">
          → matched: {party.matched_name} <span className="entity-id">[{party.matched_entity_id}]</span>
        </div>
      )}
    </div>
  )
}

function BehavioralRules({ rulesFired }) {
  if (!rulesFired.length) {
    return <div className="rules-empty">No behavioral rules fired.</div>
  }
  return (
    <ul className="rules-list">
      {rulesFired.map((rule) => (
        <li key={rule.rule_id} className={`rule severity-${rule.severity}`}>
          <span className="rule-id">{ruleLabel(rule.rule_id)}</span>
          <span className="rule-severity">{rule.severity}</span>
          <span className="rule-score">+{rule.score}</span>
          <p className="rule-reason">{rule.explanation ?? rule.reason}</p>
        </li>
      ))}
    </ul>
  )
}

const SECTION_LABELS = {
  'Layer A (sanctions)': 'Watchlist Screening',
  'Layer B (behavioral)': 'Behavioral Analysis',
  'Layer C (ownership)': 'Ownership Analysis',
  'Sanctions screening': 'Watchlist Screening',
  'Behavioral analysis': 'Behavioral Analysis',
  'Ownership analysis': 'Ownership Analysis',
}

function formatBehavioralBody(text) {
  return text
    .replace(/outcome=(\w+)/i, (_, v) => `Outcome: ${v.charAt(0).toUpperCase() + v.slice(1)}`)
    .replace(/,?\s*score=(\d+)/, (_, s) => `  ·  Risk score: ${s}`)
    .replace(/,?\s*rules fired=\[([^\]]*)\]\.?/, (_, rules) => {
      const labels = rules
        .split(',')
        .map((r) => ruleLabel(r.trim()))
        .join(', ')
      return `  ·  Rules triggered: ${labels}`
    })
}

function ComposerExplanation({ explanation }) {
  const normalized = explanation
    .replace(/^Route to analyst queue for manual review\.\s*/, '')
    .replace(/^Block this payment and escalate to compliance\.\s*/, '')
    .replace(/^No action required — payment may proceed\.\s*/, '')
    .replace(/^(PASS|REVIEW|BLOCK)\.\s*/, '')
    .replace(/Final verdict:\s*\w+\.\s*/i, '')

  const parts = normalized
    .split(
      /(?=Layer A \(sanctions\):|Layer B \(behavioral\):|Layer C \(ownership\):|Sanctions screening:|Behavioral analysis:|Ownership analysis:)/
    )
    .map((part) => part.trim())
    .filter(Boolean)

  if (!parts.length) {
    return <p className="composer-text">{explanation}</p>
  }

  return (
    <div className="composer-detail">
      {parts.map((part) => {
        const colonIdx = part.indexOf(':')
        if (colonIdx === -1) return <p key={part} className="composer-text">{part}</p>

        const rawLabel = part.slice(0, colonIdx).trim()
        let body = part.slice(colonIdx + 1).trim()
        const label = SECTION_LABELS[rawLabel] ?? rawLabel

        const isBehavioral =
          rawLabel.toLowerCase().includes('behavioral') || rawLabel.toLowerCase().includes('behaviour')
        if (isBehavioral) body = formatBehavioralBody(body)

        const isWatchlist = label === 'Watchlist Screening'
        const sanctionsItems = isWatchlist
          ? body.split(/(?=Beneficiary\s')/).map((i) => i.trim()).filter(Boolean)
          : []

        const slug = rawLabel.toLowerCase().replace(/[\s()]/g, '-').replace(/-+/g, '-')

        return (
          <div className={`composer-row composer-row-${slug}`} key={part}>
            <span className="composer-label">{label}</span>
            {sanctionsItems.length > 1 ? (
              <ul className="composer-list">
                {sanctionsItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>{body}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function DecisionRecord({ decision }) {
  if (!decision) return null

  if (decision.type === 'manual') {
    return (
      <section className="tx-section decision-record manual-decision">
        <h4>{decision.title}</h4>
        <div className="decision-meta">
          <span>{decision.reviewer}</span>
          <span>{decision.reviewedAt}</span>
          <span className={`final-outcome outcome-${decision.outcome}`}>{decision.verdict}</span>
        </div>
        <p className="explanation">{decision.reasoning}</p>
        <div className="document-chip">Evidence: {decision.document}</div>
      </section>
    )
  }

  return (
    <section className="tx-section decision-record automatic-decision">
      <h4>{decision.title}</h4>
      <p className="explanation">{decision.reasoning}</p>
    </section>
  )
}

export default function TransactionCard({ tx, decision = null }) {
  return (
    <article className={`tx-card action-${tx.recommended_action}`}>
      <header className="tx-card-header">
        <h3>{tx.label}</h3>
        <span className={`action-badge action-${tx.recommended_action}`}>
          {tx.recommended_action.replace('_', ' ')}
        </span>
      </header>

      <dl className="tx-summary">
        <div>
          <dt>Originator</dt>
          <dd>{tx.originator}</dd>
        </div>
        <div>
          <dt>Beneficiary</dt>
          <dd>{tx.beneficiary}</dd>
        </div>
        <div>
          <dt>Amount</dt>
          <dd>
            {tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} {tx.currency}
          </dd>
        </div>
        <div>
          <dt>Counterparty country</dt>
          <dd>{tx.counterparty_country}</dd>
        </div>
      </dl>

      <section className="tx-section">
        <h4>Watchlist Screening</h4>
        <PartyResult role="Originator" party={tx.layer_a.originator} />
        <PartyResult role="Beneficiary" party={tx.layer_a.beneficiary} />
      </section>

      <section className="tx-section">
        <h4>Behavioral Analysis</h4>
        <div className="behavioral-summary">
          Risk score <strong>{tx.layer_b.score}</strong>{' '}
          <span className={`outcome-pill outcome-${tx.layer_b.outcome}`}>
            {tx.layer_b.outcome.charAt(0).toUpperCase() + tx.layer_b.outcome.slice(1)}
          </span>
        </div>
        <BehavioralRules rulesFired={tx.layer_b.rules_fired} />
      </section>

      <section className="tx-section composer-section">
        <h4>Compliance Decision</h4>
        <div className="composer-summary">
          <div className="composer-metric">
            <span>Triggered checks</span>
            <strong>
              {tx.triggered_layers.length ? tx.triggered_layers.map(layerLabel).join(', ') : 'none'}
            </strong>
          </div>
          <div className="composer-metric">
            <span>Confidence</span>
            <strong>{(tx.confidence * 100).toFixed(0)}%</strong>
          </div>
          <VerdictBadge verdict={tx.verdict} />
        </div>
        <ComposerExplanation explanation={tx.explanation} />
      </section>

      <DecisionRecord decision={decision} />
    </article>
  )
}
