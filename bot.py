import os
import asyncio
import requests
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

LAUNCH_TIME = datetime(2026, 4, 1, 22, 35, 0, tzinfo=timezone.utc)  # 18:35 EDT = 22:35 UTC

WMO_CODES = {
    0: "☀️ Clear sky", 1: "🌤 Mainly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
    45: "🌫 Foggy", 48: "🌫 Icy fog", 51: "🌦 Light drizzle", 53: "🌦 Drizzle",
    55: "🌧 Heavy drizzle", 61: "🌧 Light rain", 63: "🌧 Rain", 65: "🌧 Heavy rain",
    71: "🌨 Light snow", 73: "🌨 Snow", 75: "❄️ Heavy snow", 80: "🌦 Rain showers",
    85: "🌨 Snow showers", 95: "⛈ Thunderstorm", 99: "⛈ Thunderstorm with hail",
}


# ─────────────────────────────────────────────
# 1. ARTEMIS II — NASA AROW scrape
# ─────────────────────────────────────────────

def get_artemis_stats():
    """
    NASA's AROW does not expose a public JSON API.
    We calculate mission elapsed time ourselves and pull
    the latest headline from NASA's Artemis blog RSS feed.
    """
    try:
        now = datetime.now(timezone.utc)
        elapsed = now - LAUNCH_TIME
        days = elapsed.days
        hours, remainder = divmod(elapsed.seconds, 3600)
        minutes = remainder // 60

        # Pull latest NASA Artemis blog entry via RSS
        rss_url = "https://blogs.nasa.gov/artemis/feed/"
        rss_resp = requests.get(rss_url, timeout=10)
        latest_headline = "No update available"
        if rss_resp.status_code == 200:
            # Quick parse — grab first <title> after the channel title
            content = rss_resp.text
            titles = [t.split("</title>")[0] for t in content.split("<title>")[2:5]]
            if titles:
                latest_headline = titles[0].replace("<![CDATA[", "").replace("]]>", "").strip()

        return (
            f"🚀 *ARTEMIS II — LIVE MISSION STATUS*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏱ *Mission Elapsed:* {days}d {hours}h {minutes}m\n"
            f"📅 *Launch:* 1 April 2026, 22:35 UTC\n"
            f"👨‍🚀 *Crew:* Wiseman, Glover, Koch, Hansen\n"
            f"🌕 *Phase:* Trans-lunar coast\n"
            f"📡 *Track live:* nasa.gov/trackartemis\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📰 *Latest NASA update:*\n{latest_headline}"
        )
    except Exception as e:
        print(f"Artemis error: {e}")
        return "🛰️ Could not fetch Artemis data right now. Try again shortly."


# ─────────────────────────────────────────────
# 2. WEATHER — Open-Meteo (free, no key)
# ─────────────────────────────────────────────

def geocode_city(city: str):
    """Use Open-Meteo's free geocoding API to resolve a city name to lat/lon."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=10)
    results = r.json().get("results")
    if not results:
        return None, None, None
    loc = results[0]
    return loc["latitude"], loc["longitude"], loc.get("name", city)


def get_weather(city: str):
    try:
        lat, lon, resolved_name = geocode_city(city)
        if lat is None:
            return f"❌ Could not find a place called *{city}*. Try a different city name."

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,windspeed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "forecast_days": 4,
            "timezone": "auto",
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        cur = data["current"]
        daily = data["daily"]
        condition = WMO_CODES.get(cur["weather_code"], "❓ Unknown")

        lines = [
            f"🌍 *Weather for {resolved_name}*",
            f"━━━━━━━━━━━━━━━━━━",
            f"{condition}",
            f"🌡 *Temp:* {cur['temperature_2m']}°C (feels {cur['apparent_temperature']}°C)",
            f"💧 *Humidity:* {cur['relative_humidity_2m']}%",
            f"💨 *Wind:* {cur['windspeed_10m']} km/h",
            f"🌧 *Precip now:* {cur['precipitation']} mm",
            f"",
            f"📅 *3-Day Forecast:*",
        ]
        for i in range(1, 4):
            day = daily["time"][i]
            hi = daily["temperature_2m_max"][i]
            lo = daily["temperature_2m_min"][i]
            rain_pct = daily["precipitation_probability_max"][i]
            cond = WMO_CODES.get(daily["weather_code"][i], "❓")
            lines.append(f"  *{day}:* {cond} {lo}–{hi}°C, {rain_pct}% rain")

        return "\n".join(lines)

    except Exception as e:
        print(f"Weather error: {e}")
        return "⛅ Weather data unavailable right now. Try again shortly."


# ─────────────────────────────────────────────
# 3. FOREX — Frankfurter (free, no key)
# ─────────────────────────────────────────────

def get_forex(args: list):
    try:
        base = args[0].upper() if args else "USD"
        majors = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY", "SGD"]

        if len(args) >= 2:
            quotes = [a.upper() for a in args[1:]]
        else:
            quotes = [c for c in majors if c != base]

        # Use the stable .app endpoint — returns {"rates": {...}} directly
        url = "https://api.frankfurter.app/latest"
        r = requests.get(url, params={"from": base, "to": ",".join(quotes)}, timeout=10)
        data = r.json()

        if "rates" not in data:
            return f"❌ Could not find rates for *{base}*. Check the currency code (e.g. USD, EUR, GBP)."

        lines = [
            f"💱 *Forex Rates — Base: {base}*",
            f"━━━━━━━━━━━━━━━━━━",
            f"📅 Rate date: {data.get('date', 'N/A')}",
            f"🏦 Source: European Central Bank",
            "",
        ]
        for currency, rate in data["rates"].items():
            lines.append(f"  *{currency}:* {rate}")

        lines.append("\nTip: `/forex GBP USD EUR` for a custom pair.")
        return "\n".join(lines)

    except Exception as e:
        print(f"Forex error: {e}")
        return "💱 Forex data unavailable right now. Try again shortly."


# ─────────────────────────────────────────────
# 4. BOT COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to Space & Earth Bot!*\n\n"
        "Commands:\n"
        "🚀 /artemis — Artemis II live mission status\n"
        "🌤 /weather <city> — Current weather + 3-day forecast\n"
        "💱 /forex <BASE> [TARGET ...] — Exchange rates\n\n"
        "Examples:\n"
        "`/weather Auckland`\n"
        "`/forex USD EUR GBP`\n"
        "`/forex JPY`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def artemis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛰️ Fetching Artemis II status...", parse_mode="Markdown")
    status = get_artemis_stats()
    await update.message.reply_text(status, parse_mode="Markdown")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/weather <city>` — e.g. `/weather Tokyo`", parse_mode="Markdown")
        return
    city = " ".join(context.args)
    await update.message.reply_text(f"🌍 Looking up weather for *{city}*...", parse_mode="Markdown")
    result = get_weather(city)
    await update.message.reply_text(result, parse_mode="Markdown")


async def forex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/forex USD` or `/forex USD EUR GBP`", parse_mode="Markdown")
        return
    await update.message.reply_text("💱 Fetching exchange rates...", parse_mode="Markdown")
    result = get_forex(context.args)
    await update.message.reply_text(result, parse_mode="Markdown")


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Try one of these commands:\n"
        "🚀 /artemis\n"
        "🌤 /weather <city>\n"
        "💱 /forex <currency>",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────

async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("ERROR: No BOT_TOKEN found!")
        return

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("artemis", artemis_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("forex", forex_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

    await app.initialize()
    await app.start()
    print("Bot is alive — Artemis II tracking + weather + forex active!")
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
