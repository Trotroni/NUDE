import discord
from discord import app_commands, Embed, Color, Interaction
import logging
import os
from dotenv import load_dotenv
import RPi.GPIO as GPIO
import random
import asyncio
import subprocess

# ==== Setup GPIO ====
GPIO.setmode(GPIO.BCM)
LED_PIN = 23
<<<<<<< Updated upstream
MOTOR_PIN = 13
=======
>>>>>>> Stashed changes
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(MOTOR_PIN, GPIO.OUT)

# ==== Load env ====
load_dotenv("var.env")
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# ==== Logging ====
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

# ==== Bot setup ====
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ==== Synchronisation fiable des commandes ====
@bot.event
async def on_ready():
    logger.info(f"Connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(name="LED: {} | Moteur: {}".format(
        "ON" if GPIO.input(LED_PIN) else "OFF",
        "ON" if GPIO.input(MOTOR_PIN) else "OFF"
    )))
    
    await asyncio.sleep(3)  # délai de sécurité avant sync

    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild)
            logger.info(f"Commandes synchronisées pour le serveur {GUILD_ID}")
        else:
            await tree.sync()
            logger.info("Commandes synchronisées globalement")
    except Exception as e:
        logger.error(f"Erreur de synchronisation : {e}")

    # Envoi d'un message dans un canal au démarrage
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("✅ Bot en ligne sur Raspberry Pi !")

# ==== Commande LED ====
@tree.command(name="led", description="Allume ou éteint la LED", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(state="on pour allumer, off pour éteindre")
async def led(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(LED_PIN, GPIO.HIGH)
        await interaction.response.send_message("LED allumée")
    elif state == "off":
        GPIO.output(LED_PIN, GPIO.LOW)
        await interaction.response.send_message("LED éteinte")
    else:
        await interaction.response.send_message("Utilise `/led on` ou `/led off`")
    await bot.change_presence(activity=discord.Game(name=f"LED: {'ON' if GPIO.input(LED_PIN) else 'OFF'}"))

# ==== Commande MOTEUR ====
@tree.command(name="moteur", description="Active ou désactive le moteur", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(state="on pour activer, off pour désactiver")
async def moteur(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
        await interaction.response.send_message("Moteur activé")
    elif state == "off":
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        await interaction.response.send_message("Moteur désactivé")
    else:
        await interaction.response.send_message("Utilise `/moteur on` ou `/moteur off`")

# ==== Commande ÉTAT ====
@tree.command(name="etat", description="Affiche l'état du moteur et de la LED", guild=discord.Object(id=GUILD_ID))
async def etat(interaction: Interaction):
    led_state = "ON" if GPIO.input(LED_PIN) else "OFF"
    motor_state = "ON" if GPIO.input(MOTOR_PIN) else "OFF"
    await interaction.response.send_message(f"LED : {led_state}\nMoteur : {motor_state}")

# ==== Commande REBOOT ====
@tree.command(name="reboot", description="Redémarre le Raspberry Pi", guild=discord.Object(id=GUILD_ID))
async def reboot(interaction: Interaction):
    await interaction.response.send_message("Redémarrage du Raspberry Pi...")
    os.system("sudo reboot")

# ==== Lancement ====
if TOKEN:
    bot.run(TOKEN)
else:
    logger.error("DISCORD_TOKEN manquant dans var.env")
