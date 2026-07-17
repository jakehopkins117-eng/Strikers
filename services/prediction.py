"""
Strikers Prediction Engine 3.0

This module provides an object-oriented MLB matchup prediction engine.
It combines team performance, offense, pitching, home/away records,
home-field advantage, and probable starting-pitcher statistics.

The public ``predict_matchup()`` function is kept for compatibility with
older versions of app.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.prediction_tracker import save_prediction

from api.mlb_api import (
    find_team,
    get_pitcher_stats,
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
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

    TEAM_WEIGHT = 65.0
    PITCHER_WEIGHT = 30.0
    HOME_FIELD_POINTS = 5.0

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
            self.save_prediction_to_history(result)

        except (ConnectionError, RuntimeError) as error:
            print(f"\nPrediction could not be completed: {error}")
        except Exception as error:
            print(f"\nUnexpected prediction error: {error}")

    @staticmethod
    def print_header() -> None:
        """Display the Prediction Engine heading."""

        print("\n" + "=" * 62)
        print("STRIKERS PREDICTION ENGINE 3.0".center(62))
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
        """Score the matchup and produce win probabilities."""

        assert self.away_data is not None
        assert self.home_data is not None

        away_score = 0.0
        home_score = self.HOME_FIELD_POINTS
        self.factor_edges = []

        team_factors = [
            (
                "Season record",
                self.away_data.win_pct,
                self.home_data.win_pct,
                14.0,
                True,
            ),
            (
                "Home/away performance",
                self.away_data.location_win_pct,
                self.home_data.location_win_pct,
                8.0,
                True,
            ),
            (
                "OPS",
                self.away_data.ops,
                self.home_data.ops,
                16.0,
                True,
            ),
            (
                "Runs per game",
                self.away_data.runs_per_game,
                self.home_data.runs_per_game,
                12.0,
                True,
            ),
            (
                "Team ERA",
                self.away_data.era,
                self.home_data.era,
                9.0,
                False,
            ),
            (
                "Team WHIP",
                self.away_data.whip,
                self.home_data.whip,
                6.0,
                False,
            ),
        ]

        for label, away_value, home_value, points, higher_is_better in team_factors:
            awarded = self.award_factor(
                label,
                away_value,
                home_value,
                points,
                higher_is_better,
            )
            away_score += awarded[0]
            home_score += awarded[1]

        pitcher_points = self.score_pitchers()
        away_score += pitcher_points[0]
        home_score += pitcher_points[1]

        self.factor_edges.append(
            ("Home-field advantage", self.home_data.name)
        )

        total = away_score + home_score

        if total <= 0:
            away_probability = 50.0
            home_probability = 50.0
        else:
            away_probability = (away_score / total) * 100
            home_probability = 100 - away_probability

        # Keep probabilities from becoming falsely extreme.
        away_probability = max(20.0, min(80.0, away_probability))
        home_probability = 100 - away_probability

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
    ) -> tuple[float, float]:
        """Award model points for one statistical category."""

        assert self.away_data is not None
        assert self.home_data is not None

        if away_value <= 0 and home_value <= 0:
            return points / 2, points / 2

        if abs(away_value - home_value) < 0.0001:
            return points / 2, points / 2

        away_is_better = (
            away_value > home_value
            if higher_is_better
            else away_value < home_value
        )

        if away_is_better:
            self.factor_edges.append((label, self.away_data.name))
            return points, 0.0

        self.factor_edges.append((label, self.home_data.name))
        return 0.0, points

    def score_pitchers(self) -> tuple[float, float]:
        """Score the probable starting-pitcher matchup."""

        assert self.away_data is not None
        assert self.home_data is not None

        total_points = self.PITCHER_WEIGHT

        if not self.away_pitcher.available and not self.home_pitcher.available:
            return total_points / 2, total_points / 2

        if self.away_pitcher.available and not self.home_pitcher.available:
            self.factor_edges.append(
                ("Confirmed starting pitcher", self.away_data.name)
            )
            return total_points * 0.65, total_points * 0.35

        if self.home_pitcher.available and not self.away_pitcher.available:
            self.factor_edges.append(
                ("Confirmed starting pitcher", self.home_data.name)
            )
            return total_points * 0.35, total_points * 0.65

        away_score = 0.0
        home_score = 0.0

        pitcher_factors = [
            ("Starter ERA", self.away_pitcher.era, self.home_pitcher.era, 12.0, False),
            ("Starter WHIP", self.away_pitcher.whip, self.home_pitcher.whip, 8.0, False),
            (
                "Starter strikeout rate",
                self.pitcher_rate(self.away_pitcher.strikeouts, self.away_pitcher.innings),
                self.pitcher_rate(self.home_pitcher.strikeouts, self.home_pitcher.innings),
                5.0,
                True,
            ),
            (
                "Starter walk rate",
                self.pitcher_rate(self.away_pitcher.walks, self.away_pitcher.innings),
                self.pitcher_rate(self.home_pitcher.walks, self.home_pitcher.innings),
                3.0,
                False,
            ),
            (
                "Starter opponent average",
                self.away_pitcher.opponent_average,
                self.home_pitcher.opponent_average,
                2.0,
                False,
            ),
        ]

        for label, away_value, home_value, points, higher_is_better in pitcher_factors:
            awarded = self.award_factor(
                label,
                away_value,
                home_value,
                points,
                higher_is_better,
            )
            away_score += awarded[0]
            home_score += awarded[1]

        # Reduce confidence in tiny samples.
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
        """Convert a win probability into a confidence label."""

        if probability >= 72:
            return "HIGH", "â˜…â˜…â˜…â˜…â˜…"

        if probability >= 64:
            return "MEDIUM-HIGH", "â˜…â˜…â˜…â˜…â˜†"

        if probability >= 57:
            return "MEDIUM", "â˜…â˜…â˜…â˜†â˜†"

        if probability >= 53:
            return "LOW", "â˜…â˜…â˜†â˜†â˜†"

        return "VERY LOW", "â˜…â˜†â˜†â˜†â˜†"

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
                print(f"âœ“ {reason}")
        else:
            print("The matchup is nearly even across the available factors.")

        print("\n" + "=" * 62)
        print(
            "Model probabilities are estimates, not guarantees."
        )
        print("=" * 62)

    def save_prediction_to_history(self, result: ModelResult) -> None:
        """Save the completed prediction to prediction history."""

        assert self.away_data is not None
        assert self.home_data is not None

        if result.winner == self.away_data.name:
            winning_probability = result.away_probability
        else:
            winning_probability = result.home_probability

        try:
            prediction_id = save_prediction(
                away_team=self.away_data.name,
                home_team=self.home_data.name,
                predicted_winner=result.winner,
                predicted_probability=winning_probability,
                confidence=result.confidence,
            )
        except (OSError, ValueError) as error:
            print(f"\nPrediction could not be saved to history: {error}")
            return

        print("\nPrediction saved to history.")
        print(f"Prediction ID: {prediction_id}")
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
    Run Prediction Engine 3.0.

    This wrapper preserves compatibility with an existing app.py that
    imports and calls ``predict_matchup()``.
    """

    PredictionEngine().run()

