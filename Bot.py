import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically
PORT = int(os.environ.get("PORT", 10000))
MEALDB_URL = "https://www.themealdb.com/api/json/v1/1/"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! I can give you dish ideas and cooking steps.\n"
        "Try `/random` for a surprise dish, or send an ingredient like `/chicken`."
    )

async def random_recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(MEALDB_URL + "random.php")
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
        logging.error(f"Error fetching recipe: {e}")
        await update.message.reply_text("Sorry, I couldn't fetch a recipe. Try again later.")

async def search_by_ingredient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please specify an ingredient. Example: `/chicken`")
        return

    ingredient = context.args[0]
    try:
        response = requests.get(MEALDB_URL + f"filter.php?i={ingredient}")
        data = response.json()

        if not data.get("meals"):
            await update.message.reply_text(f"No recipes found with *{ingredient}*. Try another!")
            return

        dishes = [meal["strMeal"] for meal in data["meals"][:5]]
        reply = f"Found some ideas with *{ingredient}*:\n" + "\n".join([f"• {d}" for d in dishes])
        reply += "\n\nUse `/random` for a full recipe with instructions."

        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error searching: {e}")
        await update.message.reply_text("Something went wrong. Please try again.")

# --- Webhook Application ---
async def healthcheck(request):
    return PlainTextResponse("OK")

async def webhook(request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return PlainTextResponse("OK")
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return PlainTextResponse("Error", status_code=500)

# --- Build Telegram Application ---
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("random", random_recipe))
application.add_handler(CommandHandler(["chicken", "beef", "rice", "pasta"], search_by_ingredient))

# --- Starlette App (for Render Web Service) ---
app = Starlette(routes=[
    Route("/", healthcheck),
    Route("/healthcheck", healthcheck),
    Route("/webhook", webhook, methods=["POST"]),
])

# --- Startup: Set Telegram Webhook ---
@app.on_event("startup")
async def on_startup():
    await application.initialize()
    await application.start()
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    await application.bot.set_webhook(url=webhook_url)
    logging.info(f"Webhook set to: {webhook_url}")

@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
