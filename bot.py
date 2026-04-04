import os
import asyncio
import requests
import html
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

LAUNCH_TIME = datetime(2026, 4, 1, 22, 35, 0, tzinfo=timezone.utc)

WMO_CODES = {
    0: "☀️ Clear sky", 1: "🌤 Mainly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
    45: "🌫 Foggy", 48: "🌫 Icy fog", 51: "🌦 Light drizzle", 53: "🌦 Drizzle",
    55: "🌧 Heavy drizzle", 61: "🌧 Light rain", 63: "🌧 Rain", 65: "🌧 Heavy rain",
    71: "🌨 Light snow", 73: "🌨 Snow", 75: "❄️ Heavy snow", 80: "🌦 Rain showers",
    85: "🌨 Snow showers", 95: "⛈ Thunderstorm", 99: "⛈ Thunderstorm with hail",
}

NEWS_CATEGORIES = ["business", "entertainment", "health", "science", "sports", "technology", "general"]
NEWS_COUNTRIES = {
    "nz": "🇳🇿", "us": "🇺🇸", "gb": "🇬🇧", "au": "🇦🇺",
    "ca": "🇨🇦", "in": "🇮🇳", "de": "🇩🇪", "fr": "🇫🇷",
}

TRIVIA_CATEGORIES = {
    "general": 9, "books": 10, "film": 11, "music": 12, "science": 17,
    "computers": 18, "maths": 19, "sports": 21, "geography": 22,
    "history": 23, "art": 25, "animals": 27, "space": 14,
}


# ─────────────────────────────────────────────
# 1. ARTEMIS II
# ─────────────────────────────────────────────

def get_artemis_stats():
    try:
        now = datetime.now(timezone.utc)
        elapsed = now - LAUNCH_TIME
        days = elapsed.days
        hours, remainder = divmod(elapsed.seconds, 3600)
        minutes = remainder // 60

        rss_url = "https://blogs.nasa.gov/artemis/feed/"
        rss_resp = requests.get(rss_url, timeout=10)
        latest_headline = "No update available"
        if rss_resp.status_code == 200:
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
# 2. WEATHER — Open-Meteo
# ─────────────────────────────────────────────

def geocode_city(city: str):
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
            return f"❌ Could not find a place called *{city}*."

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,windspeed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "forecast_days": 4, "timezone": "auto",
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
            f"", f"📅 *3-Day Forecast:*",
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
# 3. FOREX — Frankfurter
# ─────────────────────────────────────────────

def get_forex(args: list):
    try:
        base = args[0].upper() if args else "USD"
        majors = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "USD", "SGD"]
        quotes = [a.upper() for a in args[1:]] if len(args) >= 2 else [c for c in majors if c != base]

        url = "https://api.frankfurter.app/latest"
        r = requests.get(url, params={"from": base, "to": ",".join(quotes)}, timeout=10)
        data = r.json()

        if "rates" not in data:
            return f"❌ Could not find rates for *{base}*. Check the currency code (e.g. USD, EUR, GBP)."

        lines = [
            f"💱 *Forex Rates — Base: {base}*",
            f"━━━━━━━━━━━━━━━━━━",
            f"📅 Rate date: {data.get('date', 'N/A')}",
            f"🏦 Source: European Central Bank", "",
        ]
        for currency, rate in data["rates"].items():
            lines.append(f"  *{currency}:* {rate}")
        lines.append("\nTip: `/forex GBP USD EUR` for a custom pair.")
        return "\n".join(lines)
    except Exception as e:
        print(f"Forex error: {e}")
        return "💱 Forex data unavailable right now. Try again shortly."


# ─────────────────────────────────────────────
# 4. APOD — NASA Astronomy Picture of the Day
# ─────────────────────────────────────────────

def get_apod():
    try:
        api_key = os.environ.get("NASA_API_KEY", "DEMO_KEY")
        r = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params={"api_key": api_key},
            timeout=10
        )
        data = r.json()

        if "error" in data:
            return None, f"❌ NASA APOD error: {data['error'].get('message', 'Unknown error')}"

        title = data.get("title", "No title")
        date = data.get("date", "")
        explanation = data.get("explanation", "")
        media_type = data.get("media_type", "image")
        url = data.get("url", "")
        hdurl = data.get("hdurl", url)

        # Trim explanation to ~600 chars so it's readable in Telegram
        if len(explanation) > 600:
            explanation = explanation[:597] + "..."

        caption = (
            f"🌌 *NASA Astronomy Picture of the Day*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📸 *{title}*\n"
            f"📅 {date}\n\n"
            f"{explanation}\n\n"
            f"🔗 [Full resolution]({hdurl})"
        )

        if media_type == "image":
            return url, caption
        else:
            # It's a video (e.g. YouTube) — can't send as photo
            return None, caption + f"\n🎬 [Watch here]({url})"

    except Exception as e:
        print(f"APOD error: {e}")
        return None, "🌌 Could not fetch today's APOD. Try again shortly."


# ─────────────────────────────────────────────
# 5. TRIVIA — Open Trivia DB
# ─────────────────────────────────────────────

# Store pending answers per user: {user_id: correct_answer}
trivia_pending = {}


def get_trivia(category_name: str = None, difficulty: str = None):
    try:
        params = {"amount": 1, "type": "multiple"}

        if category_name:
            cat = category_name.lower()
            if cat in TRIVIA_CATEGORIES:
                params["category"] = TRIVIA_CATEGORIES[cat]
            else:
                return None, f"❌ Unknown category *{category_name}*.\n\nAvailable: {', '.join(TRIVIA_CATEGORIES.keys())}"

        if difficulty and difficulty.lower() in ["easy", "medium", "hard"]:
            params["difficulty"] = difficulty.lower()

        r = requests.get("https://opentdb.com/api.php", params=params, timeout=10)
        data = r.json()

        if data["response_code"] != 0 or not data["results"]:
            return None, "❌ Could not fetch a trivia question. Try again!"

        q = data["results"][0]
        question = html.unescape(q["question"])
        correct = html.unescape(q["correct_answer"])
        wrong = [html.unescape(a) for a in q["incorrect_answers"]]
        category = html.unescape(q["category"])
        difficulty_label = q["difficulty"].capitalize()

        # Shuffle options
        import random
        options = wrong + [correct]
        random.shuffle(options)
        letters = ["A", "B", "C", "D"]

        option_lines = []
        correct_letter = ""
        for i, opt in enumerate(options):
            option_lines.append(f"  *{letters[i]}:* {opt}")
            if opt == correct:
                correct_letter = letters[i]

        text = (
            f"🎯 *TRIVIA*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📚 *Category:* {category}\n"
            f"⚡ *Difficulty:* {difficulty_label}\n\n"
            f"❓ {question}\n\n"
            + "\n".join(option_lines) +
            f"\n\n💬 Reply with *A*, *B*, *C*, or *D*!"
        )

        return correct_letter, text

    except Exception as e:
        print(f"Trivia error: {e}")
        return None, "🎯 Could not fetch trivia right now. Try again shortly."


# ─────────────────────────────────────────────
# 6. NEWS — NewsAPI
# ─────────────────────────────────────────────

def get_news(args: list):
    try:
        api_key = os.environ.get("NEWS_API_KEY")
        if not api_key:
            return "❌ NEWS_API_KEY not set. Get a free key at newsapi.org and add it to your environment."

        # Parse args: /news [category] [country]
        category = None
        country = "us"  # default

        for arg in [a.lower() for a in args]:
            if arg in NEWS_CATEGORIES:
                category = arg
            elif arg in NEWS_COUNTRIES:
                country = arg

        params = {
            "apiKey": api_key,
            "country": country,
            "pageSize": 5,
        }
        if category:
            params["category"] = category

        r = requests.get("https://newsapi.org/v2/top-headlines", params=params, timeout=10)
        data = r.json()

        if data.get("status") != "ok":
            return f"❌ News API error: {data.get('message', 'Unknown error')}"

        articles = data.get("articles", [])
        if not articles:
            return f"📰 No news found for that filter. Try a different category or country."

        flag = NEWS_COUNTRIES.get(country, "🌐")
        label = f"{flag} *Top Headlines"
        if category:
            label += f" — {category.capitalize()}"
        label += "*"

        lines = [label, "━━━━━━━━━━━━━━━━━━"]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "No title").split(" - ")[0].strip()
            source = article.get("source", {}).get("name", "Unknown")
            url = article.get("url", "")
            lines.append(f"\n*{i}. {title}*")
            lines.append(f"   📡 {source}")
            if url:
                lines.append(f"   🔗 [Read more]({url})")

        lines.append(f"\n\n💡 Try: `/news technology nz` or `/news sports us`")
        lines.append(f"Categories: {', '.join(NEWS_CATEGORIES)}")
        lines.append(f"Countries: {', '.join(NEWS_COUNTRIES.keys())}")

        return "\n".join(lines)

    except Exception as e:
        print(f"News error: {e}")
        return "📰 News unavailable right now. Try again shortly."


# ─────────────────────────────────────────────
# 7. BOT COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Space & Earth Bot — Command Guide*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 *SPACE*\n"
        "/artemis — Live Artemis II mission status, elapsed time & latest NASA updates\n"
        "/apod — NASA Astronomy Picture of the Day with description\n\n"
        "🌍 *WEATHER*\n"
        "/weather `<city>` — Current conditions + 3-day forecast for any city\n"
        "Example: `/weather Auckland`\n\n"
        "💱 *FINANCE*\n"
        "/forex `<base>` `[targets]` — Exchange rates from the European Central Bank\n"
        "Example: `/forex NZD USD GBP` or `/forex EUR` for major pairs\n\n"
        "📰 *NEWS*\n"
        "/news `[category]` `[country]` — Top headlines, fully filterable\n"
        "Categories: business, technology, science, sports, health, entertainment, general\n"
        "Countries: nz, us, gb, au, ca, in, de, fr\n"
        "Example: `/news technology nz` or `/news sports`\n\n"
        "🎯 *TRIVIA*\n"
        "/trivia `[category]` `[difficulty]` — Random trivia question, reply A/B/C/D to answer\n"
        "Categories: general, space, science, history, geography, film, music, sports, computers, animals, art\n"
        "Difficulty: easy, medium, hard\n"
        "Example: `/trivia space hard` or `/trivia` for a random one\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 Type /help anytime to see this menu."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def artemis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛰️ Fetching Artemis II status...")
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
        await update.message.reply_text("Usage: `/forex USD` or `/forex NZD USD GBP`", parse_mode="Markdown")
        return
    await update.message.reply_text("💱 Fetching exchange rates...", parse_mode="Markdown")
    result = get_forex(context.args)
    await update.message.reply_text(result, parse_mode="Markdown")


async def apod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌌 Fetching today's Astronomy Picture of the Day...")
    image_url, caption = get_apod()
    if image_url:
        await update.message.reply_photo(photo=image_url, caption=caption, parse_mode="Markdown")
    else:
        await update.message.reply_text(caption, parse_mode="Markdown")


async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = None
    difficulty = None
    for arg in context.args:
        if arg.lower() in TRIVIA_CATEGORIES:
            category = arg.lower()
        elif arg.lower() in ["easy", "medium", "hard"]:
            difficulty = arg.lower()

    correct_letter, text = get_trivia(category, difficulty)
    if correct_letter:
        trivia_pending[update.effective_user.id] = correct_letter
    await update.message.reply_text(text, parse_mode="Markdown")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📰 Fetching headlines...", parse_mode="Markdown")
    result = get_news(context.args)
    await update.message.reply_text(result, parse_mode="Markdown", disable_web_page_preview=True)


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    # Check if this is a trivia answer
    if user_id in trivia_pending and text in ["A", "B", "C", "D"]:
        correct = trivia_pending.pop(user_id)
        if text == correct:
            await update.message.reply_text(f"✅ *Correct! Well done!*", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"❌ *Wrong!* The correct answer was *{correct}*.",
                parse_mode="Markdown"
            )
        return

    await update.message.reply_text(
        "Not sure what you mean! Type /help to see all available commands.",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# 8. MAIN
# ─────────────────────────────────────────────

async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("ERROR: No BOT_TOKEN found!")
        return

    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("artemis", artemis_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("forex", forex_command))
    app.add_handler(CommandHandler("apod", apod_command))
    app.add_handler(CommandHandler("trivia", trivia_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

    await app.initialize()
    await app.start()
    print("Bot is alive — all systems go!")
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
