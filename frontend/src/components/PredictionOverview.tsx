import type { PredictionResponse } from "../App";

function value(metric: number | null | undefined, digits = 3, suffix = "") {
  return metric == null ? "—" : `${metric.toFixed(digits)}${suffix}`;
}

function StatcastMetric({ label, away, home, lowerIsBetter = false, digits = 3, suffix = "" }: { label:string; away:number|null|undefined; home:number|null|undefined; lowerIsBetter?:boolean; digits?:number; suffix?:string }) {
  const awayWins = away != null && home != null && (lowerIsBetter ? away < home : away > home);
  const homeWins = away != null && home != null && (lowerIsBetter ? home < away : home > away);
  return <div className="sc-row">
    <strong className={awayWins ? "metric-winner" : ""}>{value(away,digits,suffix)}</strong>
    <span>{label}</span>
    <strong className={homeWins ? "metric-winner" : ""}>{value(home,digits,suffix)}</strong>
  </div>;
}

export function PredictionOverview({ result, winningProbability }: { result:PredictionResponse; winningProbability:number }) {
  const statcast = result.statcast_intelligence;
  const adjustment = result.statcast_adjustment;
  const awayLineup = statcast?.away.lineup.metrics ?? {};
  const homeLineup = statcast?.home.lineup.metrics ?? {};
  const awayStarter = statcast?.away.starter.metrics ?? {};
  const homeStarter = statcast?.home.starter.metrics ?? {};
  const score = `${result.prediction.away_score}–${result.prediction.home_score}`;

  return <section className="prediction-command">
    <article className="pick-hero panel">
      <div className="pick-hero-top">
        <div><p className="eyebrow">STRIKERS MODEL PICK</p><span className="matchup-label">{result.matchup.away} <b>at</b> {result.matchup.home}</span></div>
        <span className={`pick-status ${adjustment?.applied ? "active" : ""}`}>{adjustment?.applied ? "STATCAST APPLIED" : "CORE MODEL"}</span>
      </div>
      <div className="pick-core">
        <div><span>Projected winner</span><h3>{result.prediction.winner}</h3><div className="confidence-line"><span>{result.prediction.confidence_stars}</span><strong>{result.prediction.confidence} confidence</strong></div></div>
        <div className="probability-orb"><strong>{winningProbability.toFixed(1)}</strong><span>%</span><small>win probability</small></div>
      </div>
      <div className="pick-probabilities">
        <div><span>{result.matchup.away}</span><strong>{result.prediction.away_probability.toFixed(1)}%</strong><i><b style={{width:`${result.prediction.away_probability}%`}} /></i></div>
        <div><span>{result.matchup.home}</span><strong>{result.prediction.home_probability.toFixed(1)}%</strong><i><b style={{width:`${result.prediction.home_probability}%`}} /></i></div>
      </div>
      <div className="pick-footer"><div><span>Projected score</span><strong>{score}</strong></div><div><span>Model grade</span><strong>{result.intelligence.grade}</strong></div><div><span>Risk</span><strong>{result.intelligence.risk.level}</strong></div></div>
    </article>

    <article className="why-card panel">
      <div className="card-heading"><div><p className="eyebrow">DECISION SUMMARY</p><h3>Why Strikers likes the pick</h3></div><span className="edge-chip">{result.intelligence.edge_points.toFixed(1)} pt edge</span></div>
      <p className="why-summary">{result.intelligence.summary}</p>
      <div className="reason-list clean-reasons">{result.prediction.reasons.slice(0,5).map((reason,index)=><div className="reason-item" key={reason}><span>{index+1}</span><strong>{reason}</strong></div>)}</div>
      <div className="bottom-callout"><span>Bottom line</span><strong>{result.intelligence.bottom_line}</strong></div>
    </article>

    <article className="statcast-snapshot panel">
      <div className="card-heading"><div><p className="eyebrow">STATCAST INTELLIGENCE</p><h3>Quality-of-contact snapshot</h3></div><span className={`data-quality ${statcast?.available ? "ready" : ""}`}>{statcast?.available ? `${statcast.data_quality_score.toFixed(0)}% coverage` : "Unavailable"}</span></div>
      <div className="statcast-impact">
        <div><span>Prediction impact</span><strong className={(adjustment?.points ?? 0) >= 0 ? "positive" : "negative"}>{adjustment?.applied ? `${adjustment.points > 0 ? "+" : ""}${adjustment.points.toFixed(2)} pts` : "No change"}</strong><small>{adjustment?.favored_team ?? adjustment?.status ?? "Waiting for matched players"}</small></div>
        <div className="impact-meter"><i style={{width:`${Math.min(100,Math.abs(adjustment?.points ?? 0)/3*100)}%`}} /></div>
      </div>
      <div className="sc-table"><div className="sc-header"><strong>{result.matchup.away}</strong><span>Metric</span><strong>{result.matchup.home}</strong></div>
        <StatcastMetric label="Lineup xwOBA" away={awayLineup.xwoba} home={homeLineup.xwoba}/>
        <StatcastMetric label="Lineup xSLG" away={awayLineup.xslg} home={homeLineup.xslg}/>
        <StatcastMetric label="Barrel rate" away={awayLineup.barrel_pct} home={homeLineup.barrel_pct} digits={1} suffix="%"/>
        <StatcastMetric label="Hard-hit rate" away={awayLineup.hard_hit_pct} home={homeLineup.hard_hit_pct} digits={1} suffix="%"/>
        <StatcastMetric label="Starter xERA" away={awayStarter.xera} home={homeStarter.xera} lowerIsBetter digits={2}/>
      </div>
      <p className="statcast-note">{statcast?.note ?? "Statcast data was not returned for this prediction."}</p>
    </article>
  </section>;
}
