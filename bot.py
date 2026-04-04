import os
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# --- 1. THE NASA DATA SHIPPER ---
def get_artemis_stats():
    try:
        # This is the official NASA AROW (Artemis Real-time Orbit Website) data feed
        url = "https://www.nasa.gov/trackartemis/telemetry.json"
        
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return "🛰️ NASA's AROW server is under heavy load. Try again in a minute!"

        data = response.json()
        
        # NASA's AROW JSON format for Artemis II
        dist_km = data.get("distanceToEarth", 0)
        velocity = data.get("velocity", 0)
        
        # Convert to miles (since we're tracking a US/International mission)
        dist_miles = int(dist_km * 0.621371)
        
        return (f"🚀 **ARTEMIS II: MISSION STATUS**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🌍 **Distance:** {dist_miles:,} miles from Earth\n"
                f"💨 **Speed:** {int(velocity):,} km/h\n"
                f"🌕 **Status:** Trans-lunar Coast\n"
                f"📅 **Note:** Approaching the Moon!")

    except Exception as e:
        print(f"Connection Error: {e}")
        return "🛰️ Unable to reach Orion. NASA's live telemetry might be in a blackout period."

# --- 2. THE BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Space Tracker Active. Use /artemis for live mission data.")

async def artemis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = get_artemis_stats()
    await update.message.reply_text(status)

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}. Try /artemis for a space update!")

# --- 3. THE MAIN BRAIN ---
async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("ERROR: No BOT_TOKEN found!")
        return

    app = ApplicationBuilder().token(bot_token).build()
    
    # Register our commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("artemis", artemis_command))
    
    # Handle regular text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    
    await app.initialize()
    await app.start()
    print("Bot is alive with Artemis tracking!")
    await app.updater.start_polling()
    
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
