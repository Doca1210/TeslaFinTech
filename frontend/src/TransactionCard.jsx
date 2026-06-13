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

export default function TransactionCard({ tx }) {
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

      <section className="tx-section">
        <h4>Verdict Composer</h4>
        <div className="composer-summary">
          <span>Triggered layers: {tx.triggered_layers.length ? tx.triggered_layers.join(', ') : 'none'}</span>
          <span>Confidence: {(tx.confidence * 100).toFixed(0)}%</span>
          <VerdictBadge verdict={tx.verdict} />
        </div>
        <p className="explanation">{tx.explanation}</p>
      </section>
    </article>
  )
}
