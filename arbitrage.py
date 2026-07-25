"""
Arbitrage math for soccer's 1X2 market (Home / Draw / Away) across multiple
bookmakers.

HOW THIS WORKS: unlike the earlier Bayse bot (binary YES/NO, same platform),
this compares the BEST available odds for each of the 3 outcomes, where each
outcome's best odds might come from a different bookmaker entirely. E.g.
Bet9ja might offer the best price on Home, while 1xBet offers the best price
on Away — you'd bet Home on Bet9ja and Away on 1xBet.

THE MATH:
  implied_probability = 1 / decimal_odds

For a fair (no-arb) market, the three implied probabilities should sum to
more than 1.00 (the excess over 1.00 is the bookmaker's built-in margin/vig
— this is normal and expected, it's how bookmakers make money). An
arbitrage exists when the sum of the BEST available implied probabilities
across different bookmakers dips below 1.00 — meaning you could bet all
three outcomes (on whichever bookmaker offers the best price for each) and
come out ahead regardless of the result.

  arb_ratio = 1/best_home_odds + 1/best_draw_odds + 1/best_away_odds

  arb_ratio < 1.0  →  arbitrage exists
  guaranteed ROI   =  (1/arb_ratio - 1) * 100%

Stake allocation (to guarantee the SAME profit regardless of which outcome
actually happens):
  stake_on_outcome_i = total_stake * (1/odds_i) / arb_ratio
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OutcomeOdds:
    outcome: str        # "home", "draw", or "away"
    odds: float          # decimal odds, e.g. 2.10
    bookmaker: str        # which of the 4 sites offers this price


@dataclass
class ArbResult:
    match_label: str
    legs: list[OutcomeOdds]      # the 3 best-odds legs used
    arb_ratio: float              # sum of implied probabilities
    guaranteed_roi_pct: float     # profit % regardless of outcome
    stakes_per_1000: dict         # how to split ₦1000 total stake across legs


def find_best_odds_per_outcome(
    odds_by_bookmaker: dict[str, dict[str, float]]
) -> list[OutcomeOdds]:
    """
    odds_by_bookmaker: {"bet9ja": {"home": 2.10, "draw": 3.40, "away": 3.20}, ...}
    or, for a 2-way market like basketball moneyline:
    odds_by_bookmaker: {"betway": {"home": 1.90, "away": 1.95}, ...}

    Returns the single best (highest) odds for each outcome that actually
    appears in the data — works for any number of outcomes (2-way, 3-way,
    or more), not hardcoded to soccer's home/draw/away specifically.
    """
    best: dict[str, OutcomeOdds] = {}
    for bookmaker, prices in odds_by_bookmaker.items():
        for outcome, price in prices.items():
            if price is None:
                continue
            if outcome not in best or price > best[outcome].odds:
                best[outcome] = OutcomeOdds(outcome=outcome, odds=price, bookmaker=bookmaker)

    return list(best.values())


def check_arbitrage(
    match_label: str,
    odds_by_bookmaker: dict[str, dict[str, float]],
    min_roi_pct: float = 1.0,
    total_stake: float = 1000.0,
    expected_outcomes: int = 3,
) -> Optional[ArbResult]:
    """
    Checks a single match for an arbitrage opportunity across whatever
    bookmakers provided odds for it. Works for any market shape — pass
    expected_outcomes=3 for soccer's home/draw/away, or
    expected_outcomes=2 for a moneyline market like basketball (home/away,
    no draw). Returns None if no arb, or if fewer than expected_outcomes
    have any odds at all (can't compute without all outcomes present).
    """
    legs = find_best_odds_per_outcome(odds_by_bookmaker)
    if len(legs) < expected_outcomes:
        return None  # missing an outcome somewhere — can't evaluate

    arb_ratio = sum(1.0 / leg.odds for leg in legs)

    if arb_ratio >= 1.0:
        return None  # no arbitrage — this is the normal case, most of the time

    roi_pct = (1.0 / arb_ratio - 1.0) * 100.0
    if roi_pct < min_roi_pct:
        return None  # technically an arb, but too thin to bother with

    stakes = {
        leg.outcome: round(total_stake * (1.0 / leg.odds) / arb_ratio, 2)
        for leg in legs
    }

    return ArbResult(
        match_label=match_label,
        legs=legs,
        arb_ratio=arb_ratio,
        guaranteed_roi_pct=roi_pct,
        stakes_per_1000=stakes,
    )
