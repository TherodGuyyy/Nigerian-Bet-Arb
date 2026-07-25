"""
Basketball arbitrage bot — sibling to main.py (the football bot).

IMPORTANT DIFFERENCE FROM THE FOOTBALL BOT: Bet9ja/NairaBet's library only
supports soccer, so this compares just 1xBet vs Betway (both via The Odds
API) — 2 bookmakers, not 4. That means:
  - No separate match_matcher step needed — both bookmakers' odds come
    through the SAME source/response, already for the same events, so
    there's no cross-source name-matching to do (that was only needed
    because the football bot combines two DIFFERENT data sources).
  - 2-way moneyline market (home/away only, no draw) — uses the same
    arbitrage.py math, just with expected_outcomes=2.
  - Casts a wide net across ALL basketball leagues The Odds API currently
    supports (NBA, NCAA, WNBA, Euroleague, etc.) via dynamic discovery,
    not one hardcoded league.

Run with: python main_basketball.py
"""

import logging
import time

import config
from oddsapi_source import OddsApiSource
from arbitrage import check_arbitrage
from telegram_alerts import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main_basketball")

_last_alerted: dict[str, float] = {}


def _should_alert(match_label: str) -> bool:
    last = _last_alerted.get(match_label)
    return last is None or (time.time() - last) >= config.ALERT_COOLDOWN_SECONDS


def run_once(oddsapi_source: OddsApiSource) -> int:
    try:
        # WNBA specifically — confirmed in-season right now, and keeping
        # to one league leaves plenty of credit budget headroom (~180
        # credits/month at a 4-hour interval, well under the 500 cap).
        matches = oddsapi_source.fetch_matches(sport_keys=["basketball_wnba"])
    except Exception as e:
        log.error("Failed to fetch basketball odds: %s", e)
        return 0

    log.info("Fetched %d basketball matches across all available leagues", len(matches))

    alerts_sent = 0
    for match in matches:
        result = check_arbitrage(
            match["match_label"],
            match["odds_by_bookmaker"],
            min_roi_pct=config.BASKETBALL_MIN_ROI_PCT,
            total_stake=config.BASKETBALL_DEFAULT_TOTAL_STAKE,
            expected_outcomes=2,  # moneyline: home/away, no draw
        )
        if result is None:
            continue

        if not _should_alert(result.match_label):
            log.info("Suppressing repeat alert for %s (cooldown active)", result.match_label)
            continue

        log.info("Basketball arbitrage found: %s — %.2f%% guaranteed profit",
                  result.match_label, result.guaranteed_roi_pct)

        if send_alert(
            result,
            emoji="🏀",
            bot_token=config.BASKETBALL_TELEGRAM_BOT_TOKEN,
            chat_id=config.BASKETBALL_TELEGRAM_CHAT_ID,
        ):
            _last_alerted[result.match_label] = time.time()
            alerts_sent += 1

    return alerts_sent


def main():
    if not config.ODDS_API_KEY:
        raise SystemExit("ODDS_API_KEY is not set — get a free key from the-odds-api.com")
    if not config.BASKETBALL_TELEGRAM_BOT_TOKEN or not config.BASKETBALL_TELEGRAM_CHAT_ID:
        raise SystemExit(
            "BASKETBALL_TELEGRAM_BOT_TOKEN / BASKETBALL_TELEGRAM_CHAT_ID not set — "
            "set up a fresh Telegram bot for this one, separate from the football bot."
        )

    oddsapi_source = OddsApiSource(config.ODDS_API_KEY)

    if config.RUN_ONCE:
        log.info("Running single basketball scan pass (RUN_ONCE mode)")
        sent = run_once(oddsapi_source)
        log.info("Sent %d alert(s) this pass", sent)
        return

    log.info(
        "Starting basketball scan loop: interval=%ds, min_roi=%.1f%%, stake=₦%.0f",
        config.BASKETBALL_POLL_INTERVAL_SECONDS,
        config.BASKETBALL_MIN_ROI_PCT,
        config.BASKETBALL_DEFAULT_TOTAL_STAKE,
    )

    while True:
        start = time.time()
        sent = run_once(oddsapi_source)
        if sent:
            log.info("Sent %d alert(s) this pass", sent)
        elapsed = time.time() - start
        time.sleep(max(0, config.BASKETBALL_POLL_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
