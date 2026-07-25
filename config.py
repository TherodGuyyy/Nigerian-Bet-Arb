import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# From the-odds-api.com — NOT theoddsapi.com, a different unrelated service.
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

# Your default total stake per opportunity — used to show you exactly how
# much to place on each bookmaker/outcome.
DEFAULT_TOTAL_STAKE = float(os.getenv("DEFAULT_TOTAL_STAKE", "1000"))

# Minimum guaranteed profit % before alerting. 2% on a ₦1000 stake is ₦20+
# of genuinely guaranteed profit — enough to be worth the effort of placing
# both legs before odds move. Lower this if you want to see thinner
# opportunities too.
MIN_ROI_PCT = float(os.getenv("MIN_ROI_PCT", "2.0"))

# How often to run a full scan, in seconds.
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "86400"))  # 24h — 5 leagues, budget-safe

# Don't re-alert the same match repeatedly while the opportunity is still
# open — wait this long before alerting on it again.
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "600"))

# When RUN_ONCE=true (set by the GitHub Actions workflow), the bot does a
# single scan pass and exits, instead of looping forever — same pattern as
# your Bayse arb bot. GitHub Actions triggers a fresh run on a schedule,
# so the "loop" happens at the scheduling layer instead of inside the script.
RUN_ONCE = os.getenv("RUN_ONCE", "false").strip().lower() == "true"

# ── Basketball sibling bot (separate Telegram bot, shares the same
# ODDS_API_KEY above since it's the same The Odds API account/key) ────────
BASKETBALL_TELEGRAM_BOT_TOKEN = os.getenv("BASKETBALL_TELEGRAM_BOT_TOKEN", "")
BASKETBALL_TELEGRAM_CHAT_ID = os.getenv("BASKETBALL_TELEGRAM_CHAT_ID", "")
BASKETBALL_DEFAULT_TOTAL_STAKE = float(os.getenv("BASKETBALL_DEFAULT_TOTAL_STAKE", "1000"))
BASKETBALL_MIN_ROI_PCT = float(os.getenv("BASKETBALL_MIN_ROI_PCT", "2.0"))
BASKETBALL_POLL_INTERVAL_SECONDS = int(os.getenv("BASKETBALL_POLL_INTERVAL_SECONDS", "14400"))  # 4h
