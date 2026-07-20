import type { PredictionResponse } from "../App";

type Props = { result: PredictionResponse };

function oddsLabel(value: number | null): string {
  if (value === null) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

export function BettingIntelligence({ result }: Props) {
  const intelligence = result.betting_intelligence;
  if (!intelligence) return null;
  return (
    <article className="panel betting-intelligence-card">
      <div className="betting-intelligence-head">
        <div><p className="eyebrow">BETTING INTELLIGENCE</p><h3>Model probability vs. market price</h3></div>
        <span className={`value-status ${intelligence.status}`}>{intelligence.status === "ready" ? "Prices analyzed" : "Enter both prices"}</span>
      </div>
      <div className="value-side-grid">
        {intelligence.sides.map((side) => (
          <div className="value-side" key={side.team}>
            <div className="value-side-title"><strong>{side.team}</strong><span className={`value-rating rating-${side.rating.toLowerCase().replaceAll(" ", "-")}`}>{side.rating}</span></div>
            <div className="value-metrics">
              <div><span>Sportsbook</span><strong>{oddsLabel(side.odds)}</strong></div>
              <div><span>Model</span><strong>{side.model_probability.toFixed(1)}%</strong></div>
              <div><span>Implied</span><strong>{side.implied_probability === null ? "—" : `${side.implied_probability.toFixed(1)}%`}</strong></div>
              <div><span>Edge</span><strong>{side.edge_points === null ? "—" : `${side.edge_points >= 0 ? "+" : ""}${side.edge_points.toFixed(1)} pts`}</strong></div>
              <div><span>Fair odds</span><strong>{oddsLabel(side.fair_odds)}</strong></div>
              <div><span>Expected value</span><strong>{side.expected_value === null ? "—" : `${side.expected_value >= 0 ? "+" : ""}${side.expected_value.toFixed(1)}%`}</strong></div>
            </div>
            <p className="value-recommendation">{side.recommendation}</p>
          </div>
        ))}
      </div>
      <small className="prop-warning">{intelligence.disclaimer}</small>
    </article>
  );
}
