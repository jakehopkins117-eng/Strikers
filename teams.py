from api.mlb_api import find_team, get_team_record
from utils.formatting import get_split_record


def display_team_search():
    search_term = input(
        "\nEnter a team name, city, nickname, or abbreviation: "
    ).strip()

    if not search_term:
        print("\nPlease enter a team.")
        return

    print("\nSearching for team...")

    try:
        team = find_team(search_term)
    except Exception as error:
        print(f"\nTeam search failed: {error}")
        return

    if team is None:
        print("\nNo MLB team was found.")
        print("Try Orioles, Baltimore, Yankees, or NYY.")
        return

    try:
        record = get_team_record(team["id"])
    except Exception as error:
        print(f"\nTeam record lookup failed: {error}")
        return

    team_name = team.get("name", "Unknown")
    abbreviation = team.get("abbreviation", "Unknown")
    league = team.get("league", {}).get("name", "Unknown")
    division = team.get("division", {}).get("name", "Unknown")
    venue = team.get("venue", {}).get("name", "Unknown")
    first_year = team.get("firstYearOfPlay", "Unknown")

    print("\n" + "=" * 45)
    print(team_name.upper())
    print("=" * 45)
    print(f"Abbreviation: {abbreviation}")
    print(f"League:       {league}")
    print(f"Division:     {division}")
    print(f"Stadium:      {venue}")
    print(f"First season: {first_year}")

    if record is None:
        print("\nNo current record was found.")
        return

    wins = record.get("wins", 0)
    losses = record.get("losses", 0)
    winning_percentage = record.get("winningPercentage", ".000")
    division_rank = record.get("divisionRank", "Unknown")
    games_back = record.get("gamesBack", "Unknown")
    streak = record.get("streak", {}).get("streakCode", "None")

    home_record = get_split_record(record, "home")
    away_record = get_split_record(record, "away")

    print("\nCurrent Record")
    print("-" * 45)
    print(f"Overall:        {wins}-{losses}")
    print(f"Win %:          {winning_percentage}")
    print(f"Division rank:  {division_rank}")
    print(f"Games back:     {games_back}")
    print(f"Home record:    {home_record}")
    print(f"Away record:    {away_record}")
    print(f"Current streak: {streak}")