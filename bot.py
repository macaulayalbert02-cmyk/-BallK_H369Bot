import os
import re
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get token from environment variable (Railway sets this)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables!")

# Store reminders in memory (NOTE: Lost on restart!)
reminders = []

# Helper function to parse time strings like "30m", "2h", "1d", "15s"
def parse_time(time_str):
    time_str = time_str.lower()
    match = re.match(r"(\d+)([smhd])", time_str)
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    now = datetime.now()
    if unit == "s":
        return now + timedelta(seconds=value)
    elif unit == "m":
        return now + timedelta(minutes=value)
    elif unit == "h":
        return now + timedelta(hours=value)
    elif unit == "d":
        return now + timedelta(days=value)
    return None

# Parse specific time like "18:30" or "2026-07-25 09:00"
def parse_specific_time(time_str):
    now = datetime.now()
    try:
        # Try "HH:MM" format (today)
        if re.match(r"^\d{1,2}:\d{2}$", time_str):
            hours, minutes = map(int, time_str.split(":"))
            dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if dt < now:  # If time has passed today, set for tomorrow
                dt += timedelta(days=1)
            return dt
        # Try "YYYY-MM-DD HH:MM" format
        elif re.match(r"^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}$", time_str):
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except:
        return None
    return None

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your Reminder Bot!\n\n"
        "Commands:\n"
        "/remind <time> <message> - Set a reminder\n"
        "  Examples:\n"
        "  /remind 30m Call mom\n"
        "  /remind 2h Take a break\n"
        "  /remind 18:30 Go gym\n"
        "  /remind 2026-07-25 09:00 Meeting\n\n"
        "/list - Show all pending reminders\n"
        "/cancel <number> - Cancel a reminder by number\n"
        "/clear - Clear ALL your reminders"
    )

# /remind command
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text
    
    # Extract time and message
    parts = text.split(" ", 2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Please use: /remind <time> <message>\n"
            "Examples: /remind 30m Call mom, /remind 18:30 Go gym"
        )
        return
    
    time_str = parts[1]
    message = parts[2]
    
    # Try to parse the time
    remind_time = parse_time(time_str)
    if not remind_time:
        remind_time = parse_specific_time(time_str)
    
    if not remind_time:
        await update.message.reply_text(
            "❌ Invalid time format!\n"
            "Use: 30s, 15m, 2h, 1d, 18:30, or 2026-07-25 09:00"
        )
        return
    
    # Calculate time difference for confirmation
    now = datetime.now()
    diff = remind_time - now
    minutes = int(diff.total_seconds() / 60)
    seconds = int(diff.total_seconds() % 60)
    
    # Store the reminder
    reminder = {
        "user": user_id,
        "time": remind_time,
        "message": message,
        "created_at": now
    }
    reminders.append(reminder)
    
    # Confirm to user
    if minutes > 0:
        confirm = f"✅ Reminder set for {minutes} minute(s) from now!"
    else:
        confirm = f"✅ Reminder set for {seconds} second(s) from now!"
    
    await update.message.reply_text(
        f"{confirm}\n"
        f"⏰ When time comes, I'll remind you: \"{message}\"\n"
        f"(Reminder #{len(reminders)})"
    )
    
    logger.info(f"Reminder set for user {user_id}: {message} at {remind_time}")

# /list command
async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_reminders = [r for r in reminders if r["user"] == user_id]
    
    if not user_reminders:
        await update.message.reply_text("📭 You have no pending reminders.")
        return
    
    message = "📋 Your pending reminders:\n\n"
    for i, r in enumerate(user_reminders, 1):
        time_left = r["time"] - datetime.now()
        minutes = int(time_left.total_seconds() / 60)
        seconds = int(time_left.total_seconds() % 60)
        
        if minutes > 0:
            eta = f"{minutes}m {seconds}s"
        else:
            eta = f"{seconds}s"
        
        message += f"{i}. \"{r['message']}\" (in {eta})\n"
    
    await update.message.reply_text(message)

# /cancel command
async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    parts = update.message.text.split()
    
    if len(parts) < 2:
        await update.message.reply_text("❌ Please specify a number: /cancel 1")
        return
    
    try:
        index = int(parts[1]) - 1
        user_reminders = [r for r in reminders if r["user"] == user_id]
        
        if index < 0 or index >= len(user_reminders):
            await update.message.reply_text("❌ Invalid reminder number. Use /list to see your reminders.")
            return
        
        # Remove the reminder
        reminder_to_remove = user_reminders[index]
        reminders.remove(reminder_to_remove)
        await update.message.reply_text(f"✅ Reminder cancelled: \"{reminder_to_remove['message']}\"")
        
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number: /cancel 1")

# /clear command
async def clear_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_reminders = [r for r in reminders if r["user"] == user_id]
    
    if not user_reminders:
        await update.message.reply_text("📭 You have no reminders to clear.")
        return
    
    for r in user_reminders:
        reminders.remove(r)
    
    await update.message.reply_text(f"✅ Cleared all {len(user_reminders)} reminder(s).")

# Background task to check and send reminders
async def check_reminders(app: Application):
    """Check every 5 seconds if any reminder is due."""
    while True:
        try:
            now = datetime.now()
            due_reminders = [r for r in reminders if r["time"] <= now]
            
            for r in due_reminders:
                try:
                    await app.bot.send_message(
                        chat_id=r["user"],
                        text=f"⏰ REMINDER: {r['message']}"
                    )
                    logger.info(f"Sent reminder to user {r['user']}: {r['message']}")
                except Exception as e:
                    logger.error(f"Failed to send reminder: {e}")
                finally:
                    reminders.remove(r)
            
            await asyncio.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in reminder checker: {e}")
            await asyncio.sleep(10)

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Main function
async def main():
    """Start the bot."""
    # Create the Application
    app = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("cancel", cancel_reminder))
    app.add_handler(CommandHandler("clear", clear_reminders))
    
    # Register error handler
    app.add_error_handler(error_handler)
    
    # Start the reminder checker in background
    asyncio.create_task(check_reminders(app))
    
    # Start the bot
    logger.info("🤖 Reminder bot started! Waiting for commands...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
