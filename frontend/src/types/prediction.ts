export type Pitcher = {
  id: number | null;
  name: string;
  available: boolean;
  era: number | null;
  whip: number | null;
  innings: number | null;
};

export type LineupPlayer = {
  player_id: number;
  name: string;
  position: string;
  ops: number | null;
};

export type LineupSide = {
  status: string;
  confirmed: boolean;
  strength_score: number;
  average_ops: number | null;
  batting_order: LineupPlayer[];
  note: string;
};

export type InjuryPlayer = {
  player_id: number | null;
  name: string;
  position: string;
  status: string;
  impact: string;
};

export type InjurySide = {
  players: InjuryPlayer[];
  count: number;
  penalty_points: number;
};

export type GameAnalyst = {
  title: string;
  pick: string;
  win_probability: number;
  verdict: string;
  summary: string;
  key_reasons: string[];
  biggest_risks: string[];
  lineup_status: string;
  model_adjustment: {
    lineup_adjustment: number;
    injury_adjustment: number;
    total_adjustment: number;
  };
  disclaimer: string;
};

export type Bullpen = {
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
  relievers: {
    player_id: number;
    name: string;
    pitches: number;
    appearances: number;
    used_yesterday: boolean;
    used_back_to_back: boolean;
    status: string;
  }[];
};

export type SportsbookSide = {
  team: string;
  side: string;
  model_probability: number;
  market_probability: number | null;
  consensus_implied_probability: number | null;
  edge_points: number | null;
  best_odds: number | null;
  best_bookmaker: string | null;
  best_link: string | null;
  expected_value: number | null;
  bet_score: number;
  value_label: string;
  recommendation: string;
  recommendation_detail: string;
  market_depth: number;
  reasons: string[];
};

export type StatcastMetrics = {
  xwoba?: number | null;
  xslg?: number | null;
  barrel_pct?: number | null;
  hard_hit_pct?: number | null;
  xera?: number | null;
  [key: string]: number | string | boolean | null | undefined;
};

export type StatcastSide = {
  lineup: { metrics: StatcastMetrics };
  starter: { metrics: StatcastMetrics };
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
  lineup_intelligence: {
    game_pk: number | null;
    away: LineupSide;
    home: LineupSide;
    available: boolean;
  };
  injury_intelligence: {
    away: InjurySide;
    home: InjurySide;
    available: boolean;
    note: string;
  };
  prediction_adjustments: {
    lineup_adjustment: number;
    injury_adjustment: number;
    total_adjustment: number;
  };
  game_analyst: GameAnalyst;
  statcast_intelligence?: {
    available: boolean;
    data_quality_score: number;
    away: StatcastSide;
    home: StatcastSide;
    note?: string;
  };
  statcast_adjustment?: {
    applied: boolean;
    points: number;
    favored_team?: string | null;
    status?: string;
  };
  betting_intelligence?: {
    market: string;
    status: string;
    disclaimer: string;
    staking_method: string;
    unit_definition: string;
    best_value: null | {
      team: string;
      odds: number | null;
      quality_score: number;
      expected_value: number | null;
      suggested_units: number;
    };
    sides: {
      team: string;
      model_probability: number;
      odds: number | null;
      implied_probability: number | null;
      edge_points: number | null;
      fair_odds: number;
      expected_value: number | null;
      rating: string;
      recommendation: string;
      quality_score: number | null;
      kelly_fraction: number | null;
      suggested_units: number | null;
    }[];
  };
  sportsbook_intelligence?: {
    available: boolean;
    status: string;
    message: string;
    provider: string;
    event_id?: string;
    commence_time?: string;
    last_update?: string;
    best_value: null | SportsbookSide;
    sides: SportsbookSide[];
    bookmakers: {
      key: string;
      name: string;
      last_update: string | null;
      link: string | null;
      away_odds: number | null;
      home_odds: number | null;
    }[];
    spreads: {
      bookmaker: string;
      team: string;
      point: number | null;
      odds: number | null;
      last_update: string | null;
    }[];
    totals: {
      bookmaker: string;
      side: string;
      point: number | null;
      odds: number | null;
      last_update: string | null;
    }[];
    quota: Record<string, string | number | boolean | null>;
    disclaimer: string;
  };
  ml_second_opinion?: {
    available: boolean;
    status: string;
    winner: string | null;
    home_probability: number | null;
    away_probability: number | null;
    agreement: boolean | null;
    message?: string;
  };
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
    factors: {
      name: string;
      home_points: number;
      away_points: number;
      favored_team: string;
      strength: number;
      detail: string;
      available: boolean;
    }[];
    prediction_dna?: {
      winner: string;
      alignment: number;
      conflict: number;
      conviction: number;
      balance_label: string;
      dominant_driver: string;
      counterweight: string;
      summary: string;
      components: {
        name: string;
        favored_team: string;
        strength: number;
        share: number;
        role: "support" | "risk" | "neutral";
        impact: string;
        detail: string;
      }[];
      flip_conditions: string[];
    };
    risk: {
      level: string;
      volatility: number;
      upset_chance: number;
      confidence: number;
    };
  };
};
