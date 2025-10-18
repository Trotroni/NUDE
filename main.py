import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
import csv

# Charger le token depuis .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Préfixe pour les commandes slash
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Chargement des commandes personnalisées depuis commands.csv
custom_commands = {}
commands_path = os.path.join(os.path.dirname(__file__), "commands.csv")
if os.path.exists(commands_path):
    with open(commands_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                custom_commands[row[0].strip()] = row[1].strip()

# Dossier audio
audio_folder = os.path.join(os.path.dirname(__file__), "audio")
if not os.path.exists(audio_folder):
    print("⚠️ Dossier audio introuvable :", audio_folder)
else:
    print("🎵 Dossier audio détecté :", audio_folder)

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

    # Synchronisation des commandes slash
    try:
        await bot.tree.sync()
        print("🔄 Commandes slash synchronisées globalement")
    except Exception as e:
        print("⚠️ Erreur lors de la synchronisation des commandes :", e)

# Commande /reload_commands pour recharger les commandes CSV sans redémarrer le bot
@bot.tree.command(name="reload_commands", description="Recharge les commandes personnalisées depuis le fichier CSV")
async def reload_commands(interaction: discord.Interaction):
    global custom_commands
    custom_commands.clear()
    with open(commands_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                custom_commands[row[0].strip()] = row[1].strip()
    await interaction.response.send_message("🔄 Commandes personnalisées rechargées !")

# Gestion des messages
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # 1️⃣ Commandes personnalisées
    if message.content.startswith("/"):
        cmd = message.content[1:].strip()
        if cmd in custom_commands:
            await message.channel.send(custom_commands[cmd])
            return

    # 2️⃣ Si message contient une image ou un lien → envoi d’un audio aléatoire dans #meme
    if message.attachments or "http" in message.content:
        guild = message.guild
        meme_channel = discord.utils.get(guild.text_channels, name="meme")
        if meme_channel and os.path.exists(audio_folder):
            audio_files = [f for f in os.listdir(audio_folder) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
            if audio_files:
                chosen = random.choice(audio_files)
                await meme_channel.send(file=discord.File(os.path.join(audio_folder, chosen)))
                print(f"📤 Fichier audio envoyé : {chosen}")

    await bot.process_commands(message)

bot.run(TOKEN)
