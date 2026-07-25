"""
Wrapper for Bet9ja and NairaBet odds via the NaijaBet_Api library
(https://github.com/jayteealao/NaijaBet_Api, also on PyPI as NaijaBet-Api).

IMPORTANT — read this: this is an UNOFFICIAL third-party library that
accesses Bet9ja/NairaBet's own internal endpoints directly. It is NOT an
API these bookmakers publish or document themselves. That means:
  - it could break without warning if either site changes their backend
  - automated access like this is likely outside what their terms of
    service intend, even though this only reads public odds (no login,
    no account access, no bet placement)
Treat it as a genuinely useful but fragile data source, not a stable
guarantee — worth checking on periodically to confirm it's still working.

NOTE ON IMPORT STYLE: the library's own docs show two slightly different
import patterns in different places (GitHub README vs PyPI page), which
suggests some version drift. This is written against the GitHub README's
version. If `pip install NaijaBet-Api` gives you an ImportError on the line
below, check what's actually importable with:
    python3 -c "import NaijaBet_Api; help(NaijaBet_Api)"
and tell me what it shows — quick fix once we see the real package layout.

Confirmed response shape (from the library's own docs) — each match is a
dict already in exactly the shape arbitrage.py wants:
    {'home': 4.0, 'draw': 3.75, 'away': 1.92, 'match': 'Brentford FC - Arsenal FC',
     'match_id': 4467373, 'league': 'Premier League', 'time': 1628881200000}
"""

import logging

log = logging.getLogger("bet9ja_nairabet_source")


class Bet9jaNairabetSource:
    def __init__(self):
        try:
            from NaijaBet_Api.bookmakers import Bet9ja, Nairabet
        except ImportError as e:
            raise ImportError(
                "Couldn't import NaijaBet_Api as expected. Run "
                "`python3 -c \"import NaijaBet_Api; help(NaijaBet_Api)\"` "
                "to see the real package layout and tell me what it shows — "
                "the import style may differ from what this was built against."
            ) from e
        self._bet9ja = Bet9ja()
        self._nairabet = Nairabet()

    def fetch_matches(self) -> list[dict]:
        """
        Returns matches from both bookmakers, converted into this bot's
        common shape: [{"match_label": ..., "odds_by_bookmaker": {...}}]
        Matches appearing on both sites are merged into one entry so the
        arbitrage check can compare them directly without needing the
        cross-source match_matcher for this pair (same naming convention,
        since both come through the same library).
        """
        merged: dict[str, dict] = {}  # keyed by normalized match label

        for bookmaker_key, client in (("bet9ja", self._bet9ja), ("nairabet", self._nairabet)):
            try:
                raw_matches = client.get_all()
            except Exception as e:
                log.error("Failed to fetch from %s: %s", bookmaker_key, e)
                continue

            for m in raw_matches:
                label = m.get("match")
                if not label or "home" not in m or "draw" not in m or "away" not in m:
                    continue  # incomplete entry, skip rather than guess

                key = label.strip().lower()
                if key not in merged:
                    merged[key] = {
                        "match_label": label,
                        "match_time": m.get("time"),
                        "odds_by_bookmaker": {},
                    }
                merged[key]["odds_by_bookmaker"][bookmaker_key] = {
                    "home": m["home"],
                    "draw": m["draw"],
                    "away": m["away"],
                }

        return list(merged.values())
