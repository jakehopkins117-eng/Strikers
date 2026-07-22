import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { PredictionIntelligence } from "./components/PredictionIntelligence";
import { BettingIntelligence } from "./components/BettingIntelligence";
import { SportsbookIntelligence } from "./components/SportsbookIntelligence";

type Page =
  | "Dashboard"
  | "Live Games"
  | "Matchup Predictor"
  | "Best Bets"
  | "Power Rankings"
  | "Prediction History"
  | "Team Analytics"
  | "Player Props"
  | "Model Performance"
  | "Weather Center"
  | "Model Lab";

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


type LiveGame = Game & {
  inning: number | null;
  inning_label: string;
  count: { balls:number; strikes:number; outs:number };
  bases: { first:boolean; second:boolean; third:boolean };
  current_batter: string | null;
  current_pitcher: string | null;
  prediction: HistoryItem | null;
  live_probability: { home:number; away:number; method:string } | null;
};

type LiveGamesPayload = { date:string; updated_at:string; refresh_seconds:number; total_games:number; live_count:number; games:LiveGame[] };

type Pitcher = {
  id: number | null;
  name: string;
  available: boolean;
  era: number | null;
  whip: number | null;
  innings: number | null;
};


type LineupPlayer = { player_id:number; name:string; position:string; ops:number|null };
type LineupSide = { status:string; confirmed:boolean; strength_score:number; average_ops:number|null; batting_order:LineupPlayer[]; note:string };
type InjuryPlayer = { player_id:number|null; name:string; position:string; status:string; impact:string };
type InjurySide = { players:InjuryPlayer[]; count:number; penalty_points:number };
type GameAnalyst = { title:string; pick:string; win_probability:number; verdict:string; summary:string; key_reasons:string[]; biggest_risks:string[]; lineup_status:string; model_adjustment:{lineup_adjustment:number;injury_adjustment:number;total_adjustment:number}; disclaimer:string };

type Bullpen = {
  team_id: number;
  team_name: string;
  availability_score: number;
  fatigue_level: string;
  games_analyzed: number;
  total_pitches_3d: number;
  relievers_used_3d: number;
  overworked_relievers: number;
  unavailable_relievers: number;
  season_era: number | null;
  season_whip: number | null;
  available: boolean;
  note: string;
  relievers: { player_id:number; name:string; pitches:number; appearances:number; used_yesterday:boolean; used_back_to_back:boolean; status:string }[];
};

type SportsbookSide = {
  team:string; side:string; model_probability:number; market_probability:number|null; consensus_implied_probability:number|null;
  edge_points:number|null; best_odds:number|null; best_bookmaker:string|null; best_link:string|null; expected_value:number|null;
  bet_score:number; value_label:string; recommendation:string; recommendation_detail:string; market_depth:number; reasons:string[];
};

export type PredictionResponse = {
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
  away_bullpen: Bullpen;
  home_bullpen: Bullpen;
  lineup_intelligence: { game_pk:number|null; away:LineupSide; home:LineupSide; available:boolean };
  injury_intelligence: { away:InjurySide; home:InjurySide; available:boolean; note:string };
  prediction_adjustments: { lineup_adjustment:number; injury_adjustment:number; total_adjustment:number };
  game_analyst: GameAnalyst;
  betting_intelligence?: {
    market: string; status: string; disclaimer: string; staking_method:string; unit_definition:string;
    best_value: null | { team:string; odds:number|null; quality_score:number; expected_value:number|null; suggested_units:number };
    sides: { team:string; model_probability:number; odds:number|null; implied_probability:number|null; edge_points:number|null; fair_odds:number; expected_value:number|null; rating:string; recommendation:string; quality_score:number|null; kelly_fraction:number|null; suggested_units:number|null }[];
  };
  sportsbook_intelligence?: {
    available:boolean; status:string; message:string; provider:string; event_id?:string; commence_time?:string; last_update?:string;
    best_value:null|SportsbookSide; sides:SportsbookSide[];
    bookmakers:{key:string;name:string;last_update:string|null;link:string|null;away_odds:number|null;home_odds:number|null}[];
    spreads:{bookmaker:string;team:string;point:number|null;odds:number|null;last_update:string|null}[];
    totals:{bookmaker:string;side:string;point:number|null;odds:number|null;last_update:string|null}[];
    quota:Record<string,string|number|boolean|null>; disclaimer:string;
  };
  ml_second_opinion?: { available:boolean; status:string; winner:string|null; home_probability:number|null; away_probability:number|null; agreement:boolean|null; message?:string };
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
    game_report: string;
    primary_concern: string;
    bottom_line: string;
    key_matchup: string;
    game_script: string;
    confidence_explanation: string;
    swing_factor: string;
    model_version: string;
    factors: { name:string; home_points:number; away_points:number; favored_team:string; strength:number; detail:string; available:boolean }[];
    prediction_dna?: {
      winner: string; alignment: number; conflict: number; conviction: number; balance_label: string;
      dominant_driver: string; counterweight: string; summary: string;
      components: { name:string; favored_team:string; strength:number; share:number; role:"support"|"risk"|"neutral"; impact:string; detail:string }[];
      flip_conditions: string[];
    };
    risk: { level:string; volatility:number; upset_chance:number; confidence:number };
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
  bet_score:number|null;
  edge_points:number|null;
  best_odds:number|null;
  best_bookmaker:string|null;
  recommendation:string|null;
  sportsbook_intelligence?:PredictionResponse["sportsbook_intelligence"];
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

type Performance = { summary: { total_predictions:number; graded_predictions:number; pending_predictions:number; wins:number; losses:number; accuracy:number; units:number; roi:number; current_streak:number; streak_type:string|null }; confidence_tiers:{tier:string;predictions:number;wins:number;accuracy:number}[]; trend:{date:string;accuracy:number;predictions:number;cumulative_units:number}[]; team_performance:{team:string;predictions:number;wins:number;accuracy:number}[]; calibration:{bucket:string;predictions:number;expected:number;actual:number}[]; recent:HistoryItem[]; };


type ModelLab = {
  engine:string; architecture:string; status:string; games_evaluated:number; accuracy:number; roi:number; units:number; calibration:string;
  features:{name:string;importance:number;description:string}[]; limitations:string[];
};

type WeatherGame = Game & { weather: { indoor:boolean; available:boolean; temperature_f?:number; precipitation_probability?:number; wind_mph?:number; gust_mph?:number; impact:string; impact_score:number; summary:string } };

type DashboardSummary = { database: { total:number; graded:number; pending:number; wins:number; losses:number; accuracy:number; recent:HistoryItem[] }; ml:{available:boolean;status:string;trained_rows?:number}; odds?:{provider:string;configured:boolean;cache_valid:boolean;cached_events:number;remaining_requests?:string|null}; engine:string; release:string };

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
  result?: "win" | "loss";
  actual?: { winner:string; away_score:number; home_score:number };
};

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const navItems: { label: Page; icon: string }[] = [
  { label: "Dashboard", icon: "⌂" },
  { label: "Live Games", icon: "●" },
  { label: "Matchup Predictor", icon: "⚾" },
  { label: "Best Bets", icon: "★" },
  { label: "Player Props", icon: "◎" },
  { label: "Power Rankings", icon: "▥" },
  { label: "Model Performance", icon: "↗" },
  { label: "Weather Center", icon: "☁" },
  { label: "Model Lab", icon: "◈" },
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
  const [liveGames, setLiveGames] = useState<LiveGame[]>([]);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState<string | null>(null);
  const [loadingLive, setLoadingLive] = useState(false);
  const [liveFilter, setLiveFilter] = useState<"All"|"Live"|"Upcoming"|"Final">("All");
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
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [weatherGames, setWeatherGames] = useState<WeatherGame[]>([]);
  const [loadingPerformance, setLoadingPerformance] = useState(false);
  const [loadingWeather, setLoadingWeather] = useState(false);
  const [modelLab, setModelLab] = useState<ModelLab | null>(null);
  const [loadingModelLab, setLoadingModelLab] = useState(false);
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
  const [awayOdds, setAwayOdds] = useState("");
  const [homeOdds, setHomeOdds] = useState("");
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [historyTeamFilter, setHistoryTeamFilter] = useState("");
  const [historyConfidenceFilter, setHistoryConfidenceFilter] = useState("");

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

  useEffect(() => {
    if (!backendOnline || (activePage !== "Live Games" && activePage !== "Dashboard")) return;
    void loadLiveGames(false);
    const timer = window.setInterval(() => void loadLiveGames(false), 30000);
    return () => window.clearInterval(timer);
  }, [activePage, backendOnline, selectedDate]);

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

      const summaryResponse = await fetch(`${API_URL}/dashboard-summary`);
      if (summaryResponse.ok) setDashboardSummary(await summaryResponse.json() as DashboardSummary);

      if (teamsPayload.teams.length >= 2) {
        setAwayTeam(teamsPayload.teams[0].name);
        setHomeTeam(teamsPayload.teams[1].name);
      }
    } catch {
      setBackendOnline(false);
      setError("Start the Strikers FastAPI backend to load live MLB data.");
    }
  }

  async function loadLiveGames(showLoader = true) {
    if (showLoader) setLoadingLive(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/live-games?date=${selectedDate}`);
      const payload = await response.json() as LiveGamesPayload & { detail?:string };
      if (!response.ok) throw new Error(payload.detail ?? "Live games failed.");
      setLiveGames(payload.games);
      setLiveUpdatedAt(payload.updated_at);
    } catch (requestError) {
      setError(errorMessage(requestError, "Could not load live games."));
    } finally {
      if (showLoader) setLoadingLive(false);
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

  async function runPrediction(away: string, home: string, game?: Game) {
    setAwayTeam(away);
    setHomeTeam(home);
    setError("");
    setLoadingPrediction(true);
    setActivePage("Matchup Predictor");

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ away_team: away, home_team: home, away_odds: awayOdds ? Number(awayOdds) : null, home_odds: homeOdds ? Number(homeOdds) : null, game_pk: game?.game_pk ?? null, official_date: game?.official_date ?? null }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Prediction failed.");
      setResult(payload as PredictionResponse);
      setHistory([]);
      const summaryResponse = await fetch(`${API_URL}/dashboard-summary`);
      if (summaryResponse.ok) setDashboardSummary(await summaryResponse.json() as DashboardSummary);
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

  async function loadPerformance(force = false) {
    setActivePage("Model Performance");
    if (performance && !force) return;
    setLoadingPerformance(true); setError("");
    try { const response = await fetch(`${API_URL}/model-performance?refresh=true`); const payload = await response.json(); if(!response.ok) throw new Error(payload.detail ?? "Performance failed."); setPerformance(payload as Performance); }
    catch(requestError){ setError(errorMessage(requestError,"Could not load model performance.")); } finally { setLoadingPerformance(false); }
  }

  async function loadWeather(force = false) {
    setActivePage("Weather Center");
    if (weatherGames.length && !force) return;
    setLoadingWeather(true); setError("");
    try { const response = await fetch(`${API_URL}/weather?date=${selectedDate}`); const payload = await response.json(); if(!response.ok) throw new Error(payload.detail ?? "Weather failed."); setWeatherGames(payload.games as WeatherGame[]); }
    catch(requestError){ setError(errorMessage(requestError,"Could not load weather intelligence.")); } finally { setLoadingWeather(false); }
  }


  async function loadModelLab(force = false) {
    setActivePage("Model Lab");
    if (modelLab && !force) return;
    setLoadingModelLab(true); setError("");
    try { const response = await fetch(`${API_URL}/model-lab`); const payload = await response.json(); if(!response.ok) throw new Error(payload.detail ?? "Model Lab failed."); setModelLab(payload as ModelLab); }
    catch(requestError){ setError(errorMessage(requestError,"Could not load Model Lab.")); } finally { setLoadingModelLab(false); }
  }

  async function loadHistory(force = false) {
    setActivePage("Prediction History");
    if (history.length > 0 && !force) return;
    setLoadingHistory(true);
    setError("");

    try {
      const params = new URLSearchParams({ limit: "100" });
      if (historyTeamFilter.trim()) params.set("team", historyTeamFilter.trim());
      if (historyConfidenceFilter) params.set("confidence", historyConfidenceFilter);
      const response = await fetch(`${API_URL}/prediction-history?${params.toString()}`);
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
    if (page === "Live Games") { setActivePage("Live Games"); void loadLiveGames(); }
    else if (page === "Best Bets") void loadBestBets();
    else if (page === "Player Props") void loadPlayerProps();
    else if (page === "Power Rankings") void loadRankings();
    else if (page === "Model Performance") void loadPerformance();
    else if (page === "Weather Center") void loadWeather();
    else if (page === "Model Lab") void loadModelLab();
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
            <span className="season-badge">Strikers v3.5</span>
            <div className={`api-indicator ${backendOnline ? "online" : ""}`}><span />API</div>
            <button className="profile-button" type="button">JH</button>
          </div>
        </header>

        {error && <div className="error-banner"><span>{error}</span><button type="button" aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}
        {activePage === "Dashboard" && renderDashboard()}
        {activePage === "Live Games" && renderLiveGames()}
        {activePage === "Matchup Predictor" && renderPredictor()}
        {activePage === "Best Bets" && renderBestBets()}
        {activePage === "Player Props" && renderPlayerProps()}
        {activePage === "Power Rankings" && renderRankings()}
        {activePage === "Model Performance" && renderPerformance()}
        {activePage === "Weather Center" && renderWeather()}
        {activePage === "Model Lab" && renderModelLab()}
        {activePage === "Prediction History" && renderHistory()}
        {activePage === "Team Analytics" && renderTeamAnalytics()}
      </main>
    </div>
  );

  function renderLiveGames() {
    const filtered = liveGames.filter((game) => {
      if (liveFilter === "All") return true;
      if (liveFilter === "Live") return game.status.abstract === "Live";
      if (liveFilter === "Final") return game.status.abstract === "Final";
      return game.status.abstract === "Preview";
    });
    const liveCount = liveGames.filter(game => game.status.abstract === "Live").length;
    const finalCount = liveGames.filter(game => game.status.abstract === "Final").length;
    return <>
      <section className="section-heading bets-heading live-heading"><div><p className="eyebrow">REAL-TIME MLB CENTER</p><h3>Live Games Dashboard</h3><p>Scores, innings, base state, active matchup, and your saved Strikers pick. Refreshes every 30 seconds.</p></div><div className="live-actions"><label className="date-control">Date<input type="date" value={selectedDate} onChange={(event)=>setSelectedDate(event.target.value)}/></label><button className="secondary-button" type="button" onClick={()=>void loadLiveGames(true)}>Refresh Now</button></div></section>
      <section className="stats-grid live-stats"><StatCard label="Live now" value={`${liveCount}`} note="Games in progress" positive={liveCount>0}/><StatCard label="Upcoming" value={`${liveGames.length-liveCount-finalCount}`} note="Scheduled today"/><StatCard label="Final" value={`${finalCount}`} note="Completed games"/><StatCard label="Last update" value={liveUpdatedAt ? formatTime(liveUpdatedAt) : "—"} note="Automatic 30-second refresh"/></section>
      <div className="live-filter-bar">{(["All","Live","Upcoming","Final"] as const).map(filter=><button key={filter} type="button" className={liveFilter===filter?"active":""} onClick={()=>setLiveFilter(filter)}>{filter}</button>)}</div>
      {loadingLive ? <LoadingCard text="Loading live MLB action…"/> : filtered.length===0 ? <EmptyState title="No games in this view" text="Try another filter or choose a different date."/> : <section className="live-game-grid">{filtered.map(game=><LiveGameCard key={game.game_pk} game={game} onPredict={()=>void runPrediction(game.away.name,game.home.name,game)}/>)}</section>}
    </>;
  }

  function renderDashboard() {
    return (
      <>
        <section className="hero-card">
          <div>
            <p className="eyebrow">LIVE MLB COMMAND CENTER</p>
            <h3>Today’s slate, powered by your model.</h3>
            <p>Browse games, probable pitchers, and launch the explainable Prediction Engine 7.0 with one click.</p>
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
          <StatCard label="Predictions" value={`${dashboardSummary?.database.total ?? 0}`} note={`${dashboardSummary?.database.pending ?? 0} awaiting results`} />
          <StatCard label="Accuracy" value={dashboardSummary?.database.graded ? `${dashboardSummary.database.accuracy.toFixed(1)}%` : "—"} note={`${dashboardSummary?.database.graded ?? 0} graded predictions`} positive={(dashboardSummary?.database.accuracy ?? 0) >= 55} />
          <StatCard label="ML Layer" value={dashboardSummary?.ml.available ? "Active" : "Collecting"} note={dashboardSummary?.ml.status ?? "Foundation ready"} positive={dashboardSummary?.ml.available ?? false} />
        </section>

        <section className="section-heading live-tracker-heading">
          <div><p className="eyebrow">LIVE GAME TRACKER</p><h3>Games in progress</h3><p>Live scores, inning state, runners, active matchup, and your saved Strikers prediction.</p></div>
          <button className="secondary-button" type="button" onClick={() => navigate("Live Games")}>Open Full Live Dashboard</button>
        </section>

        {loadingLive ? <LoadingCard text="Checking for live MLB games…" /> :
         liveGames.filter((game) => game.status.abstract === "Live").length === 0 ?
         <EmptyState title="No games are live right now" text="The tracker will update automatically every 30 seconds while you are on the dashboard." /> :
         <section className="live-game-grid dashboard-live-tracker">
           {liveGames.filter((game) => game.status.abstract === "Live").map((game) =>
             <LiveGameCard key={game.game_pk} game={game} onPredict={() => void runPrediction(game.away.name, game.home.name, game)} />
           )}
         </section>}

        <section className="section-heading">
          <div><p className="eyebrow">MLB SCHEDULE</p><h3>Game Center</h3></div>
          <span>{selectedDate}</span>
        </section>

        {loadingSchedule ? <LoadingCard text="Loading the MLB slate…" /> :
         games.length === 0 ? <EmptyState title="No MLB games scheduled" text="Choose another date to load a different slate." /> :
         <section className="game-grid">
           {games.map((game) => <GameCard game={game} key={game.game_pk} onPredict={() => void runPrediction(game.away.name, game.home.name, game)} />)}
         </section>}
      </>
    );
  }

  function renderPredictor() {
    return (
      <>
        <section className="predictor-header">
          <div><p className="eyebrow">PREDICTION ENGINE 7.0</p><h3>Matchup Predictor</h3><p>Choose any two teams or launch a game from the dashboard.</p></div>
          <div className={`connection-pill ${backendOnline ? "online" : ""}`}><span />{backendOnline ? "Backend connected" : "Backend offline"}</div>
        </section>

        <section className="matchup-builder panel">
          <TeamSelect label="Away team" value={awayTeam} teams={teams} onChange={setAwayTeam} />
          <div className="versus-orb">AT</div>
          <TeamSelect label="Home team" value={homeTeam} teams={teams} onChange={setHomeTeam} />
          <div className="moneyline-inputs"><label>Away odds<input type="number" placeholder="-110" value={awayOdds} onChange={(e)=>setAwayOdds(e.target.value)} /></label><label>Home odds<input type="number" placeholder="+120" value={homeOdds} onChange={(e)=>setHomeOdds(e.target.value)} /></label></div>
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
            <SportsbookIntelligence result={result} />
            <BettingIntelligence result={result} />
            <PredictionIntelligence result={result} />
            <article className="panel ml-opinion-card"><p className="eyebrow">ML SECOND OPINION</p><h3>{result.ml_second_opinion?.available ? result.ml_second_opinion.winner : "Collecting training data"}</h3><p>{result.ml_second_opinion?.available ? `${result.ml_second_opinion.agreement ? "Agrees" : "Disagrees"} with the core engine.` : (result.ml_second_opinion?.message ?? "The core engine remains fully active until enough completed predictions exist.")}</p></article>
            <TeamComparison result={result} />
            <PitcherComparison result={result} />
            <BullpenComparison result={result} />
            <LineupInjuryIntelligence result={result} />
            <GameAnalystPanel analyst={result.game_analyst} />
          </section>
        )}
      </>
    );
  }

  function renderBestBets() {
    return (
      <>
        <section className="section-heading bets-heading">
          <div><p className="eyebrow">SPORTSBOOK-RANKED DAILY SLATE</p><h3>Best Bets</h3><p>Matchups ranked by Bet Score, market edge, best available price, and model confidence.</p></div>
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
               <div className="best-bet-market">
                 <div><span>Bet Score</span><strong>{bet.bet_score === null ? "—" : `${bet.bet_score}/100`}</strong></div>
                 <div><span>Edge</span><strong>{bet.edge_points === null ? "—" : `${bet.edge_points >= 0 ? "+" : ""}${bet.edge_points.toFixed(1)} pts`}</strong></div>
                 <div><span>Best line</span><strong>{bet.best_odds === null ? "—" : `${bet.best_odds > 0 ? "+" : ""}${bet.best_odds}`}</strong><small>{bet.best_bookmaker ?? "Market unavailable"}</small></div>
                 <div><span>Action</span><strong>{bet.recommendation ?? "NO MARKET"}</strong></div>
               </div>
               <div className="bet-probability"><strong>{bet.probability.toFixed(1)}%</strong><span>model probability</span></div>
               <button className="secondary-button" type="button" onClick={() => void runPrediction(bet.game.away.name, bet.game.home.name, bet.game)}>Full Analysis</button>
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

  function renderPerformance() {
    const summary = performance?.summary;
    return <>
      <section className="section-heading bets-heading"><div><p className="eyebrow">MODEL ACCOUNTABILITY</p><h3>Model Performance</h3><p>Automatic result grading, confidence calibration, and flat-stake ROI.</p></div><button className="secondary-button" type="button" onClick={() => void loadPerformance(true)}>Grade & Refresh</button></section>
      {loadingPerformance ? <LoadingCard text="Grading predictions and calculating performance…" /> : !performance ? <EmptyState title="No performance data yet" text="Run predictions, then return after games become final." /> : <>
        <section className="stats-grid"><StatCard label="Accuracy" value={`${summary?.accuracy.toFixed(1)}%`} note={`${summary?.wins}-${summary?.losses} graded record`} positive={(summary?.accuracy ?? 0)>=55}/><StatCard label="Units" value={`${(summary?.units ?? 0)>=0?'+':''}${summary?.units.toFixed(2)}`} note="1 unit per pick at -110" positive={(summary?.units ?? 0)>=0}/><StatCard label="ROI" value={`${(summary?.roi ?? 0)>=0?'+':''}${summary?.roi.toFixed(1)}%`} note={`${summary?.graded_predictions} graded · ${summary?.pending_predictions} pending`} positive={(summary?.roi ?? 0)>=0}/><StatCard label="Current streak" value={`${summary?.current_streak ?? 0} ${(summary?.streak_type ?? '').toUpperCase()}`} note="Most recent graded picks" positive={summary?.streak_type==='win'}/></section>
        <section className="analytics-grid"><article className="panel"><p className="eyebrow">CONFIDENCE TIERS</p><h3>Accuracy by model confidence</h3><div className="metric-bars">{performance.confidence_tiers.map(row=><div className="metric-bar" key={row.tier}><div><strong>{row.tier}</strong><span>{row.wins}/{row.predictions} · {row.accuracy.toFixed(1)}%</span></div><div className="probability-track"><div className="probability-fill" style={{width:`${row.accuracy}%`}}/></div></div>)}</div></article>
        <article className="panel"><p className="eyebrow">CALIBRATION</p><h3>Expected vs. actual win rate</h3><div className="calibration-list">{performance.calibration.length ? performance.calibration.map(row=><div className="calibration-row" key={row.bucket}><strong>{row.bucket}</strong><span>Expected {row.expected.toFixed(1)}%</span><span>Actual {row.actual.toFixed(1)}%</span></div>) : <p className="muted">More graded predictions are needed.</p>}</div></article></section>
        <section className="panel"><p className="eyebrow">PERFORMANCE TREND</p><h3>Cumulative units by day</h3><div className="trend-list">{performance.trend.length ? performance.trend.map(row=><div className="trend-row" key={row.date}><span>{row.date}</span><strong className={row.cumulative_units>=0?'positive':'negative'}>{row.cumulative_units>=0?'+':''}{row.cumulative_units.toFixed(2)}u</strong><small>{row.accuracy.toFixed(0)}% on {row.predictions} picks</small></div>) : <p className="muted">Trend data appears after completed games are graded.</p>}</div></section>
      </>}
    </>;
  }

  function renderWeather() {
    return <><section className="section-heading bets-heading"><div><p className="eyebrow">LIVE SLATE CONDITIONS</p><h3>Weather Center</h3><p>Temperature, wind, precipitation risk, and run-environment context.</p></div><button className="secondary-button" type="button" onClick={() => void loadWeather(true)}>Refresh Forecasts</button></section>
    {loadingWeather ? <LoadingCard text="Loading ballpark forecasts…"/> : weatherGames.length===0 ? <EmptyState title="No weather games found" text="Choose a date with scheduled MLB games."/> : <section className="weather-grid">{weatherGames.map(game=><article className="panel weather-card" key={game.game_pk}><div className="weather-top"><div><span>{game.away.name} at {game.home.name}</span><h3>{game.venue ?? 'Venue TBD'}</h3></div><span className={`weather-impact impact-${game.weather.impact.toLowerCase().replace(' ','-')}`}>{game.weather.impact}</span></div>{game.weather.indoor ? <div className="indoor-weather">⌂ Climate controlled</div> : game.weather.available ? <div className="weather-metrics"><div><span>Temperature</span><strong>{game.weather.temperature_f}°F</strong></div><div><span>Wind</span><strong>{game.weather.wind_mph} mph</strong></div><div><span>Rain</span><strong>{game.weather.precipitation_probability}%</strong></div><div><span>Gusts</span><strong>{game.weather.gust_mph} mph</strong></div></div> : <p>Forecast unavailable.</p>}<p className="weather-summary">{game.weather.summary}</p><button className="secondary-button full-width" type="button" onClick={()=>void runPrediction(game.away.name,game.home.name,game)}>Analyze Matchup</button></article>)}</section>}</>;
  }


  function renderModelLab() {
    return <>
      <section className="section-heading bets-heading"><div><p className="eyebrow">MODEL TRANSPARENCY</p><h3>Model Lab</h3><p>See what drives Strikers, how it is performing, and where its limits are.</p></div><button className="secondary-button" type="button" onClick={() => void loadModelLab(true)}>Refresh Metrics</button></section>
      {loadingModelLab ? <LoadingCard text="Loading model architecture…" /> : !modelLab ? <EmptyState title="Model Lab unavailable" text="Start the backend and refresh this page." /> : <>
        <section className="stats-grid"><StatCard label="Engine" value="7.0" note={modelLab.architecture} positive/><StatCard label="Games evaluated" value={`${modelLab.games_evaluated}`} note={modelLab.calibration}/><StatCard label="Accuracy" value={`${modelLab.accuracy.toFixed(1)}%`} note="Automatically graded predictions" positive={modelLab.accuracy>=55}/><StatCard label="ROI" value={`${modelLab.roi>=0?'+':''}${modelLab.roi.toFixed(1)}%`} note={`${modelLab.units>=0?'+':''}${modelLab.units.toFixed(2)} units`} positive={modelLab.roi>=0}/></section>
        <section className="model-lab-grid"><article className="panel"><p className="eyebrow">CONFIGURED INFLUENCE</p><h3>Feature importance</h3><p className="muted">Transparent configured weights used by the explanation layer.</p><div className="feature-list">{modelLab.features.map(feature=><div className="feature-row" key={feature.name}><div><strong>{feature.name}</strong><span>{feature.description}</span></div><b>{feature.importance}%</b><div className="feature-track"><i style={{width:`${feature.importance*3.2}%`}}/></div></div>)}</div></article>
        <article className="panel"><p className="eyebrow">MODEL CARD</p><h3>{modelLab.status}</h3><div className="model-card-details"><div><span>Architecture</span><strong>{modelLab.architecture}</strong></div><div><span>Calibration</span><strong>{modelLab.calibration}</strong></div><div><span>Output</span><strong>Probabilities + factor reports</strong></div></div><p className="eyebrow model-limit-title">KNOWN LIMITATIONS</p><div className="limitation-list">{modelLab.limitations.map(item=><div key={item}><span>!</span><p>{item}</p></div>)}</div></article></section>
      </>}
    </>;
  }

  function renderHistory() {
    return (
      <>
        <section className="section-heading bets-heading">
          <div><p className="eyebrow">SAVED MODEL OUTPUT</p><h3>Prediction History</h3><p>Every manually generated prediction is stored automatically.</p></div>
          <div className="history-actions history-filter-bar"><input placeholder="Filter team" value={historyTeamFilter} onChange={(e)=>setHistoryTeamFilter(e.target.value)} /><select value={historyConfidenceFilter} onChange={(e)=>setHistoryConfidenceFilter(e.target.value)}><option value="">All confidence</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select><button className="secondary-button" type="button" onClick={() => { setHistory([]); void loadHistory(true); }}>Apply Filters</button>
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

function BaseDiamond({ bases }: { bases: LiveGame["bases"] }) {
  return <div className="base-diamond" aria-label={`Runners on ${Object.entries(bases).filter(([,v])=>v).map(([k])=>k).join(", ") || "no bases"}`}><span className={`base second ${bases.second?"occupied":""}`}/><span className={`base third ${bases.third?"occupied":""}`}/><span className={`base first ${bases.first?"occupied":""}`}/></div>;
}

function LiveGameCard({ game, onPredict }: { game:LiveGame; onPredict:()=>void }) {
  const live=game.status.abstract==="Live"; const final=game.status.abstract==="Final";
  const pick=game.prediction; const pickProbability=pick ? Math.max(pick.away_probability,pick.home_probability) : null;
  return <article className={`panel live-game-card ${live?"is-live":""}`}>
    <div className="live-card-header"><div><span className={`game-status ${live?"live":""}`}>{live?"● LIVE":game.status.detailed}</span><strong>{live||final?game.inning_label:formatTime(game.game_date)}</strong></div><span>{game.venue??"Venue TBD"}</span></div>
    <div className="live-scoreboard"><div className="live-team"><TeamLogo team={game.away}/><div><strong>{game.away.name}</strong><span>{game.away.probable_pitcher?.name??"Starter TBD"}</span></div><b>{game.away.score??0}</b></div><div className="live-team"><TeamLogo team={game.home}/><div><strong>{game.home.name}</strong><span>{game.home.probable_pitcher?.name??"Starter TBD"}</span></div><b>{game.home.score??0}</b></div></div>
    {live && <div className="live-situation"><BaseDiamond bases={game.bases}/><div className="count-box"><strong>{game.count.balls}-{game.count.strikes}</strong><span>{game.count.outs} out{game.count.outs===1?"":"s"}</span></div><div className="active-matchup"><span>At bat</span><strong>{game.current_batter??"Updating…"}</strong><span>Pitching: {game.current_pitcher??"Updating…"}</span></div></div>}
    <div className="live-model-box">{pick?<><div><span>Strikers pregame pick</span><strong>{pick.winner}</strong><small>{pickProbability?.toFixed(1)}% · {pick.confidence_stars} {pick.confidence}</small></div>{game.live_probability&&<div className="live-prob"><span>Live estimate</span><strong>{game.live_probability.home>=50?game.home.name:game.away.name} {Math.max(game.live_probability.home,game.live_probability.away).toFixed(1)}%</strong><small>{game.live_probability.method}</small></div>}</>:<div><span>No saved prediction</span><strong>Analyze this matchup</strong><small>Save a pregame pick to track it here.</small></div>}</div>
    <button className="secondary-button full-width" type="button" onClick={onPredict}>{pick?"Open Matchup Analysis":"Run Prediction"}</button>
  </article>;
}

function StatCard({ label, value, note, positive = false }: { label: string; value: string; note: string; positive?: boolean }) {
  return <article className="stat-card"><span>{label}</span><strong className={positive ? "positive" : ""}>{value}</strong><small>{note}</small></article>;
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  return <div className="probability-row"><div><strong>{label}</strong><span>{value.toFixed(1)}%</span></div><div className="probability-track"><div className="probability-fill" style={{ width: `${value}%` }} /></div></div>;
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

function LineupInjuryIntelligence({ result }: { result: PredictionResponse }) {
  const sides:[string,LineupSide,InjurySide][] = [
    [result.matchup.away,result.lineup_intelligence.away,result.injury_intelligence.away],
    [result.matchup.home,result.lineup_intelligence.home,result.injury_intelligence.home],
  ];
  return <article className="panel lineup-injury-card"><div className="li-head"><div><p className="eyebrow">LINEUP & INJURY INTELLIGENCE v3.4</p><h3>Who is actually available tonight?</h3></div><span className="li-adjustment">Model shift {result.prediction_adjustments.total_adjustment>=0?'+':''}{result.prediction_adjustments.total_adjustment.toFixed(1)} pts toward away</span></div><div className="li-grid">{sides.map(([team,lineup,injuries])=><section className="li-team" key={team}><div className="li-team-title"><div><span>{team}</span><h4>{lineup.status}</h4></div><strong>{Math.round(lineup.strength_score)}<small>/100</small></strong></div><div className="li-meter"><i style={{width:`${lineup.strength_score}%`}} /></div><p className="li-note">{lineup.note}</p>{lineup.batting_order.length>0&&<details><summary>Batting order</summary><div className="batting-order">{lineup.batting_order.map((player,index)=><div key={player.player_id}><b>{index+1}</b><span>{player.name}<small>{player.position}{player.ops!=null?` · ${player.ops.toFixed(3)} OPS`:''}</small></span></div>)}</div></details>}<div className="injury-summary"><span>Official IL</span><strong>{injuries.count} player{injuries.count===1?'':'s'}</strong><small>{injuries.penalty_points.toFixed(1)} model-penalty points</small></div>{injuries.players.length>0?<div className="injury-list">{injuries.players.slice(0,8).map(player=><div key={`${team}-${player.player_id}`}><span><strong>{player.name}</strong><small>{player.position} · {player.status}</small></span><b>{player.impact}</b></div>)}</div>:<p className="li-note">No official injured-list entries returned by MLB.</p>}</section>)}</div><p className="li-disclaimer">{result.injury_intelligence.note}</p></article>;
}

function GameAnalystPanel({ analyst }: { analyst: GameAnalyst }) {
  return <article className="panel game-analyst-card"><div className="analyst-hero"><div><p className="eyebrow">AI GAME ANALYST</p><h3>{analyst.pick} · {analyst.win_probability.toFixed(1)}%</h3><strong>{analyst.verdict}</strong></div><span>Grounded in Strikers model inputs</span></div><p className="analyst-summary">{analyst.summary}</p><div className="analyst-columns"><section><h4>Why the model leans this way</h4>{analyst.key_reasons.map(reason=><div className="analyst-point positive-point" key={reason}><span>✓</span><p>{reason}</p></div>)}</section><section><h4>Biggest risks</h4>{analyst.biggest_risks.map(risk=><div className="analyst-point risk-point" key={risk}><span>!</span><p>{risk}</p></div>)}</section></div><div className="analyst-adjustments"><span>Lineup {analyst.model_adjustment.lineup_adjustment>=0?'+':''}{analyst.model_adjustment.lineup_adjustment.toFixed(1)}</span><span>Injuries {analyst.model_adjustment.injury_adjustment>=0?'+':''}{analyst.model_adjustment.injury_adjustment.toFixed(1)}</span><span>Total {analyst.model_adjustment.total_adjustment>=0?'+':''}{analyst.model_adjustment.total_adjustment.toFixed(1)}</span></div><small className="analyst-disclaimer">{analyst.disclaimer}</small></article>;
}
function BullpenComparison({ result }: { result: PredictionResponse }) {
  return <article className="panel bullpen-card"><p className="eyebrow">BULLPEN INTELLIGENCE v3.3</p><h3>Relief availability</h3><p className="bullpen-subtitle">Workload from the previous three calendar days. Higher availability is better.</p><div className="bullpen-grid"><BullpenPanel bullpen={result.away_bullpen} /><span className="pitcher-vs">VS</span><BullpenPanel bullpen={result.home_bullpen} /></div></article>;
}

function BullpenPanel({ bullpen }: { bullpen: Bullpen }) {
  const score = Math.round(bullpen.availability_score ?? 75);
  return <div className="bullpen-panel"><div className="bullpen-title"><div><span>{bullpen.team_name}</span><h4>{bullpen.fatigue_level}</h4></div><strong className={`bullpen-score fatigue-${bullpen.fatigue_level.toLowerCase()}`}>{score}</strong></div><div className="bullpen-track"><i style={{width:`${score}%`}} /></div><div className="bullpen-metrics"><div><span>3-day pitches</span><strong>{bullpen.total_pitches_3d}</strong></div><div><span>Relievers used</span><strong>{bullpen.relievers_used_3d}</strong></div><div><span>Limited</span><strong>{bullpen.overworked_relievers}</strong></div><div><span>Unavailable</span><strong>{bullpen.unavailable_relievers}</strong></div></div>{bullpen.season_era != null && <div className="bullpen-quality"><span>Bullpen ERA <strong>{bullpen.season_era.toFixed(2)}</strong></span>{bullpen.season_whip != null && <span>WHIP <strong>{bullpen.season_whip.toFixed(2)}</strong></span>}</div>}<details className="reliever-details"><summary>Reliever workload</summary>{bullpen.relievers.length ? bullpen.relievers.map((reliever)=><div className="reliever-row" key={reliever.player_id}><div><strong>{reliever.name}</strong><span>{reliever.appearances} appearance{reliever.appearances === 1 ? "" : "s"}</span></div><b>{reliever.pitches} pitches</b><em>{reliever.status}</em></div>) : <p>No recent relief appearances found.</p>}</details></div>;
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
