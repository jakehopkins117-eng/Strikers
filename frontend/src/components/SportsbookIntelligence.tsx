import type { PredictionResponse } from "../App";

type Props = { result: PredictionResponse };

function oddsLabel(value: number | null): string {
  if (value === null) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

function signed(value: number | null, suffix = ""): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}

export function SportsbookIntelligence({ result }: Props) {
  const market = result.sportsbook_intelligence;
  if (!market) return null;

  if (!market.available) {
    return (
      <article className="panel sportsbook-card sportsbook-unavailable">
        <div className="sportsbook-head">
          <div>
            <p className="eyebrow">SPORTSBOOK INTELLIGENCE v3.5</p>
            <h3>Live market comparison</h3>
          </div>
          <span className="sportsbook-status">Setup needed</span>
        </div>
        <p>{market.message}</p>
        <small className="prop-warning">The prediction engine still works normally without live sportsbook data.</small>
      </article>
    );
  }

  const best = market.best_value;
  return (
    <article className="panel sportsbook-card">
      <div className="sportsbook-head">
        <div>
          <p className="eyebrow">SPORTSBOOK INTELLIGENCE v3.5</p>
          <h3>Strikers vs. the live market</h3>
          <p>{market.bookmakers.length} sportsbooks compared through {market.provider}.</p>
        </div>
        <span className="sportsbook-status ready">Live prices</span>
      </div>

      {best && (
        <div className={`bet-score-hero recommendation-${best.recommendation.toLowerCase().replaceAll(" ", "-")}`}>
          <div>
            <span>Best value</span>
            <h3>{best.team}</h3>
            <strong>{best.recommendation}</strong>
          </div>
          <div className="bet-score-number"><strong>{best.bet_score}</strong><span>/100 Bet Score</span></div>
          <div><span>Best price</span><strong>{oddsLabel(best.best_odds)}</strong><small>{best.best_bookmaker ?? "—"}</small></div>
          <div><span>Market edge</span><strong>{signed(best.edge_points, " pts")}</strong><small>{best.value_label}</small></div>
        </div>
      )}

      <div className="sportsbook-side-grid">
        {market.sides.map((side) => (
          <section className="sportsbook-side" key={side.team}>
            <div className="sportsbook-side-title"><div><span>{side.side === "away" ? "Away" : "Home"}</span><h4>{side.team}</h4></div><b>{side.bet_score}/100</b></div>
            <div className="sportsbook-metrics">
              <div><span>Best odds</span><strong>{oddsLabel(side.best_odds)}</strong><small>{side.best_bookmaker ?? "No price"}</small></div>
              <div><span>Model</span><strong>{side.model_probability.toFixed(1)}%</strong></div>
              <div><span>No-vig market</span><strong>{side.market_probability === null ? "—" : `${side.market_probability.toFixed(1)}%`}</strong></div>
              <div><span>Edge</span><strong>{signed(side.edge_points, " pts")}</strong></div>
              <div><span>Expected value</span><strong>{signed(side.expected_value, "%")}</strong></div>
              <div><span>Books</span><strong>{side.market_depth}</strong></div>
            </div>
            <div className="sportsbook-verdict"><strong>{side.value_label}</strong><span>{side.recommendation}</span></div>
            <ul>{side.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </section>
        ))}
      </div>
      <small className="prop-warning">{market.disclaimer}</small>
    </article>
  );
}
