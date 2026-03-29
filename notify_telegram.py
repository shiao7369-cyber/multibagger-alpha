#!/usr/bin/env python3
"""
每日 08:00 執行：抓取 multibagger-alpha 掃描結果，透過 Telegram bot 發送
使用方式：python3 notify_telegram.py
crontab：0 8 * * * /usr/bin/python3 /path/to/notify_telegram.py
"""

import requests
import json
from datetime import datetime

# ── 設定區 ──────────────────────────────────────────────────────────────────
RENDER_URL   = "https://multibagger-alpha.onrender.com"
BOT_TOKEN    = "你的_BOT_TOKEN"   # 從 @BotFather 取得
CHAT_ID      = "你的_CHAT_ID"     # 你的 Telegram chat ID
# ────────────────────────────────────────────────────────────────────────────


def wake_render():
    """Render 免費版會休眠，先 ping 喚醒。"""
    try:
        requests.get(f"{RENDER_URL}/api/macro", timeout=60)
    except Exception:
        pass


def fetch_results():
    resp = requests.get(f"{RENDER_URL}/api/daily-results", timeout=30)
    return resp.json()


def format_message(data):
    status    = data.get("status", "unknown")
    scan_date = data.get("scan_date", "N/A")
    summary   = data.get("summary", {})
    top_sb    = data.get("top_strong_buy", [])
    top_b     = data.get("top_buy", [])

    if status != "done":
        return f"⚠️ 小巢多倍股掃描\n狀態：{status}\n日期：{scan_date}\n\n掃描尚未完成，請稍後再查。"

    lines = [
        f"🚀 *小巢多倍股日報* — {scan_date}",
        f"",
        f"📊 掃描統計",
        f"• 掃描股票數：{summary.get('total_scanned', 0)}",
        f"• 強力買入：{summary.get('strong_buy', 0)} 支",
        f"• 買入：{summary.get('buy', 0)} 支",
        f"• 平均評分：{summary.get('avg_score', 0)}",
        f"",
    ]

    if top_sb:
        lines.append("🔥 *強力買入 Top 10（78分以上）*")
        for i, r in enumerate(top_sb[:10], 1):
            name   = r.get("name", r.get("ticker", ""))[:20]
            ticker = r.get("ticker", "")
            score  = r.get("score", 0)
            mcap   = r.get("market_cap_b", 0)
            lines.append(f"{i}. `{ticker}` {name} — {score}分 | ${mcap:.1f}B")
        lines.append("")

    if top_b:
        lines.append("✅ *買入 Top 5（62–77分）*")
        for i, r in enumerate(top_b[:5], 1):
            ticker = r.get("ticker", "")
            score  = r.get("score", 0)
            name   = r.get("name", "")[:15]
            lines.append(f"{i}. `{ticker}` {name} — {score}分")
        lines.append("")

    lines.append(f"🔗 [完整報告]({RENDER_URL})")
    return "\n".join(lines)


def send_telegram(text):
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=data, timeout=15)
    return resp.json()


def main():
    print(f"[{datetime.now()}] 喚醒 Render...")
    wake_render()

    print(f"[{datetime.now()}] 抓取掃描結果...")
    data = fetch_results()

    msg = format_message(data)
    print(f"[{datetime.now()}] 發送 Telegram...")
    result = send_telegram(msg)

    if result.get("ok"):
        print(f"[{datetime.now()}] ✅ 發送成功")
    else:
        print(f"[{datetime.now()}] ❌ 發送失敗：{result}")


if __name__ == "__main__":
    main()
