import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# This function tells the bot what to do when it gets a message
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    # The bot will reply with the exact same message you sent it
    await update.message.reply_text(f"You said: {user_message}")

async def main():
    # ⚠️ REPLACE THE TEXT BELOW WITH YOUR ACTUAL BOT TOKEN FROM BOTFATHER
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    
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
