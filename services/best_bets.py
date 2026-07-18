"""
Strikers Best Bets 2.0

Features:
- Analyze today's, tomorrow's, or a custom MLB slate
- Rank games by model probability
- Show game start times
- Separate BET, LEAN, and PASS tiers
- Warn when probable pitchers are incomplete
- Prevent duplicate games
- Save each generated slate for future model tracking
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from api.mlb_api import get_schedule_by_date, get_today_schedule
from services.prediction import PredictionEngine


BET_THRESHOLD = 60.0
LEAN_THRESHOLD = 55.0
MAX_PLAYS_TO_DISPLAY = 10

EASTERN_TIME = ZoneInfo("America/New_York")
HISTORY_FILE = Path("data") / "best_bets_history.jsonl"


@dataclass
class BestBet:
    """A single analyzed MLB matchup."""

    game_id: int
    game_date: str
    start_time: str
    away_team: str
    home_team: str
    predicted_winner: str
    probability: float
    confidence: str
    confidence_stars: str
    recommendation: str
    reasons: list[str]
    away_pitcher: str
    home_pitcher: str
    pitchers_confirmed: bool
    game_status: str


def extract_games(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract games from the MLB schedule response."""

    games: list[dict[str, Any]] = []

    for date_group in schedule.get("dates", []):
        games.extend(date_group.get("games", []))

    return games


def remove_duplicate_games(
    games: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate games using the MLB game ID."""

    unique_games: list[dict[str, Any]] = []
    seen_game_ids: set[int] = set()

    for game in games:
        game_id = int(game.get("gamePk", 0))

        if game_id and game_id in seen_game_ids:
            continue

        if game_id:
            seen_game_ids.add(game_id)

        unique_games.append(game)

    return unique_games


def get_game_status(game: dict[str, Any]) -> str:
    """Return the most useful game-status description."""

    status = game.get("status", {})

    return str(
        status.get("detailedState")
        or status.get("abstractGameState")
        or "Unknown"
    )


def is_game_eligible(game: dict[str, Any]) -> bool:
    """Determine whether a matchup can receive a pregame prediction."""

    status = get_game_status(game).lower()

    excluded_statuses = (
        "final",
        "game over",
        "completed early",
        "cancelled",
        "canceled",
        "postponed",
        "suspended",
    )

    return not any(
        excluded_status in status
        for excluded_status in excluded_statuses
    )


def get_team_name(
    game: dict[str, Any],
    side: str,
) -> str:
    """Extract the home or away team name."""

    return str(
        game.get("teams", {})
        .get(side, {})
        .get("team", {})
        .get("name", "")
    ).strip()


def format_game_time(game: dict[str, Any]) -> str:
    """Convert the MLB UTC start time to Eastern Time."""

    raw_time = str(game.get("gameDate", "")).strip()

    if not raw_time:
        return "Time TBD"

    try:
        utc_time = datetime.fromisoformat(
            raw_time.replace("Z", "+00:00")
        )

        eastern_time = utc_time.astimezone(EASTERN_TIME)

        return eastern_time.strftime("%-I:%M %p ET")

    except (ValueError, TypeError):
        return "Time TBD"


def get_game_date(game: dict[str, Any]) -> str:
    """Return the scheduled game date."""

    raw_time = str(game.get("gameDate", "")).strip()

    if not raw_time:
        return ""

    try:
        utc_time = datetime.fromisoformat(
            raw_time.replace("Z", "+00:00")
        )

        return utc_time.astimezone(EASTERN_TIME).date().isoformat()

    except (ValueError, TypeError):
        return raw_time[:10]


def get_recommendation(probability: float) -> str:
    """Convert model probability into a recommendation tier."""

    if probability >= BET_THRESHOLD:
        return "BET"

    if probability >= LEAN_THRESHOLD:
        return "LEAN"

    return "PASS"


def get_pitcher_name(pitcher: Any) -> str:
    """Safely extract a pitcher name."""

    name = getattr(pitcher, "name", None)

    if not name:
        return "Not announced"

    return str(name)


def pitcher_is_available(pitcher: Any) -> bool:
    """Safely determine whether pitcher data is available."""

    return bool(getattr(pitcher, "available", False))


def analyze_game(game: dict[str, Any]) -> BestBet | None:
    """Run Prediction Engine 3.0 silently for one matchup."""

    away_team = get_team_name(game, "away")
    home_team = get_team_name(game, "home")

    if not away_team or not home_team:
        return None

    engine = PredictionEngine()
    result = engine.predict_silent(away_team, home_team)

    probability = round(
        max(
            float(result.away_probability),
            float(result.home_probability),
        ),
        1,
    )

    away_pitcher = get_pitcher_name(engine.away_pitcher)
    home_pitcher = get_pitcher_name(engine.home_pitcher)

    pitchers_confirmed = (
        pitcher_is_available(engine.away_pitcher)
        and pitcher_is_available(engine.home_pitcher)
    )

    return BestBet(
        game_id=int(game.get("gamePk", 0)),
        game_date=get_game_date(game),
        start_time=format_game_time(game),
        away_team=away_team,
        home_team=home_team,
        predicted_winner=str(result.winner),
        probability=probability,
        confidence=str(result.confidence),
        confidence_stars=str(result.confidence_stars),
        recommendation=get_recommendation(probability),
        reasons=list(result.reasons),
        away_pitcher=away_pitcher,
        home_pitcher=home_pitcher,
        pitchers_confirmed=pitchers_confirmed,
        game_status=get_game_status(game),
    )


def choose_slate_date() -> date | None:
    """Ask the user which MLB slate should be analyzed."""

    print("\nChoose a slate:")
    print("1. Today")
    print("2. Tomorrow")
    print("3. Custom date")
    print("4. Return to main menu")

    choice = input("\nChoose an option: ").strip()

    if choice == "1":
        return date.today()

    if choice == "2":
        return date.today() + timedelta(days=1)

    if choice == "3":
        raw_date = input(
            "Enter a date in YYYY-MM-DD format: "
        ).strip()

        try:
            return datetime.strptime(
                raw_date,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            print("\nInvalid date. Use YYYY-MM-DD.")
            return None

    if choice == "4":
        return None

    print("\nInvalid option.")
    return None


def load_schedule(target_date: date) -> dict[str, Any]:
    """Load an MLB schedule for the chosen date."""

    if target_date == date.today():
        return get_today_schedule()

    return get_schedule_by_date(target_date.isoformat())


def load_best_bets(
    target_date: date,
) -> tuple[list[BestBet], int, int]:
    """
    Analyze all eligible games.

    Returns:
        analyzed bets
        eligible-game count
        failed-game count
    """

    schedule = load_schedule(target_date)

    games = remove_duplicate_games(
        extract_games(schedule)
    )

    eligible_games = [
        game
        for game in games
        if is_game_eligible(game)
    ]

    analyzed_bets: list[BestBet] = []
    failed_games = 0

    if not eligible_games:
        return [], 0, 0

    print(
        f"\nFound {len(eligible_games)} eligible "
        f"game(s) for {target_date.isoformat()}."
    )
    print("Running Prediction Engine 3.0...\n")

    for number, game in enumerate(eligible_games, start=1):
        away_team = get_team_name(game, "away")
        home_team = get_team_name(game, "home")

        print(
            f"[{number:>2}/{len(eligible_games)}] "
            f"{away_team} @ {home_team}"
        )

        try:
            bet = analyze_game(game)

            if bet is not None:
                analyzed_bets.append(bet)

        except Exception as error:
            failed_games += 1
            print(f"     Analysis failed: {error}")

    analyzed_bets.sort(
        key=lambda bet: (
            bet.probability,
            bet.pitchers_confirmed,
        ),
        reverse=True,
    )

    return (
        analyzed_bets[:MAX_PLAYS_TO_DISPLAY],
        len(eligible_games),
        failed_games,
    )


def save_best_bets_history(
    target_date: date,
    bets: list[BestBet],
) -> None:
    """Save generated predictions for future accuracy tracking."""

    HISTORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_at = datetime.now(
        EASTERN_TIME
    ).isoformat(timespec="seconds")

    with HISTORY_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        for bet in bets:
            record = {
                "generated_at": generated_at,
                "slate_date": target_date.isoformat(),
                **asdict(bet),
                "result": None,
                "correct": None,
            }

            file.write(
                json.dumps(record, ensure_ascii=False)
                + "\n"
            )


def display_bet(
    bet: BestBet,
    rank: int,
) -> None:
    """Display one ranked matchup."""

    print("\n" + "-" * 72)
    print(
        f"#{rank}  [{bet.recommendation}] "
        f"{bet.predicted_winner} MONEYLINE"
    )
    print("-" * 72)

    print(
        f"Matchup:           "
        f"{bet.away_team} @ {bet.home_team}"
    )
    print(f"Start time:        {bet.start_time}")
    print(f"Game status:       {bet.game_status}")
    print(f"Model probability: {bet.probability:.1f}%")
    print(f"Confidence:        {bet.confidence}")
    print(f"Rating:            {bet.confidence_stars}")

    print("\nProbable starters:")
    print(
        f"  {bet.away_team}: "
        f"{bet.away_pitcher}"
    )
    print(
        f"  {bet.home_team}: "
        f"{bet.home_pitcher}"
    )

    if not bet.pitchers_confirmed:
        print(
            "\nWarning: Complete probable-pitcher "
            "information is not available."
        )

    print("\nModel advantages:")

    if bet.reasons:
        for reason in bet.reasons[:5]:
            print(f"  - {reason}")

    else:
        print(
            "  - No major statistical separation "
            "was identified."
        )


def display_summary(bets: list[BestBet]) -> None:
    """Display recommendation-tier totals."""

    bet_count = sum(
        item.recommendation == "BET"
        for item in bets
    )

    lean_count = sum(
        item.recommendation == "LEAN"
        for item in bets
    )

    pass_count = sum(
        item.recommendation == "PASS"
        for item in bets
    )

    print("\nRecommendation summary:")
    print(f"  BET:  {bet_count}")
    print(f"  LEAN: {lean_count}")
    print(f"  PASS: {pass_count}")


def display_best_bets() -> None:
    """Generate and display the selected slate."""

    print("\n" + "=" * 72)
    print("STRIKERS BEST BETS 2.0".center(72))
    print("=" * 72)

    print(
        "\nBET  = 60.0% or higher\n"
        "LEAN = 55.0% to 59.9%\n"
        "PASS = Below 55.0%"
    )

    target_date = choose_slate_date()

    if target_date is None:
        return

    try:
        bets, eligible_games, failed_games = load_best_bets(
            target_date
        )

    except ConnectionError as error:
        print(
            f"\nThe MLB schedule could not be loaded: "
            f"{error}"
        )
        return

    except Exception as error:
        print(
            f"\nBest Bets could not be generated: "
            f"{error}"
        )
        return

    print("\n" + "=" * 72)
    print(
        f"SLATE RESULTS — {target_date.isoformat()}".center(72)
    )
    print("=" * 72)

    print(f"Eligible games:   {eligible_games}")
    print(f"Analysis failures:{failed_games:>4}")

    if eligible_games == 0:
        print(
            "\nThere are no eligible MLB games "
            "for this date."
        )
        return

    if not bets:
        print("\nNo games were successfully analyzed.")
        return

    display_summary(bets)

    for rank, bet in enumerate(bets, start=1):
        display_bet(bet, rank)

    try:
        save_best_bets_history(
            target_date,
            bets,
        )

        print(
            f"\nPredictions saved to: {HISTORY_FILE}"
        )

    except OSError as error:
        print(
            f"\nPredictions were displayed but could "
            f"not be saved: {error}"
        )

    print("\n" + "=" * 72)
    print(
        "Model probabilities are estimates, not guarantees. "
        "Sportsbook prices are not yet included."
    )
    print("=" * 72)