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
# CRYPTO — CoinGecko (free, no key)
# ─────────────────────────────────────────────

CRYPTO_IDS = {
    "btc": "bitcoin", "bitcoin": "bitcoin",
    "eth": "ethereum", "ethereum": "ethereum",
    "sol": "solana", "solana": "solana",
    "xrp": "ripple", "ripple": "ripple",
    "bnb": "binancecoin", "binance": "binancecoin",
    "doge": "dogecoin", "dogecoin": "dogecoin",
    "ada": "cardano", "cardano": "cardano",
    "avax": "avalanche-2", "avalanche": "avalanche-2",
    "dot": "polkadot", "polkadot": "polkadot",
    "matic": "matic-network", "polygon": "matic-network",
}

DEFAULT_CRYPTOS = ["bitcoin", "ethereum", "solana", "ripple", "dogecoin"]


def get_crypto(args: list):
    try:
        if args:
            ids = []
            unknown = []
            for arg in args:
                key = arg.lower()
                if key in CRYPTO_IDS:
                    ids.append(CRYPTO_IDS[key])
                else:
                    unknown.append(arg.upper())
            if unknown:
                return f"❌ Unknown coin(s): {', '.join(unknown)}\n\nSupported: BTC, ETH, SOL, XRP, BNB, DOGE, ADA, AVAX, DOT, MATIC"
            # Deduplicate while preserving order
            ids = list(dict.fromkeys(ids))
        else:
            ids = DEFAULT_CRYPTOS

        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ",".join(ids),
            "order": "market_cap_desc",
            "sparkline": False,
            "price_change_percentage": "24h",
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if not data:
            return "❌ Could not fetch crypto data. Try again shortly."

        lines = ["₿ *Crypto Prices — USD*", "━━━━━━━━━━━━━━━━━━"]
        for coin in data:
            name = coin["name"]
            symbol = coin["symbol"].upper()
            price = coin["current_price"]
            change = coin["price_change_percentage_24h"]
            cap = coin["market_cap"]
            high = coin["high_24h"]
            low = coin["low_24h"]

            arrow = "📈" if change >= 0 else "📉"
            change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"

            # Format price nicely depending on size
            if price >= 1:
                price_str = f"${price:,.2f}"
            else:
                price_str = f"${price:.6f}"

            # Format market cap in billions/millions
            if cap >= 1_000_000_000:
                cap_str = f"${cap / 1_000_000_000:.2f}B"
            else:
                cap_str = f"${cap / 1_000_000:.2f}M"

            lines.append(
                f"\n*{name}* ({symbol})\n"
                f"  💰 Price: {price_str}  {arrow} {change_str}\n"
                f"  📊 24h: ${low:,.2f} — ${high:,.2f}\n"
                f"  🏦 Market cap: {cap_str}"
            )

        lines.append("\n💡 Try: `/crypto btc eth sol` or `/crypto doge`")
        return "\n".join(lines)

    except Exception as e:
        print(f"Crypto error: {e}")
        return "₿ Crypto data unavailable right now. Try again shortly."


# ─────────────────────────────────────────────
# TIME — WorldTimeAPI (free, no key)
# ─────────────────────────────────────────────

CITY_TIMEZONES = {
    "london": "Europe/London",
    "new york": "America/New_York", "nyc": "America/New_York",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "toronto": "America/Toronto",
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland",
    "tokyo": "Asia/Tokyo",
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "dubai": "Asia/Dubai",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "moscow": "Europe/Moscow",
    "singapore": "Asia/Singapore",
    "hong kong": "Asia/Hong_Kong", "hongkong": "Asia/Hong_Kong",
    "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata",
    "cairo": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg",
    "sao paulo": "America/Sao_Paulo",
    "mexico city": "America/Mexico_City",
    "amsterdam": "Europe/Amsterdam",
    "seoul": "Asia/Seoul",
    "bangkok": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta",
    "wellington": "Pacific/Auckland",
    "christchurch": "Pacific/Auckland",
}


def get_time(city: str):
    try:
        api_key = os.environ.get("RAPIDAPI_KEY")
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "world-time-api3.p.rapidapi.com"
        }

        key = city.lower().strip()
        timezone_str = CITY_TIMEZONES.get(key)
        if not timezone_str:
            guessed = city.replace(" ", "_")
            for region in ["America", "Europe", "Asia", "Pacific", "Australia", "Africa"]:
                test_url = f"https://world-time-api3.p.rapidapi.com/timezone/{region}/{guessed}"
                r = requests.get(test_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    timezone_str = f"{region}/{guessed}"
                    break
        if not timezone_str:
            cities = ", ".join(sorted(CITY_TIMEZONES.keys()))
            return f"❌ Couldn't find timezone for *{city}*.\n\nKnown cities: {cities}"
        url = f"https://world-time-api3.p.rapidapi.com/timezone/{timezone_str}"
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Time API status: {r.status_code}")
        print(f"Time API response: {r.text}")
        if r.status_code != 200:
            return f"❌ Could not fetch time for *{city}*. Try again shortly."
        data = r.json()
        dt_str = data["datetime"]
        abbr = data.get("abbreviation", "")
        utc_offset = data.get("utc_offset", "")
        day_of_week = data.get("day_of_week", 0)
        week_number = data.get("week_number", "")
        dt = datetime.fromisoformat(dt_str)
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        day_name = day_names[day_of_week]
        formatted = dt.strftime("%I:%M %p").lstrip("0")
        date_formatted = dt.strftime("%d %B %Y")
        return (
            f"🕐 *Time in {city.title()}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕰 *{formatted}*\n"
            f"📅 {day_name}, {date_formatted}\n"
            f"🌐 Timezone: {timezone_str}\n"
            f"⏱ UTC offset: {utc_offset} ({abbr})\n"
            f"📆 Week: {week_number}"
        )
     except Exception as e:
        print(f"Time error: {e}")
        import traceback
        traceback.print_exc()
        return "🕐 Could not fetch time data. Try again shortly."

# ─────────────────────────────────────────────
# SPORTS — ESPN hidden API (no key required)
# ─────────────────────────────────────────────

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

SPORT_CONFIG = {
    "nfl": {
        "url": f"{ESPN_BASE}/football/nfl/scoreboard",
        "params": {},
        "emoji": "🏈",
        "name": "NFL",
    },
    "nba": {
        "url": f"{ESPN_BASE}/basketball/nba/scoreboard",
        "params": {},
        "emoji": "🏀",
        "name": "NBA",
    },
    "mlb": {
        "url": f"{ESPN_BASE}/baseball/mlb/scoreboard",
        "params": {},
        "emoji": "⚾",
        "name": "MLB",
    },
    "f1": {
        "url": f"{ESPN_BASE}/racing/f1/scoreboard",
        "params": {},
        "emoji": "🏎️",
        "name": "Formula 1",
    },
    "rugby": {
        "url": f"{ESPN_BASE}/rugby/242041/scoreboard",   # league ID in path
        "params": {},
        "emoji": "🏉",
        "name": "Super Rugby Pacific",
    },
    "sixnations": {
        "url": f"{ESPN_BASE}/rugby/180659/scoreboard",   # league ID in path
        "params": {},
        "emoji": "🏉",
        "name": "Six Nations",
    },
    "championship": {
        "url": f"{ESPN_BASE}/rugby/244293/scoreboard",   # league ID in path
        "params": {},
        "emoji": "🏉",
        "name": "Rugby Championship",
    },
}
SPORT_ALIASES = {
    # F1
    "f1": "f1", "formula1": "f1", "formula 1": "f1",
    # NBA
    "nba": "nba", "basketball": "nba",
    # NFL
    "nfl": "nfl", "american football": "nfl", "gridiron": "nfl",
    # MLB
    "mlb": "mlb", "baseball": "mlb",
    # Rugby
    "rugby": "rugby", "super rugby": "rugby", "super rugby pacific": "rugby",
    "six nations": "sixnations", "sixnations": "sixnations", "6 nations": "sixnations",
    "rugby championship": "championship", "championship": "championship",
}


def get_sports(args: list):
    try:
        if not args:
            return (
                "🏆 *Sports Scores — ESPN Live Data*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "Usage: `/sports <sport>`\n\n"
                "🏉 *Rugby*\n"
                "  `/sports rugby` — Super Rugby Pacific\n"
                "  `/sports six nations`\n"
                "  `/sports rugby championship`\n\n"
                "🏎️ *Motorsport*\n"
                "  `/sports f1` — Formula 1\n\n"
                "🏀 *Basketball*\n"
                "  `/sports nba`\n\n"
                "⚾ *Baseball*\n"
                "  `/sports mlb`\n\n"
                "🏈 *American Football*\n"
                "  `/sports nfl`\n\n"
                "ℹ️ Data powered by ESPN."
            )

        # Join all args to catch multi-word sports like "six nations"
        query = " ".join(args).lower()
        sport_key = SPORT_ALIASES.get(query)

        # If no match on full query, try just the first word
        if not sport_key:
            sport_key = SPORT_ALIASES.get(args[0].lower())

        if not sport_key:
            return (
                f"❌ Unknown sport *{args[0]}*.\n\n"
                f"Try: `rugby`, `six nations`, `rugby championship`, "
                f"`f1`, `nba`, `mlb`, `nfl`"
            )

        config = SPORT_CONFIG[sport_key]
        url = config["url"]
        params = config.get("params", {})
        emoji = config["emoji"]
        name = config["name"]

        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 404:
            return (
                f"{emoji} *{name}*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ ESPN doesn't have a scoreboard for {name} right now.\n"
                f"This may be off-season or the league may not be covered."
            )

        if resp.status_code != 200:
            return f"{emoji} Could not reach ESPN for {name} data right now. Try again shortly."

        data = resp.json()
        events = data.get("events", [])

        if not events:
            season = data.get("season", {})
            season_name = season.get("type", {}).get("name", "")
            return (
                f"{emoji} *{name}*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"No games scheduled today.\n"
                f"{'Season type: ' + season_name if season_name else 'Check back on a match day!'}"
            )

        lines = [f"{emoji} *{name} — Scores*", "━━━━━━━━━━━━━━━━━━"]

        for event in events[:8]:
            competitions = event.get("competitions", [{}])
            if not competitions:
                continue
            competition = competitions[0]
            competitors = competition.get("competitors", [])
            status = event.get("status", {})
            state = status.get("type", {}).get("state", "")        # pre, in, post
            status_detail = status.get("type", {}).get("shortDetail", "")
            display_clock = status.get("displayClock", "")
            period = status.get("period", 0)

            if len(competitors) < 2:
                continue

            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

            home_name = home.get("team", {}).get("shortDisplayName", "?")
            away_name = away.get("team", {}).get("shortDisplayName", "?")
            home_score = home.get("score", "-")
            away_score = away.get("score", "-")

            # Determine winner for finished games
            home_winner = home.get("winner", False)
            away_winner = away.get("winner", False)

            # Format team names — bold the winner
            if state == "post":
                home_display = f"*{home_name}*" if home_winner else home_name
                away_display = f"*{away_name}*" if away_winner else away_name
            else:
                home_display = f"*{home_name}*"
                away_display = f"*{away_name}*"

            # Status icon and clock
            if state == "post":
                status_icon = "🔴 Final"
            elif state == "in":
                if sport_key == "f1":
                    status_icon = f"🟢 Live — Lap {period}"
                elif sport_key in ["nba", "nfl"]:
                    status_icon = f"🟢 Live — {display_clock} Q{period}"
                elif sport_key == "mlb":
                    status_icon = f"🟢 Live — Inning {period}"
                else:
                    status_icon = f"🟢 Live — {display_clock}"
            else:
                status_icon = f"📅 {status_detail}"

            lines.append(f"\n{status_icon}")
            if state == "pre":
                lines.append(f"  {away_display} vs {home_display}")
            else:
                lines.append(f"  {away_display} {away_score} – {home_score} {home_display}")

        lines.append(f"\n📡 Source: ESPN")
        return "\n".join(lines)

    except Exception as e:
        print(f"Sports error: {e}")
        return "🏆 Sports data unavailable right now. Try again shortly."


async def sports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(get_sports([]), parse_mode="Markdown")
        return
    sport = " ".join(context.args).lower()
    await update.message.reply_text(f"🏆 Fetching {sport.upper()} scores...", parse_mode="Markdown")
    result = get_sports(context.args)
    await update.message.reply_text(result, parse_mode="Markdown")

# ─────────────────────────────────────────────
# 7. BOT COMMANDS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Dave's Bot — Command Guide*\n"
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
        "₿ *CRYPTO*\n"
        "/crypto `[coins]` — Live prices, 24h change & market cap in USD\n"
        "Example: `/crypto` for top 5, or `/crypto btc eth doge`\n\n"
        "🕐 *TIME*\n"
        "/time `<city>` — Current time and date in any major city\n"
        "Example: `/time Auckland` or `/time New York`\n\n"
        "🏆 *SPORTS*\n"
        "/sports `<sport>` — Latest scores powered by ESPN\n"
        "Rugby: `rugby`, `six nations`, `rugby championship`\n"
        "Other: `f1`, `nba`, `mlb`, `nfl`\n"
        "Example: `/sports rugby` or `/sports six nations`\n\n"
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
async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("₿ Fetching crypto prices...", parse_mode="Markdown")
    result = get_crypto(context.args)
    await update.message.reply_text(result, parse_mode="Markdown")


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/time <city>` — e.g. `/time Tokyo` or `/time New York`",
            parse_mode="Markdown"
        )
        return
    city = " ".join(context.args)
    result = get_time(city)
    await update.message.reply_text(result, parse_mode="Markdown")

async def sports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(get_sports([]), parse_mode="Markdown")
        return
    sport = context.args[0].lower()
    await update.message.reply_text(f"🏆 Fetching {sport.upper()} results...", parse_mode="Markdown")
    result = get_sports(context.args)
    await update.message.reply_text(result, parse_mode="Markdown")

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
    app.add_handler(CommandHandler("crypto", crypto_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("sports", sports_command))

    await app.initialize()
    await app.start()
    print("Bot is alive — all systems go!")
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
