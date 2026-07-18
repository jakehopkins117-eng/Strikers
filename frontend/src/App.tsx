import { useEffect, useMemo, useState } from "react";
import "./App.css";

type Page =
  | "Dashboard"
  | "Matchup Predictor"
  | "Best Bets"
  | "Power Rankings"
  | "Prediction History"
  | "Team Analytics"
  | "Player Props";

type TeamOption = {
  id: number;
  name: string;
  logo: string | null;
};

type ScheduleTeam = {
  id: number;
  name: string;
  logo: string | null;
  score: number | null;
  probable_pitcher: {
    id: number;
    name: string;
  } | null;
};

type Game = {
  game_pk: number;
  game_date: string;
  official_date: string;
  venue: string | null;
  status: {
    abstract: string;
    detailed: string;
  };
  away: ScheduleTeam;
  home: ScheduleTeam;
};

type Pitcher = {
  id: number | null;
  name: string;
  available: boolean;
  era: number | null;
  whip: number | null;
  innings: number | null;
};

type PredictionResponse = {
  matchup: { away: string; home: string };
  prediction: {
    away_probability: number;
    home_probability: number;
    winner: string;
    confidence: string;
    confidence_stars: string;
    away_score: number;
    home_score: number;
    reasons: string[];
  };
  away_team: Record<string, number | string | null>;
  home_team: Record<string, number | string | null>;
  away_pitcher: Pitcher;
  home_pitcher: Pitcher;
  intelligence: {
    headline: string;
    summary: string;
    grade: string;
    edge_points: number;
    advantages: string[];
    risks: string[];
    watch_items: string[];
    recommended_action: string;
    disclaimer: string;
  };
};

type BestBet = {
  game: Game;
  winner: string;
  probability: number;
  confidence: string;
  confidence_stars: string;
  reasons: string[];
  away_probability: number;
  home_probability: number;
};

type Ranking = {
  rank: number;
  team_id: number;
  team: string;
  logo: string | null;
  wins: number;
  losses: number;
  win_pct: number;
  run_differential: number;
  last_ten: string;
  recent_win_pct: number;
  power_score: number;
};

type TeamAnalytics = {
  team: { id: number; name: string; abbreviation: string; division: string; league: string; venue: string; logo: string | null };
  period: { start: string; end: string; completed_games: number };
  summary: { wins: number; losses: number; win_pct: number; runs_per_game: number; runs_allowed_per_game: number; run_differential: number; home_record: string; road_record: string; streak: string };
  rolling: { window: number; wins: number; losses: number; win_pct: number; runs_per_game: number; runs_allowed_per_game: number; run_differential_per_game: number }[];
  trend: { date: string; result: string; runs_for: number; runs_against: number; run_differential: number }[];
  recent_games: { game_pk: number; date: string; opponent: string; home: boolean; runs_for: number; runs_against: number; result: string; run_differential: number; venue: string | null }[];
};

type PlayerProp = {
  id: string; player_id: number | null; player: string;
  team: TeamOption; opponent: TeamOption; market: string;
  projection: number; suggested_line: number; over_probability: number; under_probability: number;
  recommendation: "OVER" | "UNDER" | "PASS"; confidence: string;
  fair_over_odds: number; fair_under_odds: number; reasons: string[];
};

type PropAnalysis = { recommendation: string; over_probability: number; under_probability: number; over_edge: number; under_edge: number; fair_over_odds: number; fair_under_odds: number; expected_value: number; confidence: string; };

type HistoryItem = {
  id: string;
  created_at: string;
  away_team: string;
  home_team: string;
  winner: string;
  away_probability: number;
  home_probability: number;
  confidence: string;
  confidence_stars: string;
  projected_score: {
    away: number | null;
    home: number | null;
  };
  reasons: string[];
  away_logo: string | null;
  home_logo: string | null;
};

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const navItems: { label: Page; icon: string }[] = [
  { label: "Dashboard", icon: "⌂" },
  { label: "Matchup Predictor", icon: "⚾" },
  { label: "Best Bets", icon: "★" },
  { label: "Player Props", icon: "◎" },
  { label: "Power Rankings", icon: "▥" },
  { label: "Prediction History", icon: "↺" },
];

function todayString(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function App() {
  const [activePage, setActivePage] = useState<Page>("Dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(todayString());
  const [teams, setTeams] = useState<TeamOption[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [bestBets, setBestBets] = useState<BestBet[]>([]);
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [playerProps, setPlayerProps] = useState<PlayerProp[]>([]);
  const [loadingProps, setLoadingProps] = useState(false);
  const [propMarket, setPropMarket] = useState("All");
  const [propSearch, setPropSearch] = useState("");
  const [selectedProp, setSelectedProp] = useState<PlayerProp | null>(null);
  const [propLine, setPropLine] = useState("1.5");
  const [overOdds, setOverOdds] = useState("-110");
  const [underOdds, setUnderOdds] = useState("-110");
  const [propAnalysis, setPropAnalysis] = useState<PropAnalysis | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [teamAnalytics, setTeamAnalytics] = useState<TeamAnalytics | null>(null);
  const [analyticsTeamId, setAnalyticsTeamId] = useState<number | null>(null);
  const [awayTeam, setAwayTeam] = useState("");
  const [homeTeam, setHomeTeam] = useState("");
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [loadingPrediction, setLoadingPrediction] = useState(false);
  const [loadingBets, setLoadingBets] = useState(false);
  const [loadingRankings, setLoadingRankings] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [error, setError] = useState("");

  const winningProbability = useMemo(() => {
    if (!result) return 0;
    return Math.max(
      result.prediction.away_probability,
      result.prediction.home_probability,
    );
  }, [result]);

  useEffect(() => {
    void initialize();
  }, []);

  useEffect(() => {
    if (backendOnline) void loadSchedule(selectedDate);
  }, [selectedDate, backendOnline]);

  async function initialize() {
    try {
      const healthResponse = await fetch(`${API_URL}/health`);
      if (!healthResponse.ok) throw new Error("Backend unavailable");
      setBackendOnline(true);

      const teamsResponse = await fetch(`${API_URL}/teams`);
      const teamsPayload = (await teamsResponse.json()) as {
        teams: TeamOption[];
      };
      setTeams(teamsPayload.teams);

      if (teamsPayload.teams.length >= 2) {
        setAwayTeam(teamsPayload.teams[0].name);
        setHomeTeam(teamsPayload.teams[1].name);
      }
    } catch {
      setBackendOnline(false);
      setError("Start the Strikers FastAPI backend to load live MLB data.");
    }
  }

  async function loadSchedule(date: string) {
    setLoadingSchedule(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/schedule?date=${date}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Schedule failed.");
      setGames(payload.games as Game[]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load the MLB schedule."));
    } finally {
      setLoadingSchedule(false);
    }
  }

  async function runPrediction(away: string, home: string) {
    setAwayTeam(away);
    setHomeTeam(home);
    setError("");
    setLoadingPrediction(true);
    setActivePage("Matchup Predictor");

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ away_team: away, home_team: home }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Prediction failed.");
      setResult(payload as PredictionResponse);
      setHistory([]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not run prediction."));
    } finally {
      setLoadingPrediction(false);
    }
  }

  async function loadBestBets(force = false) {
    setActivePage("Best Bets");
    if (bestBets.length > 0 && !force) return;
    setLoadingBets(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/best-bets?date=${selectedDate}&limit=8`,
      );
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Best Bets failed.");
      setBestBets(payload.bets as BestBet[]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not calculate Best Bets."));
    } finally {
      setLoadingBets(false);
    }
  }

  async function loadPlayerProps(force = false) {
    setActivePage("Player Props");
    if (playerProps.length > 0 && !force) return;
    setLoadingProps(true); setError("");
    try {
      const response = await fetch(`${API_URL}/player-props?date=${selectedDate}&limit=90`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Player props failed.");
      setPlayerProps(payload.props as PlayerProp[]);
    } catch (requestError) { setError(errorMessage(requestError, "Could not load player props.")); }
    finally { setLoadingProps(false); }
  }

  async function analyzeProp() {
    if (!selectedProp) return; setError("");
    try {
      const response = await fetch(`${API_URL}/analyze-prop`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({player:selectedProp.player,market:selectedProp.market,projection:selectedProp.projection,line:Number(propLine),over_odds:Number(overOdds),under_odds:Number(underOdds)})});
      const payload=await response.json(); if(!response.ok) throw new Error(payload.detail ?? "Analysis failed.");
      setPropAnalysis(payload as PropAnalysis);
    } catch(requestError){setError(errorMessage(requestError,"Could not analyze prop."));}
  }

  async function loadRankings(force = false) {
    setActivePage("Power Rankings");
    if (rankings.length > 0 && !force) return;
    setLoadingRankings(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/power-rankings`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Rankings failed.");
      setRankings(payload.rankings as Ranking[]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load Power Rankings."));
    } finally {
      setLoadingRankings(false);
    }
  }

  async function loadHistory(force = false) {
    setActivePage("Prediction History");
    if (history.length > 0 && !force) return;
    setLoadingHistory(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/prediction-history?limit=100`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "History failed.");
      setHistory(payload.predictions as HistoryItem[]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load history."));
    } finally {
      setLoadingHistory(false);
    }
  }

  async function loadTeamAnalytics(teamId: number) {
    setAnalyticsTeamId(teamId);
    setActivePage("Team Analytics");
    setLoadingAnalytics(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/team-analytics/${teamId}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Team analytics failed.");
      setTeamAnalytics(payload as TeamAnalytics);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load team analytics."));
    } finally {
      setLoadingAnalytics(false);
    }
  }

  async function clearHistory() {
    const confirmed = window.confirm(
      "Clear all saved Strikers prediction history?",
    );
    if (!confirmed) return;

    try {
      const response = await fetch(`${API_URL}/prediction-history`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Could not clear history.");
      setHistory([]);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not clear history."));
    }
  }

  function navigate(page: Page) {
    setSidebarOpen(false);
    if (page === "Best Bets") void loadBestBets();
    else if (page === "Player Props") void loadPlayerProps();
    else if (page === "Power Rankings") void loadRankings();
    else if (page === "Prediction History") void loadHistory();
    else setActivePage(page);
  }

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" type="button" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">S</div>
          <div><h1>STRIKERS</h1><p>MLB Analytics</p></div>
          <button className="sidebar-close" aria-label="Close navigation" type="button" onClick={() => setSidebarOpen(false)}>×</button>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.label}
              className={`nav-button ${activePage === item.label ? "active" : ""}`}
              onClick={() => navigate(item.label)}
            >
              <span>{item.icon}</span>{item.label}
            </button>
          ))}
        </nav>

        <div className="model-card">
          <span className={`status-dot ${backendOnline ? "" : "offline"}`} />
          <div>
            <strong>{backendOnline ? "Model Online" : "Backend Offline"}</strong>
            <p>Prediction Engine 4.0</p>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-title"><button className="menu-button" aria-label="Open navigation" type="button" onClick={() => setSidebarOpen(true)}>☰</button><div><p className="eyebrow">STRIKERS COMMAND CENTER</p><h2>{activePage}</h2></div></div>
          <div className="topbar-actions">
            <span className="season-badge">Sprint 6</span>
            <div className={`api-indicator ${backendOnline ? "online" : ""}`}><span />API</div>
            <button className="profile-button" type="button">JH</button>
          </div>
        </header>

        {error && <div className="error-banner"><span>{error}</span><button type="button" aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}
        {activePage === "Dashboard" && renderDashboard()}
        {activePage === "Matchup Predictor" && renderPredictor()}
        {activePage === "Best Bets" && renderBestBets()}
        {activePage === "Player Props" && renderPlayerProps()}
        {activePage === "Power Rankings" && renderRankings()}
        {activePage === "Prediction History" && renderHistory()}
        {activePage === "Team Analytics" && renderTeamAnalytics()}
      </main>
    </div>
  );

  function renderDashboard() {
    return (
      <>
        <section className="hero-card">
          <div>
            <p className="eyebrow">LIVE MLB COMMAND CENTER</p>
            <h3>Today’s slate, powered by your model.</h3>
            <p>Browse games, probable pitchers, and launch Prediction Engine 4.0 with one click.</p>
          </div>
          <div className="hero-actions">
            <label className="date-control">Slate date
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => {
                  setSelectedDate(event.target.value);
                  setBestBets([]);
                }}
              />
            </label>
            <button className="primary-button" type="button" onClick={() => void loadBestBets()}>
              Calculate Best Bets
            </button>
          </div>
        </section>

        <section className="stats-grid">
          <StatCard label="Backend" value={backendOnline ? "Online" : "Offline"} note="FastAPI connection" positive={backendOnline} />
          <StatCard label="Games" value={loadingSchedule ? "…" : `${games.length}`} note={`Scheduled for ${selectedDate}`} />
          <StatCard label="MLB Clubs" value={`${teams.length || 30}`} note="Official team data" />
          <StatCard label="Latest Pick" value={result ? `${winningProbability.toFixed(1)}%` : "—"} note={result?.prediction.winner ?? "Select a game below"} />
        </section>

        <section className="section-heading">
          <div><p className="eyebrow">MLB SCHEDULE</p><h3>Game Center</h3></div>
          <span>{selectedDate}</span>
        </section>

        {loadingSchedule ? <LoadingCard text="Loading the MLB slate…" /> :
         games.length === 0 ? <EmptyState title="No MLB games scheduled" text="Choose another date to load a different slate." /> :
         <section className="game-grid">
           {games.map((game) => <GameCard game={game} key={game.game_pk} onPredict={() => void runPrediction(game.away.name, game.home.name)} />)}
         </section>}
      </>
    );
  }

  function renderPredictor() {
    return (
      <>
        <section className="predictor-header">
          <div><p className="eyebrow">PREDICTION ENGINE 4.0</p><h3>Matchup Predictor</h3><p>Choose any two teams or launch a game from the dashboard.</p></div>
          <div className={`connection-pill ${backendOnline ? "online" : ""}`}><span />{backendOnline ? "Backend connected" : "Backend offline"}</div>
        </section>

        <section className="matchup-builder panel">
          <TeamSelect label="Away team" value={awayTeam} teams={teams} onChange={setAwayTeam} />
          <div className="versus-orb">AT</div>
          <TeamSelect label="Home team" value={homeTeam} teams={teams} onChange={setHomeTeam} />
          <button className="primary-button" type="button" disabled={loadingPrediction || !awayTeam || !homeTeam} onClick={() => void runPrediction(awayTeam, homeTeam)}>
            {loadingPrediction ? "Analyzing…" : "Run Prediction"}
          </button>
        </section>

        {loadingPrediction && <LoadingCard text="Analyzing matchup data…" />}
        {result && !loadingPrediction && (
          <section className="result-grid">
            <article className="winner-card panel">
              <p className="eyebrow">MODEL PICK</p>
              <span className="matchup-label">{result.matchup.away} at {result.matchup.home}</span>
              <h3>{result.prediction.winner}</h3>
              <strong className="probability-number">{winningProbability.toFixed(1)}%</strong>
              <div className="confidence-line"><span>{result.prediction.confidence_stars}</span><strong>{result.prediction.confidence}</strong></div>
              <ProbabilityBar label={result.matchup.away} value={result.prediction.away_probability} />
              <ProbabilityBar label={result.matchup.home} value={result.prediction.home_probability} />
            </article>

            <article className="panel">
              <p className="eyebrow">MODEL EXPLANATION</p>
              <h3>Why Strikers likes this side</h3>
              <div className="reason-list">
                {result.prediction.reasons.map((reason) => <div className="reason-item" key={reason}><span>✓</span><strong>{reason}</strong></div>)}
              </div>
            </article>
            <GameIntelligence result={result} />
            <TeamComparison result={result} />
            <PitcherComparison result={result} />
          </section>
        )}
      </>
    );
  }

  function renderBestBets() {
    return (
      <>
        <section className="section-heading bets-heading">
          <div><p className="eyebrow">AUTOMATIC MODEL RANKING</p><h3>Best Bets</h3><p>Every scheduled matchup ranked by highest model probability.</p></div>
          <button className="secondary-button" type="button" onClick={() => void loadBestBets(true)}>Recalculate</button>
        </section>

        {loadingBets ? <LoadingCard text="Running every game through Prediction Engine 4.0…" /> :
         bestBets.length === 0 ? <EmptyState title="No Best Bets available" text="Choose a slate with scheduled games and recalculate." /> :
         <section className="bets-list">
           {bestBets.map((bet, index) => (
             <article className="bet-card panel" key={bet.game.game_pk}>
               <div className="bet-rank">#{index + 1}</div>
               <TeamLogo team={bet.game.away} />
               <div className="bet-main">
                 <span className="bet-matchup">{bet.game.away.name} at {bet.game.home.name}</span>
                 <h3>{bet.winner}</h3>
                 <div className="bet-meta"><span>{bet.confidence_stars}</span><strong>{bet.confidence}</strong><span>{formatTime(bet.game.game_date)}</span></div>
               </div>
               <div className="bet-probability"><strong>{bet.probability.toFixed(1)}%</strong><span>model probability</span></div>
               <button className="secondary-button" type="button" onClick={() => void runPrediction(bet.game.away.name, bet.game.home.name)}>Full Analysis</button>
             </article>
           ))}
         </section>}
      </>
    );
  }

  function renderPlayerProps() {
    const markets=["All",...Array.from(new Set(playerProps.map((prop)=>prop.market)))];
    const filtered=playerProps.filter((prop)=>(propMarket==="All"||prop.market===propMarket)&&prop.player.toLowerCase().includes(propSearch.toLowerCase()));
    return <>
      <section className="section-heading bets-heading"><div><p className="eyebrow">SPRINT 6 · PLAYER PROJECTIONS</p><h3>Player Props Lab</h3><p>Model-generated reference lines using current MLB season rates. Enter sportsbook odds to evaluate value.</p></div><button className="secondary-button" type="button" onClick={()=>void loadPlayerProps(true)}>Refresh slate</button></section>
      <section className="prop-toolbar panel"><input placeholder="Search player…" value={propSearch} onChange={(e)=>setPropSearch(e.target.value)}/><select value={propMarket} onChange={(e)=>setPropMarket(e.target.value)}>{markets.map((m)=><option key={m}>{m}</option>)}</select><span>{filtered.length} projections · {selectedDate}</span></section>
      {loadingProps?<LoadingCard text="Building player projections…"/>:filtered.length===0?<EmptyState title="No player props available" text="Probable pitchers, active rosters, or season stats may not be posted for this slate yet."/>:<section className="prop-grid">{filtered.map((prop)=><article className="prop-card panel" key={prop.id}>
        <div className="prop-card-head"><div className="prop-player"><div className="team-logo-wrap">{prop.team.logo?<img src={prop.team.logo} className="team-logo" alt=""/>:prop.team.name.slice(0,2)}</div><div><h3>{prop.player}</h3><span>{prop.team.name} vs {prop.opponent.name}</span></div></div><span className={`prop-badge ${prop.recommendation.toLowerCase()}`}>{prop.recommendation}</span></div>
        <div className="prop-market">{prop.market}</div><div className="prop-numbers"><div><span>Projection</span><strong>{prop.projection}</strong></div><div><span>Reference line</span><strong>{prop.suggested_line}</strong></div><div><span>Over chance</span><strong>{prop.over_probability}%</strong></div></div>
        <div className="prop-meter"><span style={{width:`${prop.over_probability}%`}}/></div><div className="prop-meta"><span>{prop.confidence}</span><span>Fair O {prop.fair_over_odds>0?"+":""}{prop.fair_over_odds}</span></div>
        <ul>{prop.reasons.map((r)=><li key={r}>{r}</li>)}</ul><button className="primary-button full-width" type="button" onClick={()=>{setSelectedProp(prop);setPropLine(String(prop.suggested_line));setPropAnalysis(null);}}>Analyze sportsbook line</button>
      </article>)}</section>}
      {selectedProp&&<div className="prop-modal-backdrop" onClick={()=>setSelectedProp(null)}><section className="prop-modal panel" onClick={(e)=>e.stopPropagation()}><button className="modal-close" onClick={()=>setSelectedProp(null)}>×</button><p className="eyebrow">PROP VALUE ANALYZER</p><h3>{selectedProp.player} · {selectedProp.market}</h3><p>Model projection: <strong>{selectedProp.projection}</strong></p><div className="prop-form"><label>Sportsbook line<input type="number" step="0.5" value={propLine} onChange={(e)=>setPropLine(e.target.value)}/></label><label>Over odds<input type="number" value={overOdds} onChange={(e)=>setOverOdds(e.target.value)}/></label><label>Under odds<input type="number" value={underOdds} onChange={(e)=>setUnderOdds(e.target.value)}/></label></div><button className="primary-button full-width" onClick={()=>void analyzeProp()}>Calculate value</button>{propAnalysis&&<div className="analysis-result"><span>Recommendation</span><h3>{propAnalysis.recommendation}</h3><div className="prop-numbers"><div><span>Over</span><strong>{propAnalysis.over_probability}%</strong></div><div><span>Under</span><strong>{propAnalysis.under_probability}%</strong></div><div><span>EV</span><strong>{propAnalysis.expected_value>0?"+":""}{propAnalysis.expected_value}%</strong></div></div><p>Edges: Over {propAnalysis.over_edge}% · Under {propAnalysis.under_edge}% · {propAnalysis.confidence}</p></div>}<small className="prop-warning">Informational model output only. Lines shown by default are estimates, not live sportsbook offers.</small></section></div>}
    </>;
  }

  function renderRankings() {
    return (
      <>
        <section className="section-heading bets-heading">
          <div><p className="eyebrow">LEAGUE-WIDE ANALYTICS</p><h3>MLB Power Rankings</h3><p>Composite score using season record, recent form, and run differential.</p></div>
          <button className="secondary-button" type="button" onClick={() => void loadRankings(true)}>Refresh Rankings</button>
        </section>

        {loadingRankings ? <LoadingCard text="Calculating all 30 MLB teams…" /> :
         rankings.length === 0 ? <EmptyState title="Rankings unavailable" text="Press Refresh Rankings to try again." /> :
         <section className="rankings-panel panel">
           <div className="ranking-head">
             <span>Rank</span><span>Team</span><span>Record</span><span>Last 10</span><span>Run Diff</span><span>Score</span>
           </div>
           {rankings.map((team) => (
             <div className="ranking-row" key={team.team_id}>
               <strong className={`rank-number ${team.rank <= 3 ? "top-rank" : ""}`}>{team.rank}</strong>
               <button className="ranking-team team-link" type="button" onClick={() => void loadTeamAnalytics(team.team_id)}>
                 <div className="mini-logo">{team.logo ? <img src={team.logo} alt="" /> : team.team.slice(0, 2)}</div>
                 <div><strong>{team.team}</strong><span>{(team.win_pct * 100).toFixed(1)}% win rate · View analytics</span></div>
               </button>
               <strong>{team.wins}-{team.losses}</strong>
               <span>{team.last_ten}</span>
               <strong className={team.run_differential >= 0 ? "positive" : "negative"}>{team.run_differential > 0 ? "+" : ""}{team.run_differential}</strong>
               <div className="power-score"><strong>{team.power_score.toFixed(1)}</strong><div><span style={{ width: `${team.power_score}%` }} /></div></div>
             </div>
           ))}
         </section>}
      </>
    );
  }

  function renderTeamAnalytics() {
    if (loadingAnalytics) return <LoadingCard text="Building advanced team report…" />;
    if (!teamAnalytics) return <EmptyState title="Choose a team" text="Open Power Rankings and click a team to view its analytics page." />;

    const data = teamAnalytics;
    const maxTrend = Math.max(1, ...data.trend.map((game) => Math.max(game.runs_for, game.runs_against)));

    return (
      <>
        <section className="team-hero panel">
          <div className="team-hero-identity">
            <div className="large-team-logo">{data.team.logo ? <img src={data.team.logo} alt="" /> : data.team.abbreviation}</div>
            <div><p className="eyebrow">ADVANCED TEAM REPORT</p><h3>{data.team.name}</h3><p>{data.team.division} · {data.team.venue}</p></div>
          </div>
          <label className="analytics-selector">Change team
            <select value={analyticsTeamId ?? data.team.id} onChange={(event) => void loadTeamAnalytics(Number(event.target.value))}>
              {teams.map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}
            </select>
          </label>
        </section>

        <section className="stats-grid analytics-stats">
          <StatCard label="Recent Record" value={`${data.summary.wins}-${data.summary.losses}`} note={`${(data.summary.win_pct * 100).toFixed(1)}% win rate`} positive={data.summary.win_pct >= .5} />
          <StatCard label="Run Differential" value={`${data.summary.run_differential > 0 ? "+" : ""}${data.summary.run_differential}`} note={`${data.summary.runs_per_game.toFixed(2)} scored / game`} positive={data.summary.run_differential > 0} />
          <StatCard label="Home / Road" value={data.summary.home_record} note={`Road: ${data.summary.road_record}`} />
          <StatCard label="Current Streak" value={data.summary.streak} note={`${data.period.completed_games} games analyzed`} positive={data.summary.streak.startsWith("W")} />
        </section>

        <section className="analytics-layout">
          <article className="panel trend-card">
            <p className="eyebrow">LAST 15 GAMES</p><h3>Run Production Trend</h3>
            <div className="trend-chart">
              {data.trend.map((game) => <div className="trend-column" key={game.date}>
                <div className="trend-bars">
                  <span className="runs-for-bar" style={{ height: `${(game.runs_for / maxTrend) * 100}%` }} />
                  <span className="runs-against-bar" style={{ height: `${(game.runs_against / maxTrend) * 100}%` }} />
                </div>
                <strong className={game.result === "W" ? "positive" : "negative"}>{game.result}</strong>
                <small>{game.date.slice(5)}</small>
              </div>)}
            </div>
            <div className="chart-legend"><span><i className="legend-for" />Runs scored</span><span><i className="legend-against" />Runs allowed</span></div>
          </article>

          <article className="panel rolling-card">
            <p className="eyebrow">ROLLING PERFORMANCE</p><h3>Form by Window</h3>
            <div className="rolling-list">{data.rolling.map((window) =>
              <div className="rolling-row" key={window.window}>
                <div><strong>Last {window.window}</strong><span>{window.wins}-{window.losses}</span></div>
                <div className="rolling-meter"><span style={{ width: `${window.win_pct * 100}%` }} /></div>
                <strong>{(window.win_pct * 100).toFixed(0)}%</strong>
                <small>{window.run_differential_per_game >= 0 ? "+" : ""}{window.run_differential_per_game.toFixed(2)} RD/G</small>
              </div>)}</div>
          </article>

          <article className="panel recent-games-card">
            <p className="eyebrow">RECENT RESULTS</p><h3>Last 10 Games</h3>
            <div className="recent-games-list">{data.recent_games.map((game) =>
              <div className="recent-game-row" key={game.game_pk}>
                <strong className={`result-badge ${game.result === "W" ? "win" : "loss"}`}>{game.result}</strong>
                <div><strong>{game.home ? "vs" : "at"} {game.opponent}</strong><span>{game.date} · {game.venue ?? "Venue TBD"}</span></div>
                <strong>{game.runs_for}-{game.runs_against}</strong>
              </div>)}</div>
          </article>

          <article className="panel insight-card">
            <p className="eyebrow">STRIKERS SNAPSHOT</p><h3>What the trend says</h3>
            <div className="insight-list">
              <InsightItem label="Offense" value={`${data.summary.runs_per_game.toFixed(2)} runs/game`} positive={data.summary.runs_per_game >= data.summary.runs_allowed_per_game} />
              <InsightItem label="Run prevention" value={`${data.summary.runs_allowed_per_game.toFixed(2)} allowed/game`} positive={data.summary.runs_allowed_per_game <= data.summary.runs_per_game} />
              <InsightItem label="Recent momentum" value={data.summary.streak} positive={data.summary.streak.startsWith("W")} />
              <InsightItem label="Overall form" value={data.summary.win_pct >= .6 ? "Hot" : data.summary.win_pct >= .5 ? "Competitive" : "Cooling"} positive={data.summary.win_pct >= .5} />
            </div>
          </article>
        </section>
      </>
    );
  }

  function renderHistory() {
    return (
      <>
        <section className="section-heading bets-heading">
          <div><p className="eyebrow">SAVED MODEL OUTPUT</p><h3>Prediction History</h3><p>Every manually generated prediction is stored automatically.</p></div>
          <div className="history-actions">
            <button className="secondary-button" type="button" onClick={() => void loadHistory(true)}>Refresh</button>
            <button className="danger-button" type="button" onClick={() => void clearHistory()}>Clear History</button>
          </div>
        </section>

        {loadingHistory ? <LoadingCard text="Loading saved predictions…" /> :
         history.length === 0 ? <EmptyState title="No saved predictions yet" text="Run a matchup prediction and it will appear here automatically." /> :
         <section className="history-grid">
           {history.map((item) => {
             const probability = Math.max(item.away_probability, item.home_probability);
             return (
               <article className="history-card panel" key={item.id}>
                 <div className="history-top"><span>{formatDateTime(item.created_at)}</span><span className="history-confidence">{item.confidence_stars} {item.confidence}</span></div>
                 <div className="history-matchup">
                   <HistoryTeam logo={item.away_logo} name={item.away_team} probability={item.away_probability} />
                   <div className="history-vs">AT</div>
                   <HistoryTeam logo={item.home_logo} name={item.home_team} probability={item.home_probability} />
                 </div>
                 <div className="history-pick"><span>Model pick</span><h3>{item.winner}</h3><strong>{probability.toFixed(1)}%</strong></div>
                 {item.projected_score.away !== null && item.projected_score.home !== null && (
                   <div className="projected-score">Projected score: <strong>{item.away_team} {item.projected_score.away} – {item.home_team} {item.projected_score.home}</strong></div>
                 )}
                 <button className="secondary-button full-width" type="button" onClick={() => void runPrediction(item.away_team, item.home_team)}>Run Again</button>
               </article>
             );
           })}
         </section>}
      </>
    );
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function TeamSelect({ label, value, teams, onChange }: { label: string; value: string; teams: TeamOption[]; onChange: (value: string) => void }) {
  return <label className="team-select">{label}<select value={value} onChange={(event) => onChange(event.target.value)}>{teams.map((team) => <option value={team.name} key={team.id}>{team.name}</option>)}</select></label>;
}

function TeamLogo({ team }: { team: ScheduleTeam }) {
  return <div className="team-logo-wrap">{team.logo ? <img src={team.logo} alt="" className="team-logo" /> : <span>{team.name.slice(0, 2).toUpperCase()}</span>}</div>;
}

function HistoryTeam({ logo, name, probability }: { logo: string | null; name: string; probability: number }) {
  return <div className="history-team"><div className="team-logo-wrap">{logo ? <img src={logo} alt="" className="team-logo" /> : name.slice(0, 2)}</div><strong>{name}</strong><span>{probability.toFixed(1)}%</span></div>;
}

function GameCard({ game, onPredict }: { game: Game; onPredict: () => void }) {
  const live = game.status.abstract === "Live";
  const final = game.status.abstract === "Final";
  return <article className="game-card panel">
    <div className="game-card-top"><span className={`game-status ${live ? "live" : ""}`}>{game.status.detailed}</span><span>{formatTime(game.game_date)}</span></div>
    <div className="game-team"><TeamLogo team={game.away} /><div><strong>{game.away.name}</strong><span>{game.away.probable_pitcher?.name ?? "Starter TBD"}</span></div>{(live || final) && <b>{game.away.score ?? 0}</b>}</div>
    <div className="game-team"><TeamLogo team={game.home} /><div><strong>{game.home.name}</strong><span>{game.home.probable_pitcher?.name ?? "Starter TBD"}</span></div>{(live || final) && <b>{game.home.score ?? 0}</b>}</div>
    <div className="game-card-footer"><span>{game.venue ?? "Venue TBD"}</span><button className="secondary-button" type="button" onClick={onPredict}>Predict</button></div>
  </article>;
}

function StatCard({ label, value, note, positive = false }: { label: string; value: string; note: string; positive?: boolean }) {
  return <article className="stat-card"><span>{label}</span><strong className={positive ? "positive" : ""}>{value}</strong><small>{note}</small></article>;
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  return <div className="probability-row"><div><strong>{label}</strong><span>{value.toFixed(1)}%</span></div><div className="probability-track"><div className="probability-fill" style={{ width: `${value}%` }} /></div></div>;
}


function GameIntelligence({ result }: { result: PredictionResponse }) {
  const insight = result.intelligence;

  return (
    <article className="panel intelligence-card">
      <div className="intelligence-heading">
        <div>
          <p className="eyebrow">STRIKERS GAME INTELLIGENCE</p>
          <h3>{insight.headline}</h3>
          <p>{insight.summary}</p>
        </div>
        <div className={`intelligence-grade grade-${insight.grade.toLowerCase().replace(" ", "-")}`}>
          <span>{insight.recommended_action}</span>
          <strong>{insight.grade}</strong>
          <small>{insight.edge_points.toFixed(1)}-point edge</small>
        </div>
      </div>

      <div className="intelligence-columns">
        <IntelligenceList
          title="Key advantages"
          icon="↗"
          items={insight.advantages}
          emptyText="No single metric dominates this matchup."
          tone="positive"
        />
        <IntelligenceList
          title="Risk factors"
          icon="!"
          items={insight.risks}
          emptyText="No major statistical warning was detected."
          tone="warning"
        />
        <IntelligenceList
          title="Before first pitch"
          icon="◎"
          items={insight.watch_items}
          emptyText="No additional watch items."
          tone="neutral"
        />
      </div>

      <p className="intelligence-disclaimer">{insight.disclaimer}</p>
    </article>
  );
}

function IntelligenceList({
  title,
  icon,
  items,
  emptyText,
  tone,
}: {
  title: string;
  icon: string;
  items: string[];
  emptyText: string;
  tone: "positive" | "warning" | "neutral";
}) {
  const displayItems = items.length > 0 ? items : [emptyText];

  return (
    <section className={`intelligence-list intelligence-${tone}`}>
      <div className="intelligence-list-title">
        <span>{icon}</span>
        <strong>{title}</strong>
      </div>
      {displayItems.map((item) => (
        <div className="intelligence-item" key={item}>
          <i />
          <span>{item}</span>
        </div>
      ))}
    </section>
  );
}

function TeamComparison({ result }: { result: PredictionResponse }) {
  const away = result.away_team; const home = result.home_team;
  const rows = [
    ["Season win %", percentValue(away.win_pct), percentValue(home.win_pct)],
    ["Location win %", percentValue(away.location_win_pct), percentValue(home.location_win_pct)],
    ["OPS", fixedValue(away.ops, 3), fixedValue(home.ops, 3)],
    ["Runs / game", fixedValue(away.runs_per_game, 2), fixedValue(home.runs_per_game, 2)],
    ["Team ERA", fixedValue(away.era, 2), fixedValue(home.era, 2)],
    ["Team WHIP", fixedValue(away.whip, 2), fixedValue(home.whip, 2)],
    ["Recent run diff", fixedValue(away.recent_run_differential_per_game, 2), fixedValue(home.recent_run_differential_per_game, 2)],
  ];
  return <article className="panel comparison-card"><p className="eyebrow">TEAM COMPARISON</p><h3>Season and recent-form metrics</h3><div className="comparison-header"><span>Metric</span><strong>{result.matchup.away}</strong><strong>{result.matchup.home}</strong></div>{rows.map(([label, a, h]) => <div className="comparison-row" key={label}><span>{label}</span><strong>{a}</strong><strong>{h}</strong></div>)}</article>;
}

function PitcherComparison({ result }: { result: PredictionResponse }) {
  return <article className="panel pitcher-card"><p className="eyebrow">PROBABLE STARTERS</p><h3>Pitcher matchup</h3><div className="pitcher-grid"><PitcherPanel team={result.matchup.away} pitcher={result.away_pitcher} /><span className="pitcher-vs">VS</span><PitcherPanel team={result.matchup.home} pitcher={result.home_pitcher} /></div></article>;
}

function PitcherPanel({ team, pitcher }: { team: string; pitcher: Pitcher }) {
  return <div className="pitcher-panel"><span>{team}</span><h4>{pitcher.name}</h4>{pitcher.available ? <div className="pitcher-stats"><div>ERA <strong>{pitcher.era?.toFixed(2)}</strong></div><div>WHIP <strong>{pitcher.whip?.toFixed(2)}</strong></div><div>IP <strong>{pitcher.innings?.toFixed(1)}</strong></div></div> : <p>Pitcher statistics unavailable.</p>}</div>;
}

function InsightItem({ label, value, positive }: { label: string; value: string; positive: boolean }) {
  return <div className="insight-item"><span>{label}</span><strong className={positive ? "positive" : "negative"}>{value}</strong></div>;
}

function LoadingCard({ text }: { text: string }) {
  return <div className="loading-card panel"><div className="loader" /><strong>{text}</strong></div>;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return <section className="empty-state panel"><div>◇</div><p className="eyebrow">STRIKERS</p><h3>{title}</h3><p>{text}</p></section>;
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function fixedValue(value: unknown, places: number): string {
  const parsed = numeric(value); return parsed === null ? "—" : parsed.toFixed(places);
}
function percentValue(value: unknown): string {
  const parsed = numeric(value); return parsed === null ? "—" : `${(parsed * 100).toFixed(1)}%`;
}

export default App;
