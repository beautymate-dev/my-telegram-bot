import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ... (keep your reply function at the top) ...

async def main():
    # This line is the magic part for Railway
    bot_token = os.environ.get("BOT_TOKEN")
    
    # This check helps us see if the token is actually being found
    if not bot_token:
        print("ERROR: No BOT_TOKEN found in environment variables!")
        return

    print("Bot is starting up...")
    app = ApplicationBuilder().token(bot_token).build() 
    
    # This tells the bot to listen for any text message and trigger the 'reply' function
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    
    await app.initialize()
    await app.start()
    print("Bot is alive! Press Ctrl+C in this window to stop it.")
    await app.updater.start_polling()
    
    # Keep the bot running
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
