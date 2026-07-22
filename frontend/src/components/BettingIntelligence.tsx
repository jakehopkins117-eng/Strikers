import type { PredictionResponse } from "../App";

type Props = { result: PredictionResponse };

function oddsLabel(value: number | null): string {
  if (value === null) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

function signed(value: number | null, suffix: string): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}

export function BettingIntelligence({ result }: Props) {
  const intelligence = result.betting_intelligence;
  if (!intelligence) return null;
  const best = intelligence.best_value;

  return (
    <article className="panel betting-intelligence-card">
      <div className="betting-intelligence-head">
        <div>
          <p className="eyebrow">BETTING INTELLIGENCE v1</p>
          <h3>Model probability vs. market price</h3>
        </div>
        <span className={`value-status ${intelligence.status}`}>
          {intelligence.status === "ready" ? "Prices analyzed" : "Enter both prices"}
        </span>
      </div>

      {best && (
        <div className="best-value-banner">
          <div>
            <span>Best available value</span>
            <strong>{best.team} {oddsLabel(best.odds)}</strong>
          </div>
          <div><span>Quality</span><strong>{best.quality_score}/100</strong></div>
          <div><span>EV</span><strong>{signed(best.expected_value, "%")}</strong></div>
          <div><span>Stake</span><strong>{best.suggested_units.toFixed(2)}u</strong></div>
        </div>
      )}

      <div className="value-side-grid">
        {intelligence.sides.map((side) => (
          <div className="value-side" key={side.team}>
            <div className="value-side-title">
              <strong>{side.team}</strong>
              <span className={`value-rating rating-${side.rating.toLowerCase().replaceAll(" ", "-")}`}>
                {side.rating}
              </span>
            </div>
            <div className="quality-score-row">
              <span>Bet quality</span>
              <strong>{side.quality_score === null ? "—" : `${side.quality_score}/100`}</strong>
            </div>
            <div className="value-metrics">
              <div><span>Sportsbook</span><strong>{oddsLabel(side.odds)}</strong></div>
              <div><span>Model</span><strong>{side.model_probability.toFixed(1)}%</strong></div>
              <div><span>Implied</span><strong>{side.implied_probability === null ? "—" : `${side.implied_probability.toFixed(1)}%`}</strong></div>
              <div><span>Edge</span><strong>{signed(side.edge_points, " pts")}</strong></div>
              <div><span>Fair odds</span><strong>{oddsLabel(side.fair_odds)}</strong></div>
              <div><span>Expected value</span><strong>{signed(side.expected_value, "%")}</strong></div>
              <div><span>Full Kelly</span><strong>{side.kelly_fraction === null ? "—" : `${side.kelly_fraction.toFixed(1)}%`}</strong></div>
              <div><span>Suggested stake</span><strong>{side.suggested_units === null ? "—" : `${side.suggested_units.toFixed(2)}u`}</strong></div>
            </div>
            <p className="value-recommendation">{side.recommendation}</p>
          </div>
        ))}
      </div>
      <div className="staking-note">
        <strong>{intelligence.staking_method}</strong>
        <span>{intelligence.unit_definition}</span>
      </div>
      <small className="prop-warning">{intelligence.disclaimer}</small>
    </article>
  );
}
