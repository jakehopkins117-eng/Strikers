"""Live MLB player-prop odds for Strikers Sprint 19.1.

The Odds API exposes player props through the event-level odds endpoint. This
module keeps those calls cached on disk and in memory so normal page refreshes
do not repeatedly consume API credits.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import requests

from services.odds import OddsServiceError, get_mlb_odds

SPORT_KEY = "baseball_mlb"
EVENT_ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/events/{{event_id}}/odds"
DEFAULT_MARKETS = (
    "batter_hits,batter_total_bases,batter_home_runs,batter_rbis,"
    "pitcher_strikeouts,pitcher_outs,pitcher_earned_runs"
)
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,williamhill_us,espnbet,betrivers,fanatics"
CACHE_SECONDS = max(300, int(os.getenv("PROP_ODDS_CACHE_SECONDS", "1800")))
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "prop_odds_cache.json"

MARKET_LABELS = {
    "batter_hits": "Hits",
    "batter_total_bases": "Total Bases",
    "batter_home_runs": "Home Runs",
    "batter_rbis": "RBIs",
    "batter_runs_scored": "Runs Scored",
    "batter_walks": "Walks",
    "batter_strikeouts": "Batter Strikeouts",
    "batter_stolen_bases": "Stolen Bases",
    "pitcher_strikeouts": "Pitcher Strikeouts",
    "pitcher_outs": "Pitcher Outs",
    "pitcher_earned_runs": "Earned Runs",
    "pitcher_hits_allowed": "Hits Allowed",
    "pitcher_walks": "Pitcher Walks",
}

_CACHE_LOCK = Lock()
_MEMORY_CACHE: dict[str, Any] = {"events": {}}


def _configured_markets() -> list[str]:
    raw = os.getenv("PROP_ODDS_MARKETS", DEFAULT_MARKETS)
    return [value.strip() for value in raw.split(",") if value.strip()]


def _configured_bookmakers() -> str:
    return os.getenv("ODDS_BOOKMAKERS", DEFAULT_BOOKMAKERS).strip()


def _read_disk_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"events": {}}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"events": {}}
    except (OSError, json.JSONDecodeError):
        return {"events": {}}


def _write_disk_cache(payload: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def _load_cache() -> dict[str, Any]:
    with _CACHE_LOCK:
        if not _MEMORY_CACHE.get("loaded"):
            disk = _read_disk_cache()
            _MEMORY_CACHE.clear()
            _MEMORY_CACHE.update(disk)
            _MEMORY_CACHE.setdefault("events", {})
            _MEMORY_CACHE["loaded"] = True
        return _MEMORY_CACHE


def _event_cache_key(event_id: str, markets: list[str]) -> str:
    return f"{event_id}|{','.join(sorted(markets))}"


def _request_event_props(event_id: str, markets: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        raise OddsServiceError(
            "ODDS_API_KEY is not configured. Add it to your local .env file and restart the backend.",
            status_code=503,
        )

    params: dict[str, str] = {
        "apiKey": api_key,
        "regions": "us",
        "markets": ",".join(markets),
        "oddsFormat": "american",
        "dateFormat": "iso",
        "includeLinks": "true",
    }
    bookmakers = _configured_bookmakers()
    if bookmakers:
        params["bookmakers"] = bookmakers

    try:
        response = requests.get(EVENT_ODDS_URL.format(event_id=event_id), params=params, timeout=25)
    except requests.RequestException as error:
        raise OddsServiceError(f"Player-prop odds request failed: {error}") from error

    if response.status_code == 401:
        raise OddsServiceError("The Odds API rejected the API key.", status_code=401)
    if response.status_code == 404:
        raise OddsServiceError("The sportsbook event is no longer available.", status_code=404)
    if response.status_code == 422:
        detail = response.text[:400] if response.text else "Unsupported player-prop market request."
        raise OddsServiceError(f"The Odds API rejected one or more prop markets: {detail}", status_code=422)
    if response.status_code == 429:
        raise OddsServiceError("The Odds API quota or rate limit was reached.", status_code=429)
    if not response.ok:
        detail = response.text[:400] if response.text else response.reason
        raise OddsServiceError(f"The Odds API returned {response.status_code}: {detail}")

    try:
        payload = response.json()
    except ValueError as error:
        raise OddsServiceError("The Odds API returned invalid player-prop JSON.") from error
    if not isinstance(payload, dict):
        raise OddsServiceError("The Odds API player-prop response was not an event object.")

    meta = {
        "remaining_requests": response.headers.get("x-requests-remaining"),
        "used_requests": response.headers.get("x-requests-used"),
        "last_request_cost": response.headers.get("x-requests-last"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_seconds": CACHE_SECONDS,
    }
    return payload, meta


def get_event_prop_odds(event_id: str, *, force: bool = False, markets: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = markets or _configured_markets()
    key = _event_cache_key(event_id, requested)
    now = time.time()
    cache = _load_cache()

    with _CACHE_LOCK:
        entry = (cache.get("events") or {}).get(key)
        if not force and isinstance(entry, dict) and now < float(entry.get("expires_at", 0)):
            meta = dict(entry.get("meta") or {})
            meta["cached"] = True
            return dict(entry.get("payload") or {}), meta

    payload, meta = _request_event_props(event_id, requested)
    with _CACHE_LOCK:
        cache.setdefault("events", {})[key] = {
            "event_id": event_id,
            "markets": requested,
            "expires_at": now + CACHE_SECONDS,
            "payload": payload,
            "meta": meta,
        }
        cache["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_disk_cache({k: v for k, v in cache.items() if k != "loaded"})

    result_meta = dict(meta)
    result_meta["cached"] = False
    return payload, result_meta


def _normalize_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"over", "under", "yes", "no"}:
        return text.upper()
    return str(value or "").strip()


def _normalize_event(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    offers: list[dict[str, Any]] = []
    market_counts: dict[str, int] = {}
    bookmakers_seen: set[str] = set()

    for bookmaker in payload.get("bookmakers", []) or []:
        book_key = str(bookmaker.get("key") or "")
        book_name = str(bookmaker.get("title") or book_key)
        bookmakers_seen.add(book_name)
        for market in bookmaker.get("markets", []) or []:
            market_key = str(market.get("key") or "")
            market_counts[market_key] = market_counts.get(market_key, 0) + 1
            for outcome in market.get("outcomes", []) or []:
                player = str(outcome.get("description") or outcome.get("name") or "").strip()
                side = _normalize_side(outcome.get("name"))
                price = outcome.get("price")
                if not player or price is None:
                    continue
                offers.append({
                    "event_id": payload.get("id"),
                    "commence_time": payload.get("commence_time"),
                    "away_team": payload.get("away_team"),
                    "home_team": payload.get("home_team"),
                    "player": player,
                    "market_key": market_key,
                    "market": MARKET_LABELS.get(market_key, market_key.replace("_", " ").title()),
                    "side": side,
                    "line": outcome.get("point"),
                    "odds": int(price),
                    "bookmaker_key": book_key,
                    "bookmaker": book_name,
                    "bookmaker_link": bookmaker.get("link"),
                    "last_update": market.get("last_update") or bookmaker.get("last_update"),
                })

    return {
        "event_id": payload.get("id"),
        "commence_time": payload.get("commence_time"),
        "away_team": payload.get("away_team"),
        "home_team": payload.get("home_team"),
        "offers": offers,
        "offer_count": len(offers),
        "market_counts": market_counts,
        "bookmakers": sorted(bookmakers_seen),
        "meta": meta,
    }


def get_live_player_props(*, date: str | None = None, event_id: str | None = None, force: bool = False, max_events: int = 15) -> dict[str, Any]:
    try:
        events, event_meta = get_mlb_odds(force=force)
    except OddsServiceError as error:
        return {
            "available": False,
            "status": "configuration_required" if error.status_code == 503 else "provider_error",
            "message": str(error),
            "provider": "The Odds API",
            "events": [],
            "offers": [],
            "meta": {},
        }

    selected = events
    if event_id:
        selected = [event for event in events if str(event.get("id")) == event_id]
    elif date:
        selected = [event for event in events if str(event.get("commence_time") or "")[:10] == date]
    selected = selected[:max_events]

    normalized_events: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    last_meta: dict[str, Any] = {}
    for event in selected:
        current_id = str(event.get("id") or "")
        if not current_id:
            continue
        try:
            payload, meta = get_event_prop_odds(current_id, force=force)
            normalized_events.append(_normalize_event(payload, meta))
            last_meta = meta
        except OddsServiceError as error:
            errors.append({"event_id": current_id, "message": str(error)})

    offers = [offer for event in normalized_events for offer in event["offers"]]
    return {
        "available": bool(offers),
        "status": "ready" if offers else "no_markets",
        "message": "Live player-prop prices loaded." if offers else "No live player-prop prices were returned for the selected games.",
        "provider": "The Odds API",
        "date": date,
        "event_count": len(normalized_events),
        "offer_count": len(offers),
        "markets_requested": _configured_markets(),
        "events": normalized_events,
        "offers": offers,
        "errors": errors,
        "meta": {**event_meta, **last_meta},
    }


def prop_odds_status() -> dict[str, Any]:
    cache = _load_cache()
    events = cache.get("events") or {}
    now = time.time()
    valid = sum(1 for entry in events.values() if now < float((entry or {}).get("expires_at", 0)))
    return {
        "provider": "The Odds API",
        "configured": bool(os.getenv("ODDS_API_KEY", "").strip()),
        "markets": _configured_markets(),
        "cache_seconds": CACHE_SECONDS,
        "cache_path": str(CACHE_PATH),
        "cached_event_requests": len(events),
        "valid_cached_event_requests": valid,
        "updated_at": cache.get("updated_at"),
        "version": "19.1",
    }
