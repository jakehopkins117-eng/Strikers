"""
MLB Stats API service for Strikers.

This module handles all communication with the MLB Stats API,
including schedules, teams, standings, player statistics, team
statistics, and probable starting pitchers.

Identical API requests are cached temporarily to reduce loading times.
"""

from datetime import datetime, timedelta
from typing import Any

import requests

from utils.cache import mlb_cache


BASE_URL = "https://statsapi.mlb.com/api/v1"


def create_cache_key(
    endpoint: str,
    params: dict[str, Any] | None,
) -> str:
    """
    Create a consistent cache key for an MLB API request.

    Sorting the parameters ensures requests containing the same
    information always produce the same cache key.
    """

    if not params:
        return endpoint

    sorted_params = sorted(
        (str(key), str(value))
        for key, value in params.items()
    )

    parameter_string = "&".join(
        f"{key}={value}"
        for key, value in sorted_params
    )

    return f"{endpoint}?{parameter_string}"


def make_request(
    endpoint: str,
    params: dict[str, Any] | None = None,
    cache_seconds: int = 300,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Send a request to the MLB Stats API.

    Identical requests are temporarily stored in memory so Strikers
    does not repeatedly download the same information.

    Args:
        endpoint:
            MLB API endpoint beginning with a forward slash.

        params:
            Optional query parameters sent with the request.

        cache_seconds:
            Number of seconds the response should remain cached.

        force_refresh:
            Ignore cached information and request fresh data.

    Returns:
        MLB API response converted into a Python dictionary.

    Raises:
        ConnectionError:
            The request timed out or Strikers could not connect.

        RuntimeError:
            The MLB API returned an HTTP error or invalid response.
    """

    cache_key = create_cache_key(endpoint, params)

    if not force_refresh:
        cached_data = mlb_cache.get(cache_key)

        if cached_data is not None:
            return cached_data

    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=15,
        )

        response.raise_for_status()
        data = response.json()

    except requests.Timeout as error:
        raise ConnectionError(
            "The MLB API request timed out. Please try again."
        ) from error

    except requests.ConnectionError as error:
        raise ConnectionError(
            "Strikers could not connect to the MLB API."
        ) from error

    except requests.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else "unknown"
        )

        raise RuntimeError(
            f"The MLB API returned error code {status_code}."
        ) from error

    except ValueError as error:
        raise RuntimeError(
            "The MLB API returned information Strikers could not read."
        ) from error

    mlb_cache.set(
        key=cache_key,
        value=data,
        ttl_seconds=cache_seconds,
    )

    return data


def get_today_schedule(
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return today's MLB schedule using the computer's local date.

    Probable pitchers and venue information are included when
    available.

    Schedule information uses a shorter cache because game statuses,
    scores, and probable pitchers can change throughout the day.
    """

    today = datetime.now().astimezone().strftime("%Y-%m-%d")

    return make_request(
        "/schedule",
        params={
            "sportId": 1,
            "date": today,
            "hydrate": "probablePitcher,venue",
        },
        cache_seconds=60,
        force_refresh=force_refresh,
    )


def get_schedule_by_date(
    date_string: str,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return the MLB schedule for a specific date.

    Args:
        date_string:
            Date formatted as YYYY-MM-DD.

        force_refresh:
            Ignore cached information and request fresh data.
    """

    return make_request(
        "/schedule",
        params={
            "sportId": 1,
            "date": date_string,
            "hydrate": "probablePitcher,venue",
        },
        cache_seconds=300,
        force_refresh=force_refresh,
    )


def get_all_teams() -> list[dict[str, Any]]:
    """
    Return all active MLB teams.
    """

    data = make_request(
        "/teams",
        params={
            "sportId": 1,
            "hydrate": "league,division,venue",
        },
        cache_seconds=3600,
    )

    return data.get("teams", [])


def find_team(
    search_term: str,
) -> dict[str, Any] | None:
    """
    Search for an MLB team.

    Teams may be searched by:

    - Full name
    - City
    - Nickname
    - Club name
    - Short name
    - Abbreviation

    Exact matches are checked first, followed by partial matches.
    """

    normalized_search = search_term.strip().lower()

    if not normalized_search:
        return None

    teams = get_all_teams()

    for team in teams:
        possible_names = [
            team.get("name", ""),
            team.get("teamName", ""),
            team.get("clubName", ""),
            team.get("shortName", ""),
            team.get("locationName", ""),
            team.get("abbreviation", ""),
        ]

        normalized_names = [
            str(name).strip().lower()
            for name in possible_names
            if name
        ]

        if normalized_search in normalized_names:
            return team

    for team in teams:
        possible_names = [
            team.get("name", ""),
            team.get("teamName", ""),
            team.get("clubName", ""),
            team.get("shortName", ""),
            team.get("locationName", ""),
            team.get("abbreviation", ""),
        ]

        for name in possible_names:
            if normalized_search in str(name).lower():
                return team

    return None


def get_standings(
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Return the current MLB regular-season standings.
    """

    return make_request(
        "/standings",
        params={
            "leagueId": "103,104",
            "standingsTypes": "regularSeason",
            "hydrate": "team,division",
        },
        cache_seconds=300,
        force_refresh=force_refresh,
    )


def get_team_record(
    team_id: int,
) -> dict[str, Any] | None:
    """
    Return the current standings record for one MLB team.
    """

    data = get_standings()

    for record_group in data.get("records", []):
        team_records = record_group.get("teamRecords", [])

        for team_record in team_records:
            current_team_id = (
                team_record
                .get("team", {})
                .get("id")
            )

            if current_team_id == team_id:
                return team_record

    return None


def search_player(
    player_name: str,
) -> dict[str, Any] | None:
    """
    Search for an MLB player by name.

    An exact full-name match is preferred. If no exact match exists,
    the first result returned by MLB is used.
    """

    normalized_name = player_name.strip()

    if not normalized_name:
        return None

    data = make_request(
        "/people/search",
        params={
            "names": normalized_name,
            "hydrate": "currentTeam",
        },
        cache_seconds=3600,
    )

    people = data.get("people", [])

    if not people:
        return None

    normalized_name_lower = normalized_name.lower()

    for player in people:
        full_name = player.get("fullName", "").lower()

        if full_name == normalized_name_lower:
            return player

    return people[0]


def get_player_stats(
    player_id: int,
) -> dict[str, Any] | None:
    """
    Return a player's current-season hitting statistics.
    """

    data = make_request(
        f"/people/{player_id}/stats",
        params={
            "stats": "season",
            "group": "hitting",
        },
        cache_seconds=600,
    )

    return extract_first_stat_split(data)


def get_pitcher_stats(
    player_id: int,
) -> dict[str, Any] | None:
    """
    Return a pitcher's current-season pitching statistics.
    """

    data = make_request(
        f"/people/{player_id}/stats",
        params={
            "stats": "season",
            "group": "pitching",
        },
        cache_seconds=600,
    )

    return extract_first_stat_split(data)


def get_team_hitting_stats(
    team_id: int,
) -> dict[str, Any] | None:
    """
    Return current-season hitting statistics for one MLB team.
    """

    data = make_request(
        f"/teams/{team_id}/stats",
        params={
            "stats": "season",
            "group": "hitting",
        },
        cache_seconds=600,
    )

    return extract_first_stat_split(data)


def get_team_pitching_stats(
    team_id: int,
) -> dict[str, Any] | None:
    """
    Return current-season pitching statistics for one MLB team.
    """

    data = make_request(
        f"/teams/{team_id}/stats",
        params={
            "stats": "season",
            "group": "pitching",
        },
        cache_seconds=600,
    )

    return extract_first_stat_split(data)


def extract_first_stat_split(
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Extract the first statistical split from an MLB API response.

    MLB statistic responses generally contain:

    stats
        -> first statistics group
            -> splits
                -> first split
                    -> stat
    """

    stats_groups = data.get("stats", [])

    if not stats_groups:
        return None

    first_group = stats_groups[0]
    splits = first_group.get("splits", [])

    if not splits:
        return None

    first_split = splits[0]

    return first_split.get("stat")



def get_team_recent_form(
    team_id: int,
    games: int = 10,
    end_date: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return a team's most recent completed regular-season games."""

    requested_games = max(1, min(int(games), 30))

    if end_date:
        try:
            final_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError("end_date must use YYYY-MM-DD format.") from error
    else:
        final_date = datetime.now().astimezone().date()

    start_date = final_date - timedelta(days=45)

    data = make_request(
        "/schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": final_date.strftime("%Y-%m-%d"),
            "gameType": "R",
            "hydrate": "linescore",
        },
        cache_seconds=300,
        force_refresh=force_refresh,
    )

    completed_games: list[dict[str, Any]] = []

    for date_group in data.get("dates", []):
        for game in date_group.get("games", []):
            status = game.get("status", {})
            coded_state = str(status.get("codedGameState", "")).upper()
            detailed_state = str(status.get("detailedState", "")).lower()
            is_completed = (
                coded_state == "F"
                or "final" in detailed_state
                or "game over" in detailed_state
                or "completed early" in detailed_state
            )
            if is_completed:
                completed_games.append({
                    "game": game,
                    "game_date": str(game.get("gameDate", "")),
                })

    completed_games.sort(key=lambda item: item["game_date"], reverse=True)
    completed_games = completed_games[:requested_games]

    wins = losses = runs_scored = runs_allowed = 0
    game_details: list[dict[str, Any]] = []

    for item in completed_games:
        game = item["game"]
        teams = game.get("teams", {})
        away = teams.get("away", {})
        home = teams.get("home", {})
        away_team_id = away.get("team", {}).get("id")
        home_team_id = home.get("team", {}).get("id")
        away_score = int(away.get("score") or 0)
        home_score = int(home.get("score") or 0)

        if away_team_id == team_id:
            team_score, opponent_score = away_score, home_score
            opponent = home.get("team", {}).get("name", "Unknown")
            location = "away"
        elif home_team_id == team_id:
            team_score, opponent_score = home_score, away_score
            opponent = away.get("team", {}).get("name", "Unknown")
            location = "home"
        else:
            continue

        won = team_score > opponent_score
        wins += int(won)
        losses += int(not won)
        runs_scored += team_score
        runs_allowed += opponent_score
        game_details.append({
            "date": item["game_date"][:10],
            "opponent": opponent,
            "location": location,
            "runs_scored": team_score,
            "runs_allowed": opponent_score,
            "result": "W" if won else "L",
        })

    games_played = wins + losses
    run_differential = runs_scored - runs_allowed

    return {
        "games_played": games_played,
        "wins": wins,
        "losses": losses,
        "win_pct": wins / games_played if games_played else 0.5,
        "runs_scored": runs_scored,
        "runs_allowed": runs_allowed,
        "runs_per_game": runs_scored / games_played if games_played else 0.0,
        "runs_allowed_per_game": runs_allowed / games_played if games_played else 0.0,
        "run_differential": run_differential,
        "run_differential_per_game": run_differential / games_played if games_played else 0.0,
        "games": game_details,
    }

def get_probable_pitchers_for_game(
    game: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Extract probable pitcher information from one schedule game.

    Returns:
        A dictionary containing away and home pitcher information.
    """

    teams = game.get("teams", {})

    away_pitcher = (
        teams
        .get("away", {})
        .get("probablePitcher", {})
    )

    home_pitcher = (
        teams
        .get("home", {})
        .get("probablePitcher", {})
    )

    return {
        "away": {
            "id": away_pitcher.get("id"),
            "name": away_pitcher.get(
                "fullName",
                "Not announced",
            ),
        },
        "home": {
            "id": home_pitcher.get("id"),
            "name": home_pitcher.get(
                "fullName",
                "Not announced",
            ),
        },
    }


def clear_api_cache() -> None:
    """
    Clear every cached MLB API response.

    This may be useful later for a refresh option inside Strikers.
    """

    mlb_cache.clear()


def get_api_cache_size() -> int:
    """
    Return the number of active MLB API responses in the cache.
    """

    return mlb_cache.size()