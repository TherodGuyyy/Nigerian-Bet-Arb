"""
Nigerian betting arbitrage bot — main loop.

Every POLL_INTERVAL_SECONDS:
  1. Fetch Bet9ja + NairaBet odds (via NaijaBet_Api)
  2. Fetch 1xBet + Betway odds (via The Odds API)
  3. Match the same real-world matches across both sources
  4. Check each matched match for a guaranteed-profit arbitrage
  5. Alert on Telegram with exact stake amounts, respecting a cooldown so
     the same standing opportunity doesn't spam you every cycle

Run with: python main.py
"""

import logging
import time

import config
from bet9ja_nairabet_source import Bet9jaNairabetSource
from oddsapi_source import OddsApiSource
from match_matcher import match_across_sources
from arbitrage import check_arbitrage
from telegram_alerts import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

_last_alerted: dict[str, float] = {}


def _should_alert(match_label: str) -> bool:
    last = _last_alerted.get(match_label)
    return last is None or (time.time() - last) >= config.ALERT_COOLDOWN_SECONDS


def run_once(naijabet_source: Bet9jaNairabetSource, oddsapi_source: OddsApiSource) -> int:
    """One full scan pass. Returns number of alerts sent."""
    try:
        naijabet_matches = naijabet_source.fetch_matches()
    except Exception as e:
        log.error("Failed to fetch Bet9ja/NairaBet odds: %s", e)
        return 0

    try:
        # Discovers and fetches ALL currently available soccer leagues
        # (EPL, La Liga, Serie A, Bundesliga, Champions League, etc.) —
        # not just one, so this actually has a chance to match against the
        # full spread of matches Bet9ja/NairaBet cover.
        oddsapi_matches = oddsapi_source.fetch_matches()
    except Exception as e:
        log.error("Failed to fetch 1xBet/Betway odds: %s", e)
        return 0

    log.info("Fetched %d Bet9ja/NairaBet matches, %d 1xBet/Betway matches",
              len(naijabet_matches), len(oddsapi_matches))

    paired = match_across_sources(naijabet_matches, oddsapi_matches)
    log.info("Matched %d pairs across both sources", len(paired))

    alerts_sent = 0
    for match in paired:
        result = check_arbitrage(
            match["match_label"],
            match["odds_by_bookmaker"],
            min_roi_pct=config.MIN_ROI_PCT,
            total_stake=config.DEFAULT_TOTAL_STAKE,
        )
        if result is None:
            continue

        if not _should_alert(result.match_label):
            log.info("Suppressing repeat alert for %s (cooldown active)", result.match_label)
            continue

        log.info("Arbitrage found: %s — %.2f%% guaranteed profit",
                  result.match_label, result.guaranteed_roi_pct)

        if send_alert(result):
            _last_alerted[result.match_label] = time.time()
            alerts_sent += 1

    return alerts_sent


def main():
    if not config.ODDS_API_KEY:
        raise SystemExit("ODDS_API_KEY is not set — get a free key from the-odds-api.com")

    naijabet_source = Bet9jaNairabetSource()
    oddsapi_source = OddsApiSource(config.ODDS_API_KEY)

    if config.RUN_ONCE:
        log.info("Running single scan pass (RUN_ONCE mode)")
        sent = run_once(naijabet_source, oddsapi_source)
        log.info("Sent %d alert(s) this pass", sent)
        return

    log.info(
        "Starting scan loop: interval=%ds, min_roi=%.1f%%, stake=₦%.0f",
        config.POLL_INTERVAL_SECONDS, config.MIN_ROI_PCT, config.DEFAULT_TOTAL_STAKE,
    )

    while True:
        start = time.time()
        sent = run_once(naijabet_source, oddsapi_source)
        if sent:
            log.info("Sent %d alert(s) this pass", sent)
        elapsed = time.time() - start
        time.sleep(max(0, config.POLL_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
