from api.mlb_api import get_player_stats, search_player


def display_player_search():
    player_name = input(
        "\nEnter a player's full name: "
    ).strip()

    if not player_name:
        print("\nPlease enter a player name.")
        return

    print("\nSearching for player...")

    try:
        player = search_player(player_name)
    except Exception as error:
        print(f"\nPlayer search failed: {error}")
        return

    if player is None:
        print("\nNo MLB player was found.")
        print("Try Aaron Judge or Shohei Ohtani.")
        return

    full_name = player.get("fullName", "Unknown")
    player_id = player.get("id")
    position = player.get(
        "primaryPosition",
        {},
    ).get("abbreviation", "Unknown")
    current_team = player.get(
        "currentTeam",
        {},
    ).get("name", "Unknown")

    print("\nLoading season statistics...")

    try:
        stats = get_player_stats(player_id)
    except Exception as error:
        print(f"\nPlayer statistics lookup failed: {error}")
        return

    print("\n" + "=" * 45)
    print(full_name.upper())
    print("=" * 45)
    print(f"Team:     {current_team}")
    print(f"Position: {position}")

    if stats is None:
        print("\nNo current hitting statistics were found.")
        return

    print("\nSeason Hitting Statistics")
    print("-" * 45)
    print(f"Games:       {stats.get('gamesPlayed', 0)}")
    print(f"At-bats:     {stats.get('atBats', 0)}")
    print(f"Hits:        {stats.get('hits', 0)}")
    print(f"Runs:        {stats.get('runs', 0)}")
    print(f"Home runs:   {stats.get('homeRuns', 0)}")
    print(f"RBI:         {stats.get('rbi', 0)}")
    print(f"Walks:       {stats.get('baseOnBalls', 0)}")
    print(f"Strikeouts:  {stats.get('strikeOuts', 0)}")
    print(f"AVG:         {stats.get('avg', '.000')}")
    print(f"OBP:         {stats.get('obp', '.000')}")
    print(f"SLG:         {stats.get('slg', '.000')}")
    print(f"OPS:         {stats.get('ops', '.000')}")