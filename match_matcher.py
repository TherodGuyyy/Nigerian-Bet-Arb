"""
Matches the same real-world football match across two differently-shaped
data sources:
  - bet9ja_nairabet_source: match_label like "Arsenal FC - Chelsea FC",
    match_time in unix milliseconds
  - oddsapi_source: separate home_team/away_team like "Arsenal"/"Chelsea",
    commence_time as an ISO 8601 string

This is the fragile part of the whole system — team names get abbreviated,
suffixed, or spelled differently across sources. This uses:
  1. Name normalization (strip common suffixes, lowercase, punctuation)
  2. Fuzzy string similarity (difflib, stdlib — no extra dependency)
  3. Kickoff time proximity as a confirming signal, not a hard requirement
     (since one source's timestamp could be slightly off or missing)

A match is only paired if BOTH team names clear the similarity threshold —
matching only one side risks pairing two different matches that happen to
share one team name (e.g. "Arsenal vs Chelsea" and "Arsenal vs Fulham" both
have "Arsenal").
"""

import re
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional

log = logging.getLogger("match_matcher")

# Only strip suffixes that are genuinely redundant across ALL club names —
# NOT words like "united"/"city"/"town"/"county" which are often part of
# what distinguishes one club from another (Manchester United vs Manchester
# City, Leicester City, Stoke City, etc. — stripping these would make
# different clubs look identical to the matcher, which is dangerous for a
# bot deciding where to place real money).
_NOISE_WORDS = {"fc", "afc", "cf", "sc"}

NAME_SIMILARITY_THRESHOLD = 0.65  # 0-1, per team name
TIME_TOLERANCE_HOURS = 4.0        # allow this much drift between sources


def normalize_team_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)  # strip punctuation
    words = []
    for w in name.split():
        if w in _NOISE_WORDS:
            continue
        if w == "utd":
            w = "united"  # same word, common abbreviation — normalize, don't drop
        words.append(w)
    return " ".join(words) if words else name  # don't reduce to nothing


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_team_name(a), normalize_team_name(b)).ratio()


def _parse_naijabet_label(label: str) -> Optional[tuple[str, str]]:
    """'Arsenal FC - Chelsea FC' -> ('Arsenal FC', 'Chelsea FC')"""
    parts = label.split(" - ")
    if len(parts) != 2:
        return None
    return parts[0].strip(), parts[1].strip()


def _time_diff_hours(naijabet_time_ms: Optional[int], iso_time: Optional[str]) -> Optional[float]:
    if naijabet_time_ms is None or not iso_time:
        return None
    try:
        t1 = datetime.fromtimestamp(naijabet_time_ms / 1000, tz=timezone.utc)
        t2 = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return abs((t1 - t2).total_seconds()) / 3600.0
    except (ValueError, TypeError, OSError):
        return None


def match_across_sources(
    naijabet_matches: list[dict],
    oddsapi_matches: list[dict],
) -> list[dict]:
    """
    Pairs up matches from both sources. Returns a list of merged matches,
    each with odds_by_bookmaker combining all 4 bookmakers where a pairing
    was found. Unpaired matches from either source are dropped — we can
    only check for arbitrage across all 4 books if we're confident it's
    the same real match on both sides.
    """
    merged_results = []
    used_oddsapi_indices = set()

    for nb_match in naijabet_matches:
        teams = _parse_naijabet_label(nb_match["match_label"])
        if not teams:
            continue
        nb_home, nb_away = teams

        best_idx = None
        best_score = 0.0

        for idx, oa_match in enumerate(oddsapi_matches):
            if idx in used_oddsapi_indices:
                continue

            home_sim = name_similarity(nb_home, oa_match["home_team"])
            away_sim = name_similarity(nb_away, oa_match["away_team"])

            if home_sim < NAME_SIMILARITY_THRESHOLD or away_sim < NAME_SIMILARITY_THRESHOLD:
                continue

            time_diff = _time_diff_hours(nb_match.get("match_time"), oa_match.get("commence_time"))
            if time_diff is not None and time_diff > TIME_TOLERANCE_HOURS:
                continue  # names matched but kickoff times are too far apart — likely a false match

            score = (home_sim + away_sim) / 2
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            continue  # no confident match found on the other side — skip, don't guess

        oa_match = oddsapi_matches[best_idx]
        used_oddsapi_indices.add(best_idx)

        combined_odds = dict(nb_match["odds_by_bookmaker"])
        combined_odds.update(oa_match["odds_by_bookmaker"])

        merged_results.append({
            "match_label": nb_match["match_label"],
            "odds_by_bookmaker": combined_odds,
            "match_confidence": round(best_score, 3),
        })

    return merged_results
