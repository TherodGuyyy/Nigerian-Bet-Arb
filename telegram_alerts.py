import logging
import requests

import config
from arbitrage import ArbResult

log = logging.getLogger("telegram_alerts")


def _format_message(result: ArbResult, emoji: str = "⚽") -> str:
    lines = [
        f"{emoji} ARBITRAGE — {result.match_label}",
        f"Guaranteed profit: {result.guaranteed_roi_pct:.2f}%",
        "",
        "Place these bets:",
    ]
    for leg in result.legs:
        stake = result.stakes_per_1000[leg.outcome]
        lines.append(
            f"  • {leg.outcome.upper()} on {leg.bookmaker}: "
            f"₦{stake:,.2f} @ {leg.odds:.2f}"
        )
    total = sum(result.stakes_per_1000.values())
    profit = total * (result.guaranteed_roi_pct / 100)
    lines.append("")
    lines.append(f"Total stake: ₦{total:,.2f}  →  Guaranteed profit: ₦{profit:,.2f}")
    lines.append("")
    lines.append("⚠️ Odds move fast — place all legs quickly. Verify live "
                  "prices before betting; this is a snapshot, not a lock.")
    return "\n".join(lines)


def send_alert(result: ArbResult, emoji: str = "⚽",
                bot_token: str = None, chat_id: str = None) -> bool:
    bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not bot_token or not chat_id:
        log.error("Telegram not configured — would have sent:\n%s", _format_message(result, emoji))
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": _format_message(result, emoji)},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        log.error("Failed to send Telegram alert: %s", e)
        return False
