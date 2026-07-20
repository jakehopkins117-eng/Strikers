import { useMemo, useState, type CSSProperties } from "react";
import type { PredictionResponse } from "../App";

type DnaRole = "support" | "risk" | "neutral";
type DnaFilter = "all" | DnaRole;

export function PredictionIntelligence({ result }: { result: PredictionResponse }) {
  const insight = result.intelligence;
  const maxFactor = Math.max(...insight.factors.map((factor) => factor.strength), 1);

  return (
    <article className="panel intelligence-card intelligence-v2">
      <header className="intelligence-heading intelligence-hero">
        <div>
          <p className="eyebrow">STRIKERS GAME INTELLIGENCE</p>
          <h3>{insight.headline}</h3>
          <p className="executive-summary">{insight.summary}</p>
        </div>
        <div className={`intelligence-grade grade-${insight.grade.toLowerCase().replace(" ", "-")}`}>
          <span>{insight.recommended_action}</span>
          <strong>{insight.grade}</strong>
          <small>{insight.edge_points.toFixed(1)}-point model edge</small>
        </div>
      </header>

      <div className="risk-strip intelligence-metrics">
        <div><span>Model grade</span><strong>{insight.grade}</strong></div>
        <div><span>Risk profile</span><strong>{insight.risk.level}</strong></div>
        <div><span>Volatility</span><strong>{insight.risk.volatility}/100</strong></div>
        <div><span>Upset probability</span><strong>{insight.risk.upset_chance.toFixed(1)}%</strong></div>
      </div>

      <section className="overview-grid">
        <OverviewCard eyebrow="PROJECTED GAME SCRIPT" title="How Strikers expects the game to unfold" text={insight.game_script} className="overview-primary" />
        <OverviewCard eyebrow="KEY MATCHUP" title="Matchup to watch" text={insight.key_matchup} />
        <OverviewCard eyebrow="CONFIDENCE CONTEXT" title="Why the grade lands here" text={insight.confidence_explanation} />
        <OverviewCard eyebrow="PRIMARY CONCERN" title="The clearest path to an upset" text={insight.primary_concern} className="overview-concern" />
        <OverviewCard eyebrow="SWING FACTOR" title="What could change the outlook" text={insight.swing_factor} className="overview-warning" />
      </section>

      <PredictionDNA insight={insight} />

      <section className="factor-breakdown factor-visual">
        <div className="factor-title">
          <div><p className="eyebrow">PREDICTION DRIVERS</p><h3>Where the matchup edge comes from</h3></div>
          <span>{insight.model_version}</span>
        </div>
        {insight.factors.map((factor) => (
          <div className="factor-row factor-row-v2" key={factor.name}>
            <div className="factor-copy">
              <div className="factor-label"><strong>{factor.name}</strong><b>{factor.favored_team}</b></div>
              <span>{factor.detail}</span>
              <div className="factor-track"><i style={{ width: factor.available ? `${Math.max(7, (factor.strength / maxFactor) * 100)}%` : "0%" }} /></div>
            </div>
            <div className="factor-score"><strong>{factor.available ? `${factor.strength.toFixed(1)} pts` : "N/A"}</strong></div>
          </div>
        ))}
      </section>

      <div className="intelligence-columns">
        <IntelligenceList title="Why the pick works" icon="↗" items={insight.advantages} emptyText="No single metric dominates this matchup." tone="positive" />
        <IntelligenceList title="Primary concerns" icon="!" items={insight.risks} emptyText="No major statistical warning was detected." tone="warning" />
        <IntelligenceList title="Before first pitch" icon="◎" items={insight.watch_items} emptyText="No additional watch items." tone="neutral" />
      </div>

      <div className="game-report editorial-note"><p className="eyebrow">ANALYST NOTE</p><p>{insight.game_report}</p></div>
      <div className="bottom-line-note"><p className="eyebrow">BOTTOM LINE</p><p>{insight.bottom_line}</p></div>
      <p className="intelligence-disclaimer">{insight.disclaimer}</p>
    </article>
  );
}

function OverviewCard({ eyebrow, title, text, className = "" }: { eyebrow: string; title: string; text: string; className?: string }) {
  return <article className={`overview-card ${className}`}><p className="eyebrow">{eyebrow}</p><h4>{title}</h4><p>{text}</p></article>;
}

function PredictionDNA({ insight }: { insight: PredictionResponse["intelligence"] }) {
  const dna = insight.prediction_dna;
  const [filter, setFilter] = useState<DnaFilter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  const components = useMemo(() => {
    if (!dna) return [];
    return filter === "all" ? dna.components : dna.components.filter((component) => component.role === filter);
  }, [dna, filter]);

  if (!dna) {
    return <section className="prediction-dna dna-unavailable"><p className="eyebrow">PREDICTION DNA</p><h3>Factor contribution data is unavailable</h3><p>Restart the local backend and confirm the API is returning model version 7.3 or newer.</p></section>;
  }

  const selectedComponent = dna.components.find((component) => component.name === selected);

  return (
    <section className="prediction-dna">
      <div className="dna-header">
        <div>
          <p className="eyebrow">PREDICTION DNA</p>
          <h3>Why Strikers picked {dna.winner}</h3>
          <p>{dna.summary}</p>
        </div>
        <div className="dna-conviction" aria-label={`${dna.conviction} out of 100 conviction`}>
          <div className="dna-ring" style={{ "--dna-score": `${dna.conviction * 3.6}deg` } as CSSProperties}>
            <span>{dna.conviction}</span><small>/100</small>
          </div>
          <strong>{dna.balance_label} signal</strong>
        </div>
      </div>

      <div className="dna-quick-read">
        <article><span>Pick</span><strong>{dna.winner}</strong></article>
        <article><span>Primary reason</span><strong>{dna.dominant_driver}</strong></article>
        <article><span>Main danger</span><strong>{dna.counterweight}</strong></article>
      </div>

      <div className="dna-split">
        <div><span>Signals supporting {dna.winner}</span><strong>{dna.alignment.toFixed(0)}%</strong></div>
        <div><span>Opposing signals</span><strong>{dna.conflict.toFixed(0)}%</strong></div>
      </div>
      <div className="dna-balance-track"><i style={{ width: `${dna.alignment}%` }} /></div>

      <div className="dna-filter-bar" aria-label="Filter prediction factors">
        {(["all", "support", "risk", "neutral"] as DnaFilter[]).map((item) => (
          <button className={filter === item ? "active" : ""} type="button" onClick={() => setFilter(item)} key={item}>
            {item === "all" ? "All signals" : item === "support" ? "Supports pick" : item === "risk" ? "Risks" : "Neutral"}
          </button>
        ))}
      </div>

      <div className="dna-components">
        {components.map((component) => (
          <button
            className={`dna-component dna-${component.role} ${selected === component.name ? "selected" : ""}`}
            type="button"
            onClick={() => setSelected(selected === component.name ? null : component.name)}
            key={component.name}
          >
            <div className="dna-component-top">
              <div><span>{component.impact}</span><strong>{component.name}</strong></div>
              <b>{component.share.toFixed(1)}%</b>
            </div>
            <div className="dna-component-track"><i style={{ width: `${Math.max(5, component.share)}%` }} /></div>
            <p>{component.favored_team === "Even" ? "Even signal" : `Favors ${component.favored_team}`}</p>
          </button>
        ))}
      </div>

      {selectedComponent && (
        <aside className={`dna-detail dna-${selectedComponent.role}`}>
          <div><span>{selectedComponent.impact}</span><strong>{selectedComponent.name}</strong></div>
          <p>{selectedComponent.detail}</p>
        </aside>
      )}

      <details className="dna-flip">
        <summary>What could flip the pick?</summary>
        {dna.flip_conditions.map((condition) => <p key={condition}>{condition}</p>)}
      </details>
    </section>
  );
}

function IntelligenceList({ title, icon, items, emptyText, tone }: { title: string; icon: string; items: string[]; emptyText: string; tone: "positive" | "warning" | "neutral" }) {
  const displayItems = items.length > 0 ? items : [emptyText];
  return (
    <section className={`intelligence-list intelligence-${tone}`}>
      <div className="intelligence-list-title"><span>{icon}</span><strong>{title}</strong></div>
      {displayItems.map((item) => <div className="intelligence-item" key={item}><i /><span>{item}</span></div>)}
    </section>
  );
}
