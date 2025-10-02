import discord
from discord import app_commands
import logging
import os
from dotenv import load_dotenv

# ====== Load .env ======
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))  # Pour tester rapidement les commandes dans un serveur spécifique

# ====== Logging ======
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("discord_bot")
logger.info("Bot starting...")

# ====== Bot Setup ======
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====== Sync commands ======
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    if GUILD_ID:  # Sync uniquement pour un serveur de test
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        logger.info(f"Commands synced to guild {GUILD_ID}")
    else:
        await tree.sync()
        logger.info("Global commands synced")

# ====== Slash command example ======
@tree.command(name="ping", description="Répond avec Pong!", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")
    logger.info(f"Ping command used by {interaction.user}")

# ====== Run Bot ======
if TOKEN:
    bot.run(TOKEN)
else:
    logger.error("DISCORD_TOKEN not found in .env")
