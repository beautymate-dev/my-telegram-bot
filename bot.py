import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# 1. Enable logging (This helps you see what's happening in the Railway logs)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 2. Define the "Reply" action
# This is what the bot does when it receives a text message
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"Received message: {user_text}") # This will show up in your Railway logs
    await update.message.reply_text(f"You said: {user_text}")

# 3. The Main Bot Logic
async def main():
    # Grab the secret token from Railway's environment variables
    bot_token = os.environ.get("BOT_TOKEN")
    
    # Check if the token actually exists
    if not bot_token:
        print("ERROR: No BOT_TOKEN found in Railway environment variables!")
        return

    print("Bot is starting up...")
    
    # Build the bot application
    app = ApplicationBuilder().token(bot_token).build()
    
    # Tell the bot to use the 'reply' function for any text it receives
    # (~filters.COMMAND means "ignore things that start with /")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    
    # Start the engine
    await app.initialize()
    await app.start()
    
    print("Bot is alive! Go to Telegram and send it a message.")
    
    # This tells the bot to start looking for new messages
    await app.updater.start_polling()
    
    # This loop keeps the bot running forever on the server
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

# 4. Run the script
if __name__ == '__main__':
    asyncio.run(main())
