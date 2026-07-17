from api.mlb_api import get_standings


def display_standings():
    print("\nLoading MLB standings...")

    try:
        data = get_standings()
    except Exception as error:
        print(f"\nStandings lookup failed: {error}")
        return

    records = data.get("records", [])

    if not records:
        print("\nNo standings were found.")
        return

    print("\n" + "=" * 60)
    print("MLB STANDINGS")
    print("=" * 60)

    for record_group in records:
        division_name = record_group.get(
            "division",
            {},
        ).get("name", "Unknown Division")

        print(f"\n{division_name}")
        print("-" * 60)
        print(
            f"{'RK':<4}"
            f"{'TEAM':<28}"
            f"{'W':<6}"
            f"{'L':<6}"
            f"{'PCT':<8}"
            f"{'GB'}"
        )

        for team_record in record_group.get("teamRecords", []):
            rank = team_record.get("divisionRank", "-")
            team_name = team_record.get(
                "team",
                {},
            ).get("name", "Unknown")
            wins = team_record.get("wins", 0)
            losses = team_record.get("losses", 0)
            percentage = team_record.get(
                "winningPercentage",
                ".000",
            )
            games_back = team_record.get("gamesBack", "-")

            print(
                f"{rank:<4}"
                f"{team_name:<28}"
                f"{wins:<6}"
                f"{losses:<6}"
                f"{percentage:<8}"
                f"{games_back}"
            )