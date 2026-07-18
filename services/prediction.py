"""
Strikers Prediction Engine 4.0

This module provides an object-oriented MLB matchup prediction engine.
It combines team performance, offense, pitching, home/away records,
home-field advantage, and probable starting-pitcher statistics.

The public ``predict_matchup()`` function is kept for compatibility with
older versions of app.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import tanh
from typing import Any

from api.mlb_api import (
    find_team,
    get_pitcher_stats,
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
    get_team_recent_form,
    get_today_schedule,
)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert an MLB API value to float without crashing."""

    if value is None:
        return default

    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Convert an MLB API value to int without crashing."""

    if value is None:
        return default

    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def innings_to_float(value: Any) -> float:
    """
    Convert baseball innings notation into a comparable number.

    Example:
        120.1 means 120 innings and one out, not 120.10 innings.
    """

    text = str(value or "0.0").strip()

    try:
        whole_text, outs_text = text.split(".", maxsplit=1)
        whole = int(whole_text)
        outs = int(outs_text[:1] or 0)

        if outs not in (0, 1, 2):
            return safe_float(value)

        return whole + (outs / 3)
    except (ValueError, TypeError):
        return safe_float(value)


def percentage_from_record(record: dict[str, Any] | None) -> float:
    """Return a winning percentage from an MLB standings record."""

    if not record:
        return 0.5

    direct_value = record.get("winningPercentage")

    if direct_value is not None:
        return safe_float(direct_value, 0.5)

    wins = safe_int(record.get("wins"))
    losses = safe_int(record.get("losses"))
    games = wins + losses

    return wins / games if games else 0.5


def runs_per_game(stats: dict[str, Any] | None) -> float:
    """Calculate runs scored per game from team hitting statistics."""

    if not stats:
        return 0.0

    games = safe_float(stats.get("gamesPlayed"))
    runs = safe_float(stats.get("runs"))

    return runs / games if games else 0.0


def display_number(value: Any, decimals: int = 3, fallback: str = "N/A") -> str:
    """Format a numeric value for terminal output."""

    if value is None or value == "":
        return fallback

    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


@dataclass
class TeamData:
    """All team information required by the model."""

    team_id: int
    name: str
    record: dict[str, Any]
    hitting: dict[str, Any]
    pitching: dict[str, Any]
    win_pct: float
    location_win_pct: float
    ops: float
    runs_per_game: float
    era: float
    whip: float
    recent_games: int
    recent_wins: int
    recent_losses: int
    recent_win_pct: float
    recent_runs_per_game: float
    recent_runs_allowed_per_game: float
    recent_run_differential_per_game: float


@dataclass
class PitcherData:
    """Probable starting-pitcher information."""

    player_id: int | None = None
    name: str = "Not announced"
    stats: dict[str, Any] = field(default_factory=dict)
    era: float = 0.0
    whip: float = 0.0
    innings: float = 0.0
    strikeouts: int = 0
    walks: int = 0
    opponent_average: float = 0.0
    available: bool = False


@dataclass
class ModelResult:
    """Final prediction values and explanation."""

    away_probability: float
    home_probability: float
    winner: str
    confidence: str
    confidence_stars: str
    away_score: float
    home_score: float
    reasons: list[str]


class PredictionEngine:
    """Create and display a pitcher-aware MLB matchup prediction."""

    TEAM_WEIGHT = 70.0
    PITCHER_WEIGHT = 25.0
    HOME_FIELD_POINTS = 5.0
    MAX_PROBABILITY = 80.0
    PROBABILITY_SHRINK = 0.85

    def __init__(self) -> None:
        self.away_team: dict[str, Any] | None = None
        self.home_team: dict[str, Any] | None = None
        self.away_data: TeamData | None = None
        self.home_data: TeamData | None = None
        self.away_pitcher = PitcherData()
        self.home_pitcher = PitcherData()
        self.factor_edges: list[tuple[str, str]] = []

    def run(self) -> None:
        """Prompt for teams, run the model, and print a report."""

        self.print_header()

        away_search = input("\nAway team: ").strip()
        home_search = input("Home team: ").strip()

        if not away_search or not home_search:
            print("\nBoth team names are required.")
            return

        print("\nLoading matchup information...")

        try:
            if not self.load_matchup(away_search, home_search):
                return

            self.load_team_data()
            self.load_probable_pitchers()
            result = self.generate_prediction()
            self.display_report(result)

        except (ConnectionError, RuntimeError) as error:
            print(f"\nPrediction could not be completed: {error}")
        except Exception as error:
            print(f"\nUnexpected prediction error: {error}")

    def predict_silent(
        self,
        away_search: str,
        home_search: str,
    ) -> ModelResult:
        """
        Generate a prediction without prompts, reports, or history saving.

        This mode is used by automated features such as Best Bets of
        the Day.
        """

        away_search = away_search.strip()
        home_search = home_search.strip()

        if not away_search or not home_search:
            raise ValueError("Both team names are required.")

        self.away_team = None
        self.home_team = None
        self.away_data = None
        self.home_data = None
        self.away_pitcher = PitcherData()
        self.home_pitcher = PitcherData()
        self.factor_edges = []

        self.away_team = find_team(away_search)
        self.home_team = find_team(home_search)

        if not self.away_team:
            raise ValueError(f"Away team not found: {away_search}")

        if not self.home_team:
            raise ValueError(f"Home team not found: {home_search}")

        if self.away_team.get("id") == self.home_team.get("id"):
            raise ValueError(
                "The matchup must contain two different teams."
            )

        self.load_team_data()
        self.load_probable_pitchers()

        return self.generate_prediction()
    @staticmethod
    def print_header() -> None:
        """Display the Prediction Engine heading."""

        print("\n" + "=" * 62)
        print("STRIKERS PREDICTION ENGINE 4.0".center(62))
        print("=" * 62)

    def load_matchup(self, away_search: str, home_search: str) -> bool:
        """Resolve user-entered team names through the MLB API."""

        self.away_team = find_team(away_search)
        self.home_team = find_team(home_search)

        if not self.away_team:
            print(f"\nAway team not found: {away_search}")
            return False

        if not self.home_team:
            print(f"\nHome team not found: {home_search}")
            return False

        if self.away_team.get("id") == self.home_team.get("id"):
            print("\nPlease select two different teams.")
            return False

        return True

    def load_team_data(self) -> None:
        """Download and normalize team statistics."""

        assert self.away_team is not None
        assert self.home_team is not None

        self.away_data = self.build_team_data(self.away_team, "away")
        self.home_data = self.build_team_data(self.home_team, "home")

    def build_team_data(
        self,
        team: dict[str, Any],
        location: str,
    ) -> TeamData:
        """Build a TeamData object for one club."""

        team_id = safe_int(team.get("id"))
        record = get_team_record(team_id) or {}
        hitting = get_team_hitting_stats(team_id) or {}
        pitching = get_team_pitching_stats(team_id) or {}
        recent_form = get_team_recent_form(team_id, games=10) or {}

        location_record = record.get("records", {}).get("splitRecords", [])
        location_win_pct = self.find_location_percentage(
            location_record,
            location,
        )

        return TeamData(
            team_id=team_id,
            name=team.get("name", "Unknown Team"),
            record=record,
            hitting=hitting,
            pitching=pitching,
            win_pct=percentage_from_record(record),
            location_win_pct=location_win_pct,
            ops=safe_float(hitting.get("ops")),
            runs_per_game=runs_per_game(hitting),
            era=safe_float(pitching.get("era")),
            whip=safe_float(pitching.get("whip")),
            recent_games=safe_int(recent_form.get("games_played")),
            recent_wins=safe_int(recent_form.get("wins")),
            recent_losses=safe_int(recent_form.get("losses")),
            recent_win_pct=safe_float(recent_form.get("win_pct"), 0.5),
            recent_runs_per_game=safe_float(recent_form.get("runs_per_game")),
            recent_runs_allowed_per_game=safe_float(recent_form.get("runs_allowed_per_game")),
            recent_run_differential_per_game=safe_float(recent_form.get("run_differential_per_game")),
        )

    @staticmethod
    def find_location_percentage(
        split_records: list[dict[str, Any]],
        location: str,
    ) -> float:
        """Find a team's home or away winning percentage."""

        target = location.lower()

        for split in split_records:
            split_type = str(split.get("type", "")).lower()

            if target in split_type:
                return percentage_from_record(split)

        return 0.5

    def load_probable_pitchers(self) -> None:
        """Locate today's game and load both probable starters."""

        assert self.away_data is not None
        assert self.home_data is not None

        schedule = get_today_schedule()
        matching_game = self.find_scheduled_game(
            schedule,
            self.away_data.team_id,
            self.home_data.team_id,
        )

        if not matching_game:
            return

        teams = matching_game.get("teams", {})

        away_info = teams.get("away", {}).get("probablePitcher", {})
        home_info = teams.get("home", {}).get("probablePitcher", {})

        self.away_pitcher = self.build_pitcher_data(away_info)
        self.home_pitcher = self.build_pitcher_data(home_info)

    @staticmethod
    def find_scheduled_game(
        schedule: dict[str, Any],
        away_team_id: int,
        home_team_id: int,
    ) -> dict[str, Any] | None:
        """Find today's matching away-at-home game."""

        for date_group in schedule.get("dates", []):
            for game in date_group.get("games", []):
                teams = game.get("teams", {})
                game_away_id = (
                    teams.get("away", {}).get("team", {}).get("id")
                )
                game_home_id = (
                    teams.get("home", {}).get("team", {}).get("id")
                )

                if (
                    game_away_id == away_team_id
                    and game_home_id == home_team_id
                ):
                    return game

        return None

    @staticmethod
    def build_pitcher_data(info: dict[str, Any]) -> PitcherData:
        """Build normalized pitcher data from schedule information."""

        player_id = info.get("id")
        name = info.get("fullName", "Not announced")

        if not player_id:
            return PitcherData(name=name)

        stats = get_pitcher_stats(safe_int(player_id)) or {}

        return PitcherData(
            player_id=safe_int(player_id),
            name=name,
            stats=stats,
            era=safe_float(stats.get("era")),
            whip=safe_float(stats.get("whip")),
            innings=innings_to_float(stats.get("inningsPitched")),
            strikeouts=safe_int(stats.get("strikeOuts")),
            walks=safe_int(stats.get("baseOnBalls")),
            opponent_average=safe_float(stats.get("avg")),
            available=bool(stats),
        )

    def generate_prediction(self) -> ModelResult:
        """Score the matchup and produce calibrated win probabilities."""

        assert self.away_data is not None
        assert self.home_data is not None

        away_score = 0.0
        home_score = self.HOME_FIELD_POINTS
        self.factor_edges = []

        team_factors = [
            ("Season record", self.away_data.win_pct, self.home_data.win_pct, 10.0, True, 0.120),
            ("Home/away performance", self.away_data.location_win_pct, self.home_data.location_win_pct, 7.0, True, 0.150),
            ("OPS", self.away_data.ops, self.home_data.ops, 12.0, True, 0.100),
            ("Runs per game", self.away_data.runs_per_game, self.home_data.runs_per_game, 10.0, True, 1.50),
            ("Team ERA", self.away_data.era, self.home_data.era, 8.0, False, 1.50),
            ("Team WHIP", self.away_data.whip, self.home_data.whip, 5.0, False, 0.35),
            ("Recent record", self.away_data.recent_win_pct, self.home_data.recent_win_pct, 8.0, True, 0.250),
            ("Recent run differential", self.away_data.recent_run_differential_per_game, self.home_data.recent_run_differential_per_game, 10.0, True, 3.00),
        ]

        for label, away_value, home_value, points, higher_is_better, scale in team_factors:
            away_points, home_points = self.award_factor(
                label, away_value, home_value, points, higher_is_better, scale
            )
            away_score += away_points
            home_score += home_points

        pitcher_away, pitcher_home = self.score_pitchers()
        away_score += pitcher_away
        home_score += pitcher_home
        self.factor_edges.append(("Home-field advantage", self.home_data.name))

        total = away_score + home_score
        raw_away_probability = 50.0 if total <= 0 else (away_score / total) * 100

        reliability = self.PROBABILITY_SHRINK
        if not self.away_pitcher.available and not self.home_pitcher.available:
            reliability *= 0.85
        elif not self.away_pitcher.available or not self.home_pitcher.available:
            reliability *= 0.92

        if min(self.away_data.recent_games, self.home_data.recent_games) < 5:
            reliability *= 0.92

        away_probability = 50.0 + ((raw_away_probability - 50.0) * reliability)
        away_probability = max(100.0 - self.MAX_PROBABILITY, min(self.MAX_PROBABILITY, away_probability))
        home_probability = 100.0 - away_probability

        if away_probability >= home_probability:
            winner = self.away_data.name
            winning_probability = away_probability
        else:
            winner = self.home_data.name
            winning_probability = home_probability

        confidence, stars = self.calculate_confidence(winning_probability)
        reasons = self.build_reasons(winner)

        return ModelResult(
            away_probability=away_probability,
            home_probability=home_probability,
            winner=winner,
            confidence=confidence,
            confidence_stars=stars,
            away_score=away_score,
            home_score=home_score,
            reasons=reasons,
        )

    def award_factor(
        self,
        label: str,
        away_value: float,
        home_value: float,
        points: float,
        higher_is_better: bool,
        scale: float,
    ) -> tuple[float, float]:
        """Split points according to the size of the statistical edge."""

        assert self.away_data is not None
        assert self.home_data is not None

        if scale <= 0:
            raise ValueError("Factor scale must be greater than zero.")

        if away_value <= 0 and home_value <= 0:
            return points / 2, points / 2

        difference = away_value - home_value
        if not higher_is_better:
            difference *= -1

        edge_strength = tanh(difference / scale)
        away_points = points * (0.5 + (0.5 * edge_strength))
        home_points = points - away_points

        if abs(edge_strength) >= 0.08:
            better_team = self.away_data.name if edge_strength > 0 else self.home_data.name
            self.factor_edges.append((label, better_team))

        return away_points, home_points

    def score_pitchers(self) -> tuple[float, float]:
        """Score the probable starting-pitcher matchup."""

        assert self.away_data is not None
        assert self.home_data is not None

        total_points = self.PITCHER_WEIGHT

        if not self.away_pitcher.available and not self.home_pitcher.available:
            return total_points / 2, total_points / 2

        if self.away_pitcher.available and not self.home_pitcher.available:
            self.factor_edges.append(("Confirmed starting pitcher", self.away_data.name))
            return total_points * 0.58, total_points * 0.42

        if self.home_pitcher.available and not self.away_pitcher.available:
            self.factor_edges.append(("Confirmed starting pitcher", self.home_data.name))
            return total_points * 0.42, total_points * 0.58

        away_score = 0.0
        home_score = 0.0
        pitcher_factors = [
            ("Starter ERA", self.away_pitcher.era, self.home_pitcher.era, 10.0, False, 2.00),
            ("Starter WHIP", self.away_pitcher.whip, self.home_pitcher.whip, 6.0, False, 0.40),
            ("Starter strikeout rate", self.pitcher_rate(self.away_pitcher.strikeouts, self.away_pitcher.innings), self.pitcher_rate(self.home_pitcher.strikeouts, self.home_pitcher.innings), 4.0, True, 3.00),
            ("Starter walk rate", self.pitcher_rate(self.away_pitcher.walks, self.away_pitcher.innings), self.pitcher_rate(self.home_pitcher.walks, self.home_pitcher.innings), 3.0, False, 1.50),
            ("Starter opponent average", self.away_pitcher.opponent_average, self.home_pitcher.opponent_average, 2.0, False, 0.080),
        ]

        for label, away_value, home_value, points, higher_is_better, scale in pitcher_factors:
            away_points, home_points = self.award_factor(
                label, away_value, home_value, points, higher_is_better, scale
            )
            away_score += away_points
            home_score += home_points

        away_reliability = min(self.away_pitcher.innings / 40.0, 1.0)
        home_reliability = min(self.home_pitcher.innings / 40.0, 1.0)
        combined_reliability = (away_reliability + home_reliability) / 2
        neutral_share = total_points * (1 - combined_reliability) / 2
        away_score = (away_score * combined_reliability) + neutral_share
        home_score = (home_score * combined_reliability) + neutral_share
        return away_score, home_score

    @staticmethod
    def pitcher_rate(total: int, innings: float) -> float:
        """Calculate a per-nine-innings pitcher rate."""

        return (total / innings) * 9 if innings else 0.0

    @staticmethod
    def calculate_confidence(probability: float) -> tuple[str, str]:
        """Convert a calibrated win probability into a confidence label."""

        if probability >= 76:
            return "ELITE", "★★★★★"
        if probability >= 70:
            return "VERY HIGH", "★★★★★"
        if probability >= 65:
            return "HIGH", "★★★★☆"
        if probability >= 60:
            return "MEDIUM-HIGH", "★★★★☆"
        if probability >= 55:
            return "MEDIUM", "★★★☆☆"
        if probability >= 52:
            return "LOW", "★★☆☆☆"
        return "VERY LOW", "★☆☆☆☆"

    def build_reasons(self, winner: str) -> list[str]:
        """Create a concise list of factors favoring the predicted winner."""

        reasons = [
            label
            for label, team_name in self.factor_edges
            if team_name == winner
        ]

        # Avoid overwhelming the terminal report.
        return reasons[:6]

    def display_report(self, result: ModelResult) -> None:
        """Print the complete prediction report."""

        assert self.away_data is not None
        assert self.home_data is not None

        print("\n" + "=" * 62)
        print(f"{self.away_data.name} @ {self.home_data.name}".center(62))
        print("=" * 62)

        print("\nTEAM ANALYSIS")
        print("-" * 62)
        self.print_stat_row(
            "Winning percentage",
            self.away_data.win_pct,
            self.home_data.win_pct,
            3,
        )
        self.print_stat_row(
            "Location win percentage",
            self.away_data.location_win_pct,
            self.home_data.location_win_pct,
            3,
        )
        self.print_stat_row(
            "OPS",
            self.away_data.ops,
            self.home_data.ops,
            3,
        )
        self.print_stat_row(
            "Runs/game",
            self.away_data.runs_per_game,
            self.home_data.runs_per_game,
            2,
        )
        self.print_stat_row(
            "Team ERA",
            self.away_data.era,
            self.home_data.era,
            2,
        )
        self.print_stat_row(
            "Team WHIP",
            self.away_data.whip,
            self.home_data.whip,
            2,
        )

        print("\nRECENT FORM")
        print("-" * 62)
        print(
            f"{'Last 10 record':<25}"
            f"{self.away_data.recent_wins:>5}-{self.away_data.recent_losses:<6}"
            f"{self.home_data.recent_wins:>5}-{self.home_data.recent_losses:<6}"
        )
        self.print_stat_row("Recent win percentage", self.away_data.recent_win_pct, self.home_data.recent_win_pct, 3)
        self.print_stat_row("Recent runs/game", self.away_data.recent_runs_per_game, self.home_data.recent_runs_per_game, 2)
        self.print_stat_row("Recent runs allowed/game", self.away_data.recent_runs_allowed_per_game, self.home_data.recent_runs_allowed_per_game, 2)
        self.print_stat_row("Recent run diff/game", self.away_data.recent_run_differential_per_game, self.home_data.recent_run_differential_per_game, 2)

        print("\nPROBABLE STARTING PITCHERS")
        print("-" * 62)
        self.display_pitcher(self.away_data.name, self.away_pitcher)
        print()
        self.display_pitcher(self.home_data.name, self.home_pitcher)

        print("\nMODEL RESULTS")
        print("-" * 62)
        print(
            f"{self.away_data.name:<36}"
            f"{result.away_probability:>8.1f}%"
        )
        print(
            f"{self.home_data.name:<36}"
            f"{result.home_probability:>8.1f}%"
        )
        print()
        print(f"Predicted winner: {result.winner}")
        print(f"Confidence:       {result.confidence}")
        print(f"Rating:           {result.confidence_stars}")

        print("\nWHY THE MODEL LEANS THIS WAY")
        print("-" * 62)

        if result.reasons:
            for reason in result.reasons:
                print(f"✓ {reason}")
        else:
            print("The matchup is nearly even across the available factors.")

        print("\n" + "=" * 62)
        print(
            "Model probabilities are estimates, not guarantees."
        )
        print("=" * 62)

    def print_stat_row(
        self,
        label: str,
        away_value: float,
        home_value: float,
        decimals: int,
    ) -> None:
        """Print one side-by-side team-stat row."""

        assert self.away_data is not None
        assert self.home_data is not None

        away_text = display_number(away_value, decimals)
        home_text = display_number(home_value, decimals)

        print(
            f"{label:<25}"
            f"{away_text:>12}"
            f"{home_text:>12}"
        )

    @staticmethod
    def display_pitcher(team_name: str, pitcher: PitcherData) -> None:
        """Print one probable starter's information."""

        print(f"{team_name}: {pitcher.name}")

        if not pitcher.available:
            print("  Statistics unavailable")
            return

        print(f"  ERA:  {display_number(pitcher.era, 2)}")
        print(f"  WHIP: {display_number(pitcher.whip, 2)}")
        print(f"  IP:   {pitcher.stats.get('inningsPitched', 'N/A')}")
        print(f"  K:    {pitcher.strikeouts}")
        print(f"  BB:   {pitcher.walks}")

        if pitcher.opponent_average > 0:
            print(
                "  Opponent AVG: "
                f"{display_number(pitcher.opponent_average, 3)}"
            )


def predict_matchup() -> None:
    """
    Run Prediction Engine 4.0.

    This wrapper preserves compatibility with an existing app.py that
    imports and calls ``predict_matchup()``.
    """

    PredictionEngine().run()
