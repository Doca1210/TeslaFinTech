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
          <span className="rule-id">{rule.rule_id}</span>
          <span className="rule-severity">{rule.severity}</span>
          <span className="rule-score">+{rule.score}</span>
          <p className="rule-reason">{rule.reason}</p>
        </li>
      ))}
    </ul>
  )
}

function ComposerExplanation({ explanation }) {
  const normalized = explanation
    .replace(/^Route to analyst queue for manual review\.\s*/, '')
    .replace(/^Block this payment and escalate to compliance\.\s*/, '')
    .replace(/^No action required — payment may proceed\.\s*/, '')

  const parts = normalized
    .split(/(?=Sanctions screening:|Behavioral analysis:|Ownership analysis:|Layer C \(ownership\):)/)
    .map((part) => part.trim())
    .filter(Boolean)

  if (!parts.length) {
    return <p className="composer-text">{explanation}</p>
  }

  return (
    <div className="composer-detail">
      {parts.map((part) => {
        const [label, ...rest] = part.split(':')
        const body = rest.join(':').trim()
        const sanctionsItems =
          label === 'Sanctions screening'
            ? body
                .split(/(?=Beneficiary\s')/)
                .map((item) => item.trim())
                .filter(Boolean)
            : []

        return (
          <div className={`composer-row composer-row-${label.toLowerCase().replaceAll(' ', '-')}`} key={part}>
            <span className="composer-label">{label}</span>
            {sanctionsItems.length > 1 ? (
              <ul className="composer-list">
                {sanctionsItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>{body || part}</p>
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
        <h4>Layer A — Sanctions screening</h4>
        <PartyResult role="Originator" party={tx.layer_a.originator} />
        <PartyResult role="Beneficiary" party={tx.layer_a.beneficiary} />
      </section>

      <section className="tx-section">
        <h4>Layer B — Behavioral AML</h4>
        <div className="behavioral-summary">
          Score <strong>{tx.layer_b.score}</strong> → {tx.layer_b.outcome}
        </div>
        <BehavioralRules rulesFired={tx.layer_b.rules_fired} />
      </section>

      <section className="tx-section composer-section">
        <h4>Verdict Composer</h4>
        <div className="composer-summary">
          <div className="composer-metric">
            <span>Triggered layers</span>
            <strong>{tx.triggered_layers.length ? tx.triggered_layers.join(', ') : 'none'}</strong>
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
