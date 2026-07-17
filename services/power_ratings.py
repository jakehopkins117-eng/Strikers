from __future__ import annotations

from typing import Any

from api.mlb_api import (
    find_team,
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert an MLB API value into a float safely."""

    if value is None:
        return default

    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Convert an MLB API value into an integer safely."""

    if value is None:
        return default

    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Keep a value within a defined range."""

    return max(minimum, min(maximum, value))


def get_winning_percentage(record: dict[str, Any]) -> float:
    """Extract or calculate a team's winning percentage."""

    direct_percentage = record.get("winningPercentage")

    if direct_percentage is not None:
        return safe_float(direct_percentage, 0.5)

    wins = safe_int(record.get("wins"))
    losses = safe_int(record.get("losses"))
    total_games = wins + losses

    if total_games == 0:
        return 0.5

    return wins / total_games


def get_runs_per_game(hitting: dict[str, Any]) -> float:
    """Calculate runs scored per game."""

    games_played = safe_float(hitting.get("gamesPlayed"))
    runs = safe_float(hitting.get("runs"))

    if games_played == 0:
        return 0.0

    return runs / games_played


def score_higher_is_better(
    value: float,
    poor_value: float,
    elite_value: float,
) -> float:
    """
    Convert a statistic into a 0–100 component score.

    Used for statistics where higher values are better.
    """

    if elite_value == poor_value:
        return 50.0

    score = ((value - poor_value) / (elite_value - poor_value)) * 100

    return clamp(score, 0.0, 100.0)


def score_lower_is_better(
    value: float,
    elite_value: float,
    poor_value: float,
) -> float:
    """
    Convert a statistic into a 0–100 component score.

    Used for statistics where lower values are better.
    """

    if poor_value == elite_value:
        return 50.0

    score = ((poor_value - value) / (poor_value - elite_value)) * 100

    return clamp(score, 0.0, 100.0)


def calculate_power_rating(
    win_percentage: float,
    ops: float,
    runs_per_game: float,
    era: float,
    whip: float,
) -> tuple[float, dict[str, float]]:
    """
    Calculate a weighted team power rating from 0 to 100.

    Weights:
        Winning percentage: 30%
        OPS:                25%
        Runs per game:      20%
        ERA:                15%
        WHIP:               10%
    """

    component_scores = {
        "Season record": score_higher_is_better(
            win_percentage,
            poor_value=0.350,
            elite_value=0.650,
        ),
        "OPS": score_higher_is_better(
            ops,
            poor_value=0.620,
            elite_value=0.850,
        ),
        "Runs per game": score_higher_is_better(
            runs_per_game,
            poor_value=3.2,
            elite_value=6.0,
        ),
        "Team ERA": score_lower_is_better(
            era,
            elite_value=2.80,
            poor_value=5.80,
        ),
        "Team WHIP": score_lower_is_better(
            whip,
            elite_value=1.05,
            poor_value=1.55,
        ),
    }

    power_rating = (
        component_scores["Season record"] * 0.30
        + component_scores["OPS"] * 0.25
        + component_scores["Runs per game"] * 0.20
        + component_scores["Team ERA"] * 0.15
        + component_scores["Team WHIP"] * 0.10
    )

    return round(power_rating, 1), component_scores


def get_rating_label(power_rating: float) -> str:
    """Convert a numerical power rating into a readable label."""

    if power_rating >= 85:
        return "ELITE"

    if power_rating >= 75:
        return "CONTENDER"

    if power_rating >= 65:
        return "ABOVE AVERAGE"

    if power_rating >= 50:
        return "AVERAGE"

    if power_rating >= 35:
        return "BELOW AVERAGE"

    return "STRUGGLING"


def display_component_bar(score: float, length: int = 20) -> str:
    """Create a terminal progress bar for a component score."""

    filled = round((score / 100) * length)
    empty = length - filled

    return f"[{'#' * filled}{'-' * empty}]"


def display_power_rating() -> None:
    """Prompt for an MLB team and display its current power rating."""

    print("\n" + "=" * 62)
    print("STRIKERS MLB POWER RATINGS".center(62))
    print("=" * 62)

    search = input("\nEnter an MLB team: ").strip()

    if not search:
        print("\nA team name is required.")
        return

    print("\nLoading team statistics...")

    try:
        team = find_team(search)

        if not team:
            print(f"\nTeam not found: {search}")
            return

        team_id = safe_int(team.get("id"))
        team_name = team.get("name", "Unknown Team")

        record = get_team_record(team_id) or {}
        hitting = get_team_hitting_stats(team_id) or {}
        pitching = get_team_pitching_stats(team_id) or {}

        win_percentage = get_winning_percentage(record)
        ops = safe_float(hitting.get("ops"))
        runs_per_game = get_runs_per_game(hitting)
        era = safe_float(pitching.get("era"))
        whip = safe_float(pitching.get("whip"))

        power_rating, component_scores = calculate_power_rating(
            win_percentage=win_percentage,
            ops=ops,
            runs_per_game=runs_per_game,
            era=era,
            whip=whip,
        )

        label = get_rating_label(power_rating)

        print("\n" + "=" * 62)
        print(team_name.center(62))
        print("=" * 62)

        print("\nCURRENT STATISTICS")
        print("-" * 62)
        print(f"Winning percentage: {win_percentage:.3f}")
        print(f"OPS:                {ops:.3f}")
        print(f"Runs per game:      {runs_per_game:.2f}")
        print(f"Team ERA:           {era:.2f}")
        print(f"Team WHIP:          {whip:.2f}")

        print("\nPOWER RATING COMPONENTS")
        print("-" * 62)

        for component, score in component_scores.items():
            bar = display_component_bar(score)

            print(
                f"{component:<20}"
                f"{bar} "
                f"{score:>5.1f}"
            )

        print("\nFINAL POWER RATING")
        print("-" * 62)
        print(f"Power score: {power_rating:.1f} / 100")
        print(f"Team status: {label}")

        print("\n" + "=" * 62)
        print(
            "Power ratings use current season statistics and update "
            "with MLB data."
        )
        print("=" * 62)

    except (ConnectionError, RuntimeError) as error:
        print(f"\nPower rating could not be completed: {error}")

    except Exception as error:
        print(f"\nUnexpected power-rating error: {error}")