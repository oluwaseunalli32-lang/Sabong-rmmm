import os
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
MEALDB_URL = "https://www.themealdb.com/api/json/v1/1/"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Startup Hook: Clear leftover webhook ---
async def post_init(application):
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared. Starting polling mode.")
    except Exception as e:
        logger.error(f"Failed to clear webhook: {e}", exc_info=True)


# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! I can give you dish ideas and cooking steps.\n\n"
        "Try /random for a surprise dish, or send an ingredient like /chicken."
    )


async def random_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(MEALDB_URL + "random.php", timeout=10)
        data = response.json()
        meal = data["meals"][0]

        name = meal["strMeal"]
        category = meal["strCategory"]
        instructions = meal["strInstructions"]
        image_url = meal["strMealThumb"]

        message = f"🍽️ *{name}*\n_Category: {category}_\n\n*Instructions:*\n{instructions}"

        await update.message.reply_photo(
            photo=image_url,
            caption=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error fetching recipe: {e}", exc_info=True)
        await update.message.reply_text("Sorry, I couldn't fetch a recipe. Try again later.")


async def search_by_ingredient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please specify an ingredient. Example: /chicken")
        return

    ingredient = context.args[0]
    try:
        response = requests.get(MEALDB_URL + f"filter.php?i={ingredient}", timeout=10)
        data = response.json()

        if not data.get("meals"):
            await update.message.reply_text(f"No recipes found with *{ingredient}*. Try another!")
            return

        dishes = [meal["strMeal"] for meal in data["meals"][:5]]
        reply = f"Found some ideas with *{ingredient}*:\n" + "\n".join([f"• {d}" for d in dishes])
        reply += "\n\nUse /random for a full recipe with instructions."

        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error searching: {e}", exc_info=True)
        await update.message.reply_text("Something went wrong. Please try again.")


# --- Main ---
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable is not set.")
        raise SystemExit(1)

    # Explicit event loop for Python 3.14+ compatibility
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("random", random_recipe))
    application.add_handler(CommandHandler(["chicken", "beef", "rice", "pasta"], search_by_ingredient))

    logger.info("Bot started with polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
