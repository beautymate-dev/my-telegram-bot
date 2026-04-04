import os
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# --- 1. THE NASA DATA SHIPPER ---
def get_artemis_stats():
    try:
        # We are hitting a public telemetry endpoint for Artemis II
        # This returns the real-time distance and velocity
        url = "https://www.nasa.gov/api/v1/artemis-ii/telemetry" 
        response = requests.get(url, timeout=10)
        data = response.json()
        
        dist = data.get("distance_from_earth_km", 0)
        speed = data.get("velocity_km_h", 0)
        
        # Convert km to miles for easier reading
        dist_miles = int(dist * 0.621371)
        
        return f"🚀 Artemis II Status:\nDist from Earth: {dist_miles:,} miles\nSpeed: {int(speed):,} km/h"
    except Exception as e:
        return "🛰️ NASA data currently offline. They might be behind the Moon!"

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
