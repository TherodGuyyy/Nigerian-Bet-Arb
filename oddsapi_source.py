"""
Wrapper for The Odds API (the-odds-api.com — NOT theoddsapi.com, a different,
unrelated service with a similar name).

Built against their documented v4 schema. NOTE: I built this from their
public documentation and code samples, not a live test against a real API
key (no network access in the environment this was built in) — the
response SHAPE below is accurate per their docs, but treat the first real
run as the actual confirmation, same as with the other bots.

Response shape (v4 /sports/{sport}/odds endpoint):
[
  {
    "id": "...",
    "commence_time": "2026-08-01T15:00:00Z",
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "bookmakers": [
      {
        "key": "betway", "title": "Betway",
        "markets": [
          {
            "key": "h2h",
            "outcomes": [
              {"name": "Arsenal", "price": 2.1},   # named by TEAM, not "home"
              {"name": "Chelsea", "price": 3.4},
              {"name": "Draw", "price": 3.3}
            ]
          }
        ]
      }
    ]
  }
]

Important: outcomes are labeled by team name (or literally "Draw"), not by
"home"/"away" — this wrapper converts that into the home/draw/away shape
the rest of this bot expects, using the event's own home_team/away_team
fields to know which name means which side.
"""

import logging
import requests

log = logging.getLogger("oddsapi_source")

BASE_URL = "https://api.the-odds-api.com/v4"

# 1xBet and Betway both show up under UK/EU-region bookmaker coverage.
REGIONS = "uk,eu"
BOOKMAKER_KEYS = "onexbet,betway"  # per The Odds API's bookmaker key naming
# NOTE: verify these exact keys against a real API response — bookmaker key
# naming conventions (e.g. "onexbet" vs "1xbet") aren't fully confirmed
# without a live call. If a key is wrong, that bookmaker just won't show up
# in results (fails quietly, not with an error) — worth checking manually
# once you have a real API key by hitting the /v4/sports/{sport}/odds
# endpoint without the bookmakers filter and seeing what keys come back.


# Curated league list — lower-profile leagues (less bookmaker attention,
# more likely to have pricing gaps) that are actually in season right now.
# NOT dynamically discovered — The Odds API's free tier is capped at 500
# CREDITS/month (not 500 requests; cost = markets × regions per call), so
# casting a wide net across every league blows the budget fast.
FOOTBALL_LEAGUE_KEYS = [
    "soccer_norway_eliteserien",
    "soccer_sweden_superettan",
    "soccer_faroe_islands_premier_league",
    "soccer_iceland_urvalsdeild",
    "soccer_finland_veikkausliiga",
]
# NOTE: verify these exact key strings against a real account once you have
# one — call get_available_sport_keys("Soccer") once manually and check
# these match. Same "confirm before trusting" situation as the bookmaker
# keys earlier in this project.


class OddsApiSource:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ODDS_API_KEY is not set.")
        self.api_key = api_key

    def get_available_sport_keys(self, group_filter: str) -> list[str]:
        """
        Calls /v4/sports to discover every league The Odds API currently
        supports, filtered by group (e.g. "Soccer" or "Basketball"). Used
        for basketball (small enough league count to fetch dynamically) —
        football uses the curated FOOTBALL_LEAGUE_KEYS list instead, to
        stay within the credit budget.
        """
        url = f"{BASE_URL}/sports"
        resp = requests.get(url, params={"apiKey": self.api_key}, timeout=15)
        resp.raise_for_status()
        sports = resp.json()
        return [s["key"] for s in sports if s.get("group") == group_filter]

    def fetch_matches(self, sport_keys: list[str] = None) -> list[dict]:
        """
        Returns matches across the given sport_keys. Defaults to
        FOOTBALL_LEAGUE_KEYS (the curated, budget-safe list) rather than
        discovering every league — pass an explicit list (e.g. the
        basketball bot passes its own) to override.
        """
        if sport_keys is None:
            sport_keys = FOOTBALL_LEAGUE_KEYS

        all_results = []
        for sport_key in sport_keys:
            all_results.extend(self._fetch_one_league(sport_key))
        return all_results

    def _fetch_one_league(self, sport_key: str) -> list[dict]:
        url = f"{BASE_URL}/sports/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": REGIONS,
            "markets": "h2h",
            "bookmakers": BOOKMAKER_KEYS,
            "oddsFormat": "decimal",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        events = resp.json()

        results = []
        for event in events:
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            if not home_team or not away_team:
                log.warning("Event missing home_team/away_team, skipping: %s", event.get("id"))
                continue

            odds_by_bookmaker = {}
            for bm in event.get("bookmakers", []):
                bm_key = bm.get("key")
                h2h = next((m for m in bm.get("markets", []) if m.get("key") == "h2h"), None)
                if not h2h:
                    continue

                prices = {}
                for outcome in h2h.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    if name == home_team:
                        prices["home"] = price
                    elif name == away_team:
                        prices["away"] = price
                    elif name == "Draw":
                        prices["draw"] = price
                    else:
                        log.warning(
                            "Unrecognized outcome name '%s' for match %s vs %s — "
                            "doesn't match home/away team names or 'Draw'.",
                            name, home_team, away_team,
                        )

                if prices:
                    odds_by_bookmaker[bm_key] = prices

            if odds_by_bookmaker:
                results.append({
                    "match_label": f"{home_team} vs {away_team}",
                    "home_team": home_team,
                    "away_team": away_team,
                    "commence_time": event.get("commence_time"),
                    "odds_by_bookmaker": odds_by_bookmaker,
                })

        return results
