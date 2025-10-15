import discord
from discord import app_commands, Interaction, Embed
import logging
import os
import random
import RPi.GPIO as GPIO
from dotenv import load_dotenv
import asyncio
import subprocess

# === CONFIG GPIO ===
GPIO.setmode(GPIO.BCM)
LED_PIN = 23
MOTOR_PIN = 13
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.setup(MOTOR_PIN, GPIO.OUT)

# === CONFIG ENV ===
load_dotenv("var.env")
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
TEXT_CHANNEL_ID = int(os.getenv("TEXT_CHANNEL_ID", 0))
VOICE_CHANNEL_ID = int(os.getenv("VOICE_CHANNEL_ID", 0))

# === LOGGING ===
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

# === DISCORD CLIENT ===
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# === HELPERS ===
def led_state() -> str:
    return "ON" if GPIO.input(LED_PIN) else "OFF"

def motor_state() -> str:
    return "ON" if GPIO.input(MOTOR_PIN) else "OFF"

async def update_status():
    """Met à jour l'activité du bot selon l'état de la LED"""
    await bot.change_presence(activity=discord.Game(name=f"LED: {led_state()}"))

async def play_random_audio():
    """Lit un fichier audio aléatoire dans le salon vocal"""
    folder = "/home/trotroni/discord-bot/NUDE/audio"
    if not os.path.isdir(folder):
        logger.warning("Dossier audio introuvable.")
        return

    files = [f for f in os.listdir(folder) if f.endswith(('.mp3', '.wav', '.ogg'))]
    if not files:
        logger.warning("Aucun fichier audio trouvé.")
        return

    file_path = os.path.join(folder, random.choice(files))
    vc = await bot.get_channel(VOICE_CHANNEL_ID).connect()
    vc.play(discord.FFmpegPCMAudio(file_path))
    while vc.is_playing():
        await asyncio.sleep(1)
    await vc.disconnect()

# === EVENTS ===
@bot.event
async def on_ready():
    logger.info(f"Connecté en tant que {bot.user}")
    await update_status()

    if TEXT_CHANNEL_ID:
        channel = bot.get_channel(TEXT_CHANNEL_ID)
        await channel.send("Le bot est en ligne et opérationnel.")

    # Lance la lecture audio aléatoire
    try:
        await play_random_audio()
    except Exception as e:
        logger.error(f"Erreur audio : {e}")

    # Sync des commandes
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        await tree.sync(guild=guild)
    else:
        await tree.sync()

# === COMMANDES ===
@tree.command(name="led", description="Contrôle la LED (GPIO 23)")
@app_commands.describe(state="on / off")
async def led(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(LED_PIN, GPIO.HIGH)
        await interaction.response.send_message("LED allumée.")
    elif state == "off":
        GPIO.output(LED_PIN, GPIO.LOW)
        await interaction.response.send_message("LED éteinte.")
    else:
        await interaction.response.send_message("Utilise /led on ou /led off.")
    await update_status()

@tree.command(name="moteur", description="Contrôle le moteur (GPIO 13)")
@app_commands.describe(state="on / off")
async def moteur(interaction: Interaction, state: str):
    state = state.lower()
    if state == "on":
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
        await interaction.response.send_message("Moteur activé.")
    elif state == "off":
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        await interaction.response.send_message("Moteur désactivé.")
    else:
        await interaction.response.send_message("Utilise /moteur on ou /moteur off.")

@tree.command(name="etat", description="Affiche l'état du moteur et de la LED")
async def etat(interaction: Interaction):
    led_s = led_state()
    motor_s = motor_state()
    await interaction.response.send_message(f"LED: {led_s}\nMoteur: {motor_s}")

@tree.command(name="reboot", description="Redémarre le Raspberry Pi (admin uniquement)")
async def reboot(interaction: Interaction):
    await interaction.response.send_message("Redémarrage du Raspberry Pi en cours...")
    os.system("sudo reboot")

# === RUN ===
if TOKEN:
    bot.run(TOKEN)
else:
    logger.error("DISCORD_TOKEN manquant dans var.env")
