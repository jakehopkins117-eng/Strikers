from api.mlb_api import (
    find_team,
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
)
from utils.formatting import get_split_record


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_runs_per_game(stats):
    runs = safe_float(stats.get("runs"))
    games = safe_float(stats.get("gamesPlayed"))

    if games == 0:
        return 0.0

    return runs / games


def display_stat_row(
    category,
    first_value,
    second_value,
    first_team_name,
    second_team_name,
    lower_is_better=False,
):
    first_number = safe_float(first_value)
    second_number = safe_float(second_value)

    if first_number == second_number:
        edge = "Even"
    elif lower_is_better:
        edge = (
            first_team_name
            if first_number < second_number
            else second_team_name
        )
    else:
        edge = (
            first_team_name
            if first_number > second_number
            else second_team_name
        )

    print(
        f"{category:<20}"
        f"{str(first_value):<18}"
        f"{str(second_value):<18}"
        f"{edge}"
    )


def display_team_comparison():
    print("\n" + "=" * 60)
    print("ADVANCED MLB TEAM COMPARISON")
    print("=" * 60)

    first_search = input("\nEnter the first team: ").strip()
    second_search = input("Enter the second team: ").strip()

    if not first_search or not second_search:
        print("\nPlease enter two team names.")
        return

    print("\nLoading team information...")

    try:
        first_team = find_team(first_search)
        second_team = find_team(second_search)
    except Exception as error:
        print(f"\nTeam search failed: {error}")
        return

    if first_team is None:
        print(f"\nNo team was found for: {first_search}")
        return

    if second_team is None:
        print(f"\nNo team was found for: {second_search}")
        return

    if first_team["id"] == second_team["id"]:
        print("\nPlease choose two different teams.")
        return

    first_name = first_team.get("name", "Team 1")
    second_name = second_team.get("name", "Team 2")

    print("\nLoading records and season statistics...")

    try:
        first_record = get_team_record(first_team["id"])
        second_record = get_team_record(second_team["id"])

        first_hitting = get_team_hitting_stats(first_team["id"])
        second_hitting = get_team_hitting_stats(second_team["id"])

        first_pitching = get_team_pitching_stats(first_team["id"])
        second_pitching = get_team_pitching_stats(second_team["id"])

    except Exception as error:
        print(f"\nStatistics lookup failed: {error}")
        return

    if first_record is None or second_record is None:
        print("\nCurrent team records could not be found.")
        return

    if first_hitting is None or second_hitting is None:
        print("\nTeam hitting statistics could not be found.")
        return

    if first_pitching is None or second_pitching is None:
        print("\nTeam pitching statistics could not be found.")
        return

    first_wins = first_record.get("wins", 0)
    first_losses = first_record.get("losses", 0)
    first_pct = first_record.get("winningPercentage", ".000")
    first_streak = first_record.get(
        "streak",
        {},
    ).get("streakCode", "None")

    second_wins = second_record.get("wins", 0)
    second_losses = second_record.get("losses", 0)
    second_pct = second_record.get("winningPercentage", ".000")
    second_streak = second_record.get(
        "streak",
        {},
    ).get("streakCode", "None")

    first_home = get_split_record(first_record, "home")
    first_away = get_split_record(first_record, "away")

    second_home = get_split_record(second_record, "home")
    second_away = get_split_record(second_record, "away")

    first_runs_per_game = calculate_runs_per_game(first_hitting)
    second_runs_per_game = calculate_runs_per_game(second_hitting)

    print("\n" + "=" * 90)
    print(f"{first_name.upper()} VS {second_name.upper()}")
    print("=" * 90)

    print(
        f"\n{'CATEGORY':<20}"
        f"{first_name[:16]:<18}"
        f"{second_name[:16]:<18}"
        f"EDGE"
    )
    print("-" * 90)

    print("\nTEAM RECORD")
    print("-" * 90)

    display_stat_row(
        "Winning %",
        first_pct,
        second_pct,
        first_name,
        second_name,
    )

    print(
        f"{'Overall record':<20}"
        f"{f'{first_wins}-{first_losses}':<18}"
        f"{f'{second_wins}-{second_losses}':<18}"
        f"{''}"
    )

    print(
        f"{'Home record':<20}"
        f"{first_home:<18}"
        f"{second_home:<18}"
    )

    print(
        f"{'Away record':<20}"
        f"{first_away:<18}"
        f"{second_away:<18}"
    )

    print(
        f"{'Current streak':<20}"
        f"{first_streak:<18}"
        f"{second_streak:<18}"
    )

    print("\nOFFENSE")
    print("-" * 90)

    display_stat_row(
        "Batting average",
        first_hitting.get("avg", ".000"),
        second_hitting.get("avg", ".000"),
        first_name,
        second_name,
    )

    display_stat_row(
        "On-base %",
        first_hitting.get("obp", ".000"),
        second_hitting.get("obp", ".000"),
        first_name,
        second_name,
    )

    display_stat_row(
        "Slugging %",
        first_hitting.get("slg", ".000"),
        second_hitting.get("slg", ".000"),
        first_name,
        second_name,
    )

    display_stat_row(
        "OPS",
        first_hitting.get("ops", ".000"),
        second_hitting.get("ops", ".000"),
        first_name,
        second_name,
    )

    display_stat_row(
        "Runs",
        first_hitting.get("runs", 0),
        second_hitting.get("runs", 0),
        first_name,
        second_name,
    )

    display_stat_row(
        "Runs per game",
        f"{first_runs_per_game:.2f}",
        f"{second_runs_per_game:.2f}",
        first_name,
        second_name,
    )

    display_stat_row(
        "Home runs",
        first_hitting.get("homeRuns", 0),
        second_hitting.get("homeRuns", 0),
        first_name,
        second_name,
    )

    display_stat_row(
        "Stolen bases",
        first_hitting.get("stolenBases", 0),
        second_hitting.get("stolenBases", 0),
        first_name,
        second_name,
    )

    print("\nPITCHING")
    print("-" * 90)

    display_stat_row(
        "ERA",
        first_pitching.get("era", "0.00"),
        second_pitching.get("era", "0.00"),
        first_name,
        second_name,
        lower_is_better=True,
    )

    display_stat_row(
        "WHIP",
        first_pitching.get("whip", "0.00"),
        second_pitching.get("whip", "0.00"),
        first_name,
        second_name,
        lower_is_better=True,
    )

    display_stat_row(
        "Opponent AVG",
        first_pitching.get("avg", ".000"),
        second_pitching.get("avg", ".000"),
        first_name,
        second_name,
        lower_is_better=True,
    )

    display_stat_row(
        "Strikeouts",
        first_pitching.get("strikeOuts", 0),
        second_pitching.get("strikeOuts", 0),
        first_name,
        second_name,
    )

    display_stat_row(
        "Walks allowed",
        first_pitching.get("baseOnBalls", 0),
        second_pitching.get("baseOnBalls", 0),
        first_name,
        second_name,
        lower_is_better=True,
    )

    first_score = 0
    second_score = 0

    comparison_categories = [
        (
            safe_float(first_pct),
            safe_float(second_pct),
            False,
        ),
        (
            safe_float(first_hitting.get("avg")),
            safe_float(second_hitting.get("avg")),
            False,
        ),
        (
            safe_float(first_hitting.get("obp")),
            safe_float(second_hitting.get("obp")),
            False,
        ),
        (
            safe_float(first_hitting.get("slg")),
            safe_float(second_hitting.get("slg")),
            False,
        ),
        (
            safe_float(first_hitting.get("ops")),
            safe_float(second_hitting.get("ops")),
            False,
        ),
        (
            first_runs_per_game,
            second_runs_per_game,
            False,
        ),
        (
            safe_float(first_pitching.get("era")),
            safe_float(second_pitching.get("era")),
            True,
        ),
        (
            safe_float(first_pitching.get("whip")),
            safe_float(second_pitching.get("whip")),
            True,
        ),
    ]

    for first_value, second_value, lower_is_better in comparison_categories:
        if first_value == second_value:
            continue

        if lower_is_better:
            if first_value < second_value:
                first_score += 1
            else:
                second_score += 1
        else:
            if first_value > second_value:
                first_score += 1
            else:
                second_score += 1

    total_points = first_score + second_score

    print("\n" + "=" * 90)
    print("OVERALL ANALYTICS EDGE")
    print("=" * 90)

    print(f"{first_name}: {first_score} category points")
    print(f"{second_name}: {second_score} category points")

    if first_score > second_score:
        confidence = (
            first_score / total_points * 100
            if total_points
            else 50
        )

        print(f"\nCurrent edge: {first_name}")
        print(f"Comparison confidence: {confidence:.1f}%")

    elif second_score > first_score:
        confidence = (
            second_score / total_points * 100
            if total_points
            else 50
        )

        print(f"\nCurrent edge: {second_name}")
        print(f"Comparison confidence: {confidence:.1f}%")

    else:
        print("\nCurrent edge: Even")
        print("Comparison confidence: 50.0%")

    print(
        "\nThis compares season performance and is not yet a "
        "game prediction."
    )