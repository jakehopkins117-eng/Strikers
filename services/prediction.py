from api.mlb_api import (
    find_team,
    get_team_hitting_stats,
    get_team_pitching_stats,
    get_team_record,
)


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


def get_location_win_percentage(team_record, location):
    records = team_record.get("records", {})
    split_records = records.get("splitRecords", [])

    for split in split_records:
        if split.get("type") == location:
            wins = safe_float(split.get("wins"))
            losses = safe_float(split.get("losses"))
            games = wins + losses

            if games == 0:
                return 0.0

            return wins / games

    return 0.0


def award_points(
    away_value,
    home_value,
    weight,
    lower_is_better=False,
):
    if away_value == home_value:
        return weight / 2, weight / 2

    if lower_is_better:
        if away_value < home_value:
            return weight, 0
        return 0, weight

    if away_value > home_value:
        return weight, 0

    return 0, weight


def display_prediction():
    print("\n" + "=" * 60)
    print("STRIKERS PREDICTION ENGINE V1")
    print("=" * 60)

    away_search = input("\nEnter the AWAY team: ").strip()
    home_search = input("Enter the HOME team: ").strip()

    if not away_search or not home_search:
        print("\nPlease enter both teams.")
        return

    print("\nLoading matchup data...")

    try:
        away_team = find_team(away_search)
        home_team = find_team(home_search)
    except Exception as error:
        print(f"\nTeam search failed: {error}")
        return

    if away_team is None:
        print(f"\nNo team was found for: {away_search}")
        return

    if home_team is None:
        print(f"\nNo team was found for: {home_search}")
        return

    if away_team["id"] == home_team["id"]:
        print("\nPlease choose two different teams.")
        return

    away_name = away_team.get("name", "Away Team")
    home_name = home_team.get("name", "Home Team")

    try:
        away_record = get_team_record(away_team["id"])
        home_record = get_team_record(home_team["id"])

        away_hitting = get_team_hitting_stats(away_team["id"])
        home_hitting = get_team_hitting_stats(home_team["id"])

        away_pitching = get_team_pitching_stats(away_team["id"])
        home_pitching = get_team_pitching_stats(home_team["id"])

    except Exception as error:
        print(f"\nStatistics lookup failed: {error}")
        return

    required_data = [
        away_record,
        home_record,
        away_hitting,
        home_hitting,
        away_pitching,
        home_pitching,
    ]

    if any(item is None for item in required_data):
        print("\nSome required matchup statistics were unavailable.")
        return

    away_win_pct = safe_float(
        away_record.get("winningPercentage")
    )
    home_win_pct = safe_float(
        home_record.get("winningPercentage")
    )

    away_ops = safe_float(away_hitting.get("ops"))
    home_ops = safe_float(home_hitting.get("ops"))

    away_runs_per_game = calculate_runs_per_game(away_hitting)
    home_runs_per_game = calculate_runs_per_game(home_hitting)

    away_era = safe_float(away_pitching.get("era"))
    home_era = safe_float(home_pitching.get("era"))

    away_whip = safe_float(away_pitching.get("whip"))
    home_whip = safe_float(home_pitching.get("whip"))

    away_location_pct = get_location_win_percentage(
        away_record,
        "away",
    )
    home_location_pct = get_location_win_percentage(
        home_record,
        "home",
    )

    away_score = 0.0
    home_score = 0.0
    reasons = []

    categories = [
        (
            "Season winning percentage",
            away_win_pct,
            home_win_pct,
            20,
            False,
        ),
        (
            "Team OPS",
            away_ops,
            home_ops,
            20,
            False,
        ),
        (
            "Runs per game",
            away_runs_per_game,
            home_runs_per_game,
            15,
            False,
        ),
        (
            "Team ERA",
            away_era,
            home_era,
            20,
            True,
        ),
        (
            "Team WHIP",
            away_whip,
            home_whip,
            15,
            True,
        ),
        (
            "Away versus home performance",
            away_location_pct,
            home_location_pct,
            10,
            False,
        ),
    ]

    for (
        category,
        away_value,
        home_value,
        weight,
        lower_is_better,
    ) in categories:
        away_points, home_points = award_points(
            away_value,
            home_value,
            weight,
            lower_is_better,
        )

        away_score += away_points
        home_score += home_points

        if away_points > home_points:
            reasons.append(f"{away_name}: Better {category.lower()}")
        elif home_points > away_points:
            reasons.append(f"{home_name}: Better {category.lower()}")

    score_difference = abs(away_score - home_score)

    # Shrinks the score into a reasonable 25%–75% range.
    winner_probability = 50 + (score_difference * 0.25)
    winner_probability = min(winner_probability, 75.0)
    loser_probability = 100 - winner_probability

    if away_score > home_score:
        predicted_winner = away_name
        away_probability = winner_probability
        home_probability = loser_probability
    elif home_score > away_score:
        predicted_winner = home_name
        home_probability = winner_probability
        away_probability = loser_probability
    else:
        predicted_winner = "Even matchup"
        away_probability = 50.0
        home_probability = 50.0

    if score_difference >= 40:
        confidence = "High"
    elif score_difference >= 20:
        confidence = "Medium"
    else:
        confidence = "Low"

    print("\n" + "=" * 70)
    print(f"{away_name.upper()} AT {home_name.upper()}")
    print("=" * 70)

    print("\nMODEL SCORES")
    print("-" * 70)
    print(f"{away_name:<35}{away_score:.1f}")
    print(f"{home_name:<35}{home_score:.1f}")

    print("\nESTIMATED WIN PROBABILITY")
    print("-" * 70)
    print(f"{away_name:<35}{away_probability:.1f}%")
    print(f"{home_name:<35}{home_probability:.1f}%")

    print("\nPREDICTION")
    print("-" * 70)
    print(f"Predicted winner: {predicted_winner}")
    print(f"Confidence:       {confidence}")

    print("\nTOP FACTORS")
    print("-" * 70)

    winning_reasons = [
        reason
        for reason in reasons
        if predicted_winner in reason
    ]

    if winning_reasons:
        for reason in winning_reasons[:4]:
            print(f"- {reason}")
    else:
        print("- The teams are closely matched across the model.")

    print(
        "\nNote: This is a weighted statistical estimate, not a "
        "guaranteed or professionally calibrated probability."
    )