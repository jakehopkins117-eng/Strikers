"""Keyless weather intelligence using Open-Meteo."""
from __future__ import annotations
from datetime import datetime
from typing import Any
import requests

VENUES = {
    "Yankee Stadium": (40.8296, -73.9262), "Fenway Park": (42.3467, -71.0972), "Oriole Park at Camden Yards": (39.2838, -76.6217),
    "Rogers Centre": (43.6414, -79.3894), "George M. Steinbrenner Field": (27.9799, -82.5067), "Tropicana Field": (27.7682, -82.6534),
    "Guaranteed Rate Field": (41.8300, -87.6338), "Progressive Field": (41.4962, -81.6852), "Comerica Park": (42.3390, -83.0485),
    "Kauffman Stadium": (39.0517, -94.4803), "Target Field": (44.9817, -93.2776), "Daikin Park": (29.7573, -95.3555),
    "Angel Stadium": (33.8003, -117.8827), "Oakland Coliseum": (37.7516, -122.2005), "T-Mobile Park": (47.5914, -122.3325),
    "Globe Life Field": (32.7473, -97.0847), "Truist Park": (33.8907, -84.4677), "loanDepot park": (25.7781, -80.2197),
    "Citi Field": (40.7571, -73.8458), "Citizens Bank Park": (39.9061, -75.1665), "Nationals Park": (38.8730, -77.0074),
    "Wrigley Field": (41.9484, -87.6553), "Great American Ball Park": (39.0979, -84.5082), "American Family Field": (43.0280, -87.9712),
    "PNC Park": (40.4469, -80.0057), "Busch Stadium": (38.6226, -90.1928), "Chase Field": (33.4455, -112.0667),
    "Coors Field": (39.7559, -104.9942), "Dodger Stadium": (34.0739, -118.2400), "Petco Park": (32.7076, -117.1570), "Oracle Park": (37.7786, -122.3893)
}
INDOOR = {"Rogers Centre", "Tropicana Field", "Daikin Park", "Globe Life Field", "loanDepot park", "American Family Field", "Chase Field"}

def weather_for_game(game: dict[str, Any]) -> dict[str, Any]:
    venue = game.get("venue") or "Unknown venue"
    if venue in INDOOR:
        return {"game_pk": game.get("game_pk"), "venue": venue, "indoor": True, "available": True, "impact": "Neutral", "impact_score": 0, "summary": "Climate-controlled venue; minimal weather impact."}
    coords = VENUES.get(venue)
    if not coords:
        return {"game_pk": game.get("game_pk"), "venue": venue, "indoor": False, "available": False, "impact": "Unknown", "impact_score": 0, "summary": "Venue coordinates are not configured."}
    game_time = datetime.fromisoformat(str(game.get("game_date", "")).replace("Z", "+00:00"))
    params = {"latitude": coords[0], "longitude": coords[1], "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m", "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "timezone": "UTC", "forecast_days": 7}
    try:
        payload = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=12).json()
        times = payload.get("hourly", {}).get("time", [])
        target = game_time.strftime("%Y-%m-%dT%H:00")
        idx = min(range(len(times)), key=lambda i: abs(datetime.fromisoformat(times[i]).replace(tzinfo=game_time.tzinfo)-game_time)) if times else -1
        if idx < 0: raise ValueError("No hourly forecast")
        hourly = payload["hourly"]
        temp = float(hourly["temperature_2m"][idx]); rain = float(hourly["precipitation_probability"][idx] or 0); wind = float(hourly["wind_speed_10m"][idx]); gust = float(hourly["wind_gusts_10m"][idx])
        score = 0
        notes=[]
        if temp >= 85: score += 2; notes.append("hot air can help carry")
        elif temp <= 50: score -= 2; notes.append("cool air can suppress offense")
        if wind >= 15: score += 1; notes.append("strong wind adds volatility")
        if rain >= 50: score -= 1; notes.append("delay or postponement risk")
        impact = "Hitter friendly" if score >= 2 else "Pitcher friendly" if score <= -2 else "Volatile" if wind >= 15 or rain >= 50 else "Neutral"
        return {"game_pk": game.get("game_pk"), "venue": venue, "indoor": False, "available": True, "temperature_f": round(temp), "precipitation_probability": round(rain), "wind_mph": round(wind), "gust_mph": round(gust), "impact": impact, "impact_score": score, "summary": "; ".join(notes).capitalize() if notes else "No major weather edge detected."}
    except Exception as exc:
        return {"game_pk": game.get("game_pk"), "venue": venue, "indoor": False, "available": False, "impact": "Unknown", "impact_score": 0, "summary": f"Forecast unavailable: {exc}"}
