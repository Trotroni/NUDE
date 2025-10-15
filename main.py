import discord
from discord import app_commands, Interaction, Color, Embed
import logging
import os
from dotenv import load_dotenv
import RPi.GPIO as GPIO
import subprocess

# ====== GPIO setup ======
GPIO.setmode(GPIO.BCM)
LED_PIN = 23
MOTOR_PIN = 13
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(MOTOR_PIN, GPIO.OUT)

# ====== Load .env ======
load_dotenv("var.env")
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))

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
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
        logger.info(f"Commands synced to guild {GUILD_ID}")
    else:
        await tree.sync()
        logger.info("Global commands synced")

# ====== Help command ======
@tree.command(
    name="help",
    description="Affiche un message d'aide",
    guild=discord.Object(id=GUILD_ID)
)
async def help_cmd(interaction: Interaction, message: str):
    await interaction.response.send_message(message)
    logger.info(f"Help command used by {interaction.user}")

# ====== Ping command ======
@tree.command(name="ping", description="Répond avec Pong!", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: Interaction):
    await interaction.response.send_message("Pong!")
    logger.info(f"Ping command used by {interaction.user}")

# ====== Say command ======
@tree.command(name="say", description="Le bot répète ton message joliment", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    message="Le texte que tu veux que le bot répète",
    couleur="Optionnel : red, green, blue, yellow"
)
async def say(interaction: Interaction, message: str, couleur: str = "blue"):
    color_map = {
        "red": Color.red(),
        "green": Color.green(),
        "blue": Color.blue(),
        "yellow": Color.yellow()
    }
    color = color_map.get(couleur.lower(), Color.blue())
    embed = Embed(title="Message", description=message, color=color)
    await interaction.response.send_message(embed=embed)

# ====== LED command ======
@tree.command(name="led", description="Allume ou éteint la LED", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(state="on pour allumer, off pour éteindre")
async def led(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(LED_PIN, GPIO.HIGH)
        await interaction.response.send_message("LED allumée.")
    elif state == "off":
        GPIO.output(LED_PIN, GPIO.LOW)
        await interaction.response.send_message("LED éteinte.")
    else:
        await interaction.response.send_message("Utilise `/led on` ou `/led off`")

# ====== Motor command ======
@tree.command(name="motor", description="Allume ou éteint le moteur", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(state="on pour allumer, off pour éteindre")
async def motor(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
        await interaction.response.send_message("Moteur activé.")
    elif state == "off":
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        await interaction.response.send_message("Moteur désactivé.")
    else:
        await interaction.response.send_message("Utilise `/motor on` ou `/motor off`")

# ====== Etat command ======
@tree.command(name="etat", description="Donne l'état actuel de la LED et du moteur", guild=discord.Object(id=GUILD_ID))
async def etat(interaction: Interaction):
    led_state = "allumée" if GPIO.input(LED_PIN) else "éteinte"
    motor_state = "activé" if GPIO.input(MOTOR_PIN) else "désactivé"
    await interaction.response.send_message(f"LED : {led_state}\nMoteur : {motor_state}")

# ====== Reboot command ======
@tree.command(name="reboot", description="Redémarre le Raspberry Pi", guild=discord.Object(id=GUILD_ID))
async def reboot_cmd(interaction: Interaction):
    await interaction.response.send_message("Redémarrage en cours...")
    # Execute reboot in background so the bot can respond immediately
    subprocess.Popen(["sudo", "reboot"])

# ====== Run Bot ======
if TOKEN:
    bot.run(TOKEN)
else:
    logger.error("DISCORD_TOKEN not found in var.env")
