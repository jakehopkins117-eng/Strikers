"""Live MLB sportsbook odds integration for Strikers v3.5.

The service uses The Odds API v4 and keeps the provider behind a small,
normalized interface so it can be replaced later without touching the rest of
Strikers. One league-wide response is cached in memory to protect API quota.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import requests

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
CACHE_SECONDS = max(60, int(os.getenv("ODDS_CACHE_SECONDS", "300")))
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,williamhill_us,espnbet,betrivers,fanatics"

_CACHE_LOCK = Lock()
_CACHE: dict[str, Any] = {"expires": 0.0, "events": [], "meta": {}}


@dataclass(frozen=True)
class OddsServiceError(RuntimeError):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def _normalize_team(name: str) -> str:
    value = name.lower().strip()
    value = value.replace("d-backs", "diamondbacks").replace("dbacks", "diamondbacks")
    value = value.replace("chi sox", "white sox").replace("chicago sox", "chicago white sox")
    value = value.replace("la angels", "los angeles angels").replace("la dodgers", "los angeles dodgers")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def american_implied(odds: int | float) -> float:
    value = float(odds)
    if value < 0:
        return abs(value) / (abs(value) + 100.0)
    if value > 0:
        return 100.0 / (value + 100.0)
    return 0.5


def american_decimal(odds: int | float) -> float:
    value = float(odds)
    if value < 0:
        return 1.0 + 100.0 / abs(value)
    if value > 0:
        return 1.0 + value / 100.0
    return 2.0


def _provider_request() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        raise OddsServiceError(
            "ODDS_API_KEY is not configured. Add it to your local .env file and restart the backend.",
            status_code=503,
        )

    bookmakers = os.getenv("ODDS_BOOKMAKERS", DEFAULT_BOOKMAKERS).strip()
    params: dict[str, str] = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
        "includeLinks": "true",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    try:
        response = requests.get(ODDS_API_URL, params=params, timeout=20)
    except requests.RequestException as error:
        raise OddsServiceError(f"Odds provider request failed: {error}") from error

    if response.status_code == 401:
        raise OddsServiceError("The Odds API rejected the API key.", status_code=401)
    if response.status_code == 429:
        raise OddsServiceError("The Odds API quota or rate limit was reached.", status_code=429)
    if not response.ok:
        detail = response.text[:240] if response.text else response.reason
        raise OddsServiceError(f"The Odds API returned {response.status_code}: {detail}")

    try:
        data = response.json()
    except ValueError as error:
        raise OddsServiceError("The Odds API returned invalid JSON.") from error
    if not isinstance(data, list):
        raise OddsServiceError("The Odds API response was not an event list.")

    meta = {
        "remaining_requests": response.headers.get("x-requests-remaining"),
        "used_requests": response.headers.get("x-requests-used"),
        "last_request_cost": response.headers.get("x-requests-last"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_seconds": CACHE_SECONDS,
    }
    return data, meta


def get_mlb_odds(*, force: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = time.time()
    with _CACHE_LOCK:
        if not force and _CACHE["events"] and now < float(_CACHE["expires"]):
            meta = dict(_CACHE["meta"])
            meta["cached"] = True
            return list(_CACHE["events"]), meta

    events, meta = _provider_request()
    with _CACHE_LOCK:
        _CACHE["events"] = events
        _CACHE["meta"] = meta
        _CACHE["expires"] = now + CACHE_SECONDS
    meta = dict(meta)
    meta["cached"] = False
    return events, meta


def _market_outcomes(bookmaker: dict[str, Any], market_key: str) -> list[dict[str, Any]]:
    for market in bookmaker.get("markets", []):
        if market.get("key") == market_key:
            return market.get("outcomes", []) or []
    return []


def _best_price(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    # With American odds, the numerically largest value is always the most
    # favorable price: +130 beats +120, and -105 beats -115.
    return max(rows, key=lambda row: float(row["odds"]))


def _build_moneyline(event: dict[str, Any], away_team: str, home_team: str) -> dict[str, Any]:
    teams = {away_team: [], home_team: []}
    books: list[dict[str, Any]] = []

    for bookmaker in event.get("bookmakers", []):
        outcomes = _market_outcomes(bookmaker, "h2h")
        row: dict[str, Any] = {
            "key": bookmaker.get("key"),
            "name": bookmaker.get("title") or bookmaker.get("key"),
            "last_update": bookmaker.get("last_update"),
            "link": bookmaker.get("link"),
            "away_odds": None,
            "home_odds": None,
        }
        for outcome in outcomes:
            outcome_name = str(outcome.get("name", ""))
            price = outcome.get("price")
            if price is None:
                continue
            if _normalize_team(outcome_name) == _normalize_team(away_team):
                row["away_odds"] = int(price)
                teams[away_team].append({"bookmaker": row["name"], "bookmaker_key": row["key"], "odds": int(price), "last_update": row["last_update"], "link": row["link"]})
            elif _normalize_team(outcome_name) == _normalize_team(home_team):
                row["home_odds"] = int(price)
                teams[home_team].append({"bookmaker": row["name"], "bookmaker_key": row["key"], "odds": int(price), "last_update": row["last_update"], "link": row["link"]})
        if row["away_odds"] is not None or row["home_odds"] is not None:
            books.append(row)

    consensus: dict[str, float | None] = {}
    for team, prices in teams.items():
        probabilities = [american_implied(item["odds"]) for item in prices]
        consensus[team] = round(sum(probabilities) / len(probabilities) * 100.0, 2) if probabilities else None

    # Remove the two-way overround from the consensus when both sides exist.
    away_raw = consensus.get(away_team)
    home_raw = consensus.get(home_team)
    fair: dict[str, float | None] = {away_team: None, home_team: None}
    if away_raw is not None and home_raw is not None and away_raw + home_raw > 0:
        total = away_raw + home_raw
        fair[away_team] = round(away_raw / total * 100.0, 2)
        fair[home_team] = round(home_raw / total * 100.0, 2)

    return {
        "bookmakers": books,
        "away": {
            "team": away_team,
            "best": _best_price(teams[away_team]),
            "consensus_implied_probability": consensus.get(away_team),
            "fair_market_probability": fair.get(away_team),
            "prices": teams[away_team],
        },
        "home": {
            "team": home_team,
            "best": _best_price(teams[home_team]),
            "consensus_implied_probability": consensus.get(home_team),
            "fair_market_probability": fair.get(home_team),
            "prices": teams[home_team],
        },
    }


def _build_spreads(event: dict[str, Any], away_team: str, home_team: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bookmaker in event.get("bookmakers", []):
        for outcome in _market_outcomes(bookmaker, "spreads"):
            name = str(outcome.get("name", ""))
            if _normalize_team(name) not in {_normalize_team(away_team), _normalize_team(home_team)}:
                continue
            rows.append({
                "bookmaker": bookmaker.get("title") or bookmaker.get("key"),
                "team": name,
                "point": outcome.get("point"),
                "odds": outcome.get("price"),
                "last_update": bookmaker.get("last_update"),
            })
    return rows


def _build_totals(event: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bookmaker in event.get("bookmakers", []):
        for outcome in _market_outcomes(bookmaker, "totals"):
            rows.append({
                "bookmaker": bookmaker.get("title") or bookmaker.get("key"),
                "side": outcome.get("name"),
                "point": outcome.get("point"),
                "odds": outcome.get("price"),
                "last_update": bookmaker.get("last_update"),
            })
    return rows


def get_matchup_odds(away_team: str, home_team: str, *, force: bool = False) -> dict[str, Any]:
    try:
        events, meta = get_mlb_odds(force=force)
    except OddsServiceError as error:
        return {
            "available": False,
            "status": "configuration_required" if error.status_code == 503 else "provider_error",
            "message": str(error),
            "provider": "The Odds API",
            "moneyline": None,
            "spreads": [],
            "totals": [],
            "meta": {},
        }

    away_key = _normalize_team(away_team)
    home_key = _normalize_team(home_team)
    event = next(
        (
            item for item in events
            if _normalize_team(str(item.get("away_team", ""))) == away_key
            and _normalize_team(str(item.get("home_team", ""))) == home_key
        ),
        None,
    )
    if event is None:
        return {
            "available": False,
            "status": "no_market",
            "message": "No matching live sportsbook market was found for this matchup.",
            "provider": "The Odds API",
            "moneyline": None,
            "spreads": [],
            "totals": [],
            "meta": meta,
        }

    moneyline = _build_moneyline(event, away_team, home_team)
    has_moneyline = bool(moneyline["away"]["prices"] or moneyline["home"]["prices"])
    return {
        "available": has_moneyline,
        "status": "ready" if has_moneyline else "no_moneyline",
        "message": "Live sportsbook prices loaded." if has_moneyline else "The event is available, but no moneyline prices were returned.",
        "provider": "The Odds API",
        "event_id": event.get("id"),
        "commence_time": event.get("commence_time"),
        "last_update": max((str(book.get("last_update") or "") for book in event.get("bookmakers", [])), default=None),
        "moneyline": moneyline,
        "spreads": _build_spreads(event, away_team, home_team),
        "totals": _build_totals(event),
        "meta": meta,
    }


def odds_status() -> dict[str, Any]:
    configured = bool(os.getenv("ODDS_API_KEY", "").strip())
    with _CACHE_LOCK:
        cached_events = len(_CACHE["events"])
        cache_valid = bool(cached_events and time.time() < float(_CACHE["expires"]))
        meta = dict(_CACHE["meta"])
    return {
        "provider": "The Odds API",
        "configured": configured,
        "cache_valid": cache_valid,
        "cached_events": cached_events,
        "cache_seconds": CACHE_SECONDS,
        "remaining_requests": meta.get("remaining_requests"),
        "last_fetched_at": meta.get("fetched_at"),
    }
