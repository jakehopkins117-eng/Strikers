from __future__ import annotations

from typing import Any

import requests

from api.mlb_api import (
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
)
from services.power_ratings import (
    calculate_power_rating,
    get_rating_label,
    get_runs_per_game,
    get_winning_percentage,
    safe_float,
    safe_int,
)


MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"


def get_all_mlb_teams() -> list[dict[str, Any]]:
    """
    Download all active Major League Baseball teams.
    """

    try:
        response = requests.get(
            MLB_TEAMS_URL,
            params={
                "sportId": 1,
                "activeStatus": "Y",
            },
            timeout=15,
        )

        response.raise_for_status()
        data = response.json()

        teams = data.get("teams", [])

        return sorted(
            teams,
            key=lambda team: team.get("name", ""),
        )

    except requests.RequestException as error:
        raise ConnectionError(
            f"Could not download the MLB team list: {error}"
        ) from error


def build_team_power_rating(
    team: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Download one team's statistics and calculate its power rating.
    """

    team_id = safe_int(team.get("id"))
    team_name = team.get("name", "Unknown Team")

    if team_id == 0:
        return None

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

    return {
        "team_id": team_id,
        "team_name": team_name,
        "power_rating": power_rating,
        "label": get_rating_label(power_rating),
        "win_percentage": win_percentage,
        "ops": ops,
        "runs_per_game": runs_per_game,
        "era": era,
        "whip": whip,
        "component_scores": component_scores,
    }


def load_all_power_rankings() -> list[dict[str, Any]]:
    """
    Calculate power ratings for every active MLB team.
    """

    teams = get_all_mlb_teams()
    rankings: list[dict[str, Any]] = []

    print(f"\nFound {len(teams)} MLB teams.")
    print("Calculating ratings...\n")

    for position, team in enumerate(teams, start=1):
        team_name = team.get("name", "Unknown Team")

        print(
            f"[{position:>2}/{len(teams)}] "
            f"Loading {team_name}..."
        )

        try:
            rating = build_team_power_rating(team)

            if rating is not None:
                rankings.append(rating)

        except Exception as error:
            print(
                f"     Could not calculate {team_name}: {error}"
            )

    rankings.sort(
        key=lambda item: item["power_rating"],
        reverse=True,
    )

    return rankings


def display_rankings_table(
    rankings: list[dict[str, Any]],
) -> None:
    """
    Display the league-wide power rankings table.
    """

    print("\n" + "=" * 94)
    print("STRIKERS MLB POWER RANKINGS".center(94))
    print("=" * 94)

    if not rankings:
        print("\nNo power rankings could be calculated.")
        return

    print(
        f"{'RK':<4}"
        f"{'TEAM':<27}"
        f"{'POWER':>8}"
        f"{'W%':>8}"
        f"{'OPS':>8}"
        f"{'R/G':>8}"
        f"{'ERA':>8}"
        f"{'WHIP':>8}"
        f"{'STATUS':>15}"
    )

    print("-" * 94)

    for rank, team in enumerate(rankings, start=1):
        print(
            f"{rank:<4}"
            f"{team['team_name']:<27}"
            f"{team['power_rating']:>8.1f}"
            f"{team['win_percentage']:>8.3f}"
            f"{team['ops']:>8.3f}"
            f"{team['runs_per_game']:>8.2f}"
            f"{team['era']:>8.2f}"
            f"{team['whip']:>8.2f}"
            f"{team['label']:>15}"
        )

    print("=" * 94)
    print(
        "Ratings use current season record, OPS, runs per game, "
        "team ERA, and WHIP."
    )
    print("=" * 94)


def display_top_and_bottom(
    rankings: list[dict[str, Any]],
) -> None:
    """
    Display a short summary of the strongest and weakest teams.
    """

    if len(rankings) < 3:
        return

    print("\nTOP THREE TEAMS")
    print("-" * 50)

    for rank, team in enumerate(rankings[:3], start=1):
        print(
            f"{rank}. {team['team_name']} "
            f"— {team['power_rating']:.1f}"
        )

    print("\nBOTTOM THREE TEAMS")
    print("-" * 50)

    bottom_three = rankings[-3:]

    for team in reversed(bottom_three):
        actual_rank = rankings.index(team) + 1

        print(
            f"{actual_rank}. {team['team_name']} "
            f"— {team['power_rating']:.1f}"
        )


def display_power_rankings() -> None:
    """
    Load and display power ratings for all MLB teams.
    """

    print("\n" + "=" * 62)
    print("STRIKERS MLB POWER RANKINGS".center(62))
    print("=" * 62)

    print(
        "\nThis may take a little time because Strikers must "
        "load statistics for every MLB team."
    )

    try:
        rankings = load_all_power_rankings()

        display_rankings_table(rankings)
        display_top_and_bottom(rankings)

    except ConnectionError as error:
        print(f"\nPower rankings could not be loaded: {error}")

    except Exception as error:
        print(f"\nUnexpected power-ranking error: {error}")