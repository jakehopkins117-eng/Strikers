from api.mlb_api import get_today_schedule
from utils.formatting import format_game_time


def get_probable_pitcher(game, team_type):
    """
    Return the probable pitcher information for the selected team.

    team_type should be either "away" or "home".
    """

    team_data = game.get("teams", {}).get(team_type, {})
    pitcher = team_data.get("probablePitcher")

    if not pitcher:
        return {
            "id": None,
            "name": "Not announced",
        }

    return {
        "id": pitcher.get("id"),
        "name": pitcher.get("fullName", "Not announced"),
    }


def display_game_score(game, away_team, home_team, status):
    """
    Display the score when a game has started or finished.
    """

    if status == "Scheduled":
        return

    away_score = (
        game.get("teams", {})
        .get("away", {})
        .get("score", 0)
    )

    home_score = (
        game.get("teams", {})
        .get("home", {})
        .get("score", 0)
    )

    print(
        f"   Score: {away_team} {away_score} - "
        f"{home_team} {home_score}"
    )


def display_today_games():
    """
    Load and display today's MLB games and probable pitchers.
    """

    print("\nConnecting to the MLB API...")

    try:
        data = get_today_schedule()
    except Exception as error:
        print(f"\nConnection failed: {error}")
        return

    dates = data.get("dates", [])

    if not dates:
        print("\nThere are no MLB games scheduled today.")
        return

    games = dates[0].get("games", [])

    if not games:
        print("\nThere are no MLB games scheduled today.")
        return

    print("\n" + "=" * 70)
    print(f"TODAY'S MLB GAMES: {len(games)}")
    print("=" * 70)

    for game_number, game in enumerate(games, start=1):
        teams = game.get("teams", {})

        away_team = (
            teams.get("away", {})
            .get("team", {})
            .get("name", "Unknown Away Team")
        )

        home_team = (
            teams.get("home", {})
            .get("team", {})
            .get("name", "Unknown Home Team")
        )

        status = (
            game.get("status", {})
            .get("detailedState", "Unknown")
        )

        game_date = game.get("gameDate")

        if game_date:
            start_time = format_game_time(game_date)
        else:
            start_time = "Unknown"

        venue = (
            game.get("venue", {})
            .get("name", "Venue unavailable")
        )

        away_pitcher = get_probable_pitcher(game, "away")
        home_pitcher = get_probable_pitcher(game, "home")

        print(f"\n{game_number}. {away_team} @ {home_team}")
        print("-" * 70)
        print(f"   Time:   {start_time}")
        print(f"   Status: {status}")
        print(f"   Venue:  {venue}")

        display_game_score(
            game,
            away_team,
            home_team,
            status,
        )

        print("\n   Probable Starting Pitchers")
        print(f"   Away: {away_pitcher['name']}")
        print(f"   Home: {home_pitcher['name']}")

    print("\n" + "=" * 70)