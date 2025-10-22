#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord avec commandes personnalisées CSV, support multilingue et modération
Nécessite: discord.py 2.x, python-dotenv
Installation: pip install discord.py python-dotenv
"""

# ========================================
# IMPORTS
# ========================================

# Librairies standard
import os
import sys
import csv
import json
import logging
import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import time

# Librairies externes
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# ========================================
# CONFIGURATION ET INITIALISATION
# ========================================

# Charger d'abord les variables générales
load_dotenv(dotenv_path="var.env")

# Puis charger le token (écrase seulement si déjà défini dans var.env)
load_dotenv(dotenv_path="token.env", override=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID_BOT = os.getenv("CHANNEL_ID_BOT")
ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "fr")

# Vérification du token
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant dans le fichier .env")

# Chemins des fichiers
BASE_DIR = Path(__file__).parent
COMMANDS_CSV = BASE_DIR / "commands.csv"
LOGS_DIR = BASE_DIR / "logs"
LANG_DIR = BASE_DIR / "languages"
WARN_FILE = BASE_DIR / "warns.csv"

# Créer les dossiers si nécessaire
LOGS_DIR.mkdir(exist_ok=True)
LANG_DIR.mkdir(exist_ok=True)
WARN_FILE.touch(exist_ok=True)

# ========================================
# LOGGING
# ========================================

log_filename = LOGS_DIR / f"bot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DiscordBot')

# ========================================
# GESTION DES LANGUES
# ========================================

class LanguageManager:
    """Gestionnaire de traductions multilingues."""
    def __init__(self):
        self.translations = {}
        self.available_languages = []
        self.user_preferences = {}  # user_id: language_code

    def load_languages(self):
        self.translations.clear()
        self.available_languages.clear()

        files = list(LANG_DIR.glob("*.json"))
        if not files:
            logger.error(f"❌ Aucun fichier de langue dans {LANG_DIR}")
            raise FileNotFoundError("Aucun fichier de traduction")

        for file in files:
            lang_code = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                    self.available_languages.append(lang_code)
                logger.info(f"✅ Langue chargée : {lang_code}")
            except Exception as e:
                logger.error(f"❌ Erreur chargement {file} : {e}")

        if not self.available_languages:
            raise ValueError("Aucune langue valide chargée")

    def get(self, key: str, user_id: int = None, **kwargs) -> str:
        lang = self.user_preferences.get(user_id, DEFAULT_LANGUAGE)
        if lang not in self.translations:
            lang = DEFAULT_LANGUAGE
        translation = self.translations.get(lang, {}).get(key, f"[{key}]")
        try:
            return translation.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ Variable manquante pour '{key}': {e}")
            return translation

    def set_user_language(self, user_id: int, language: str) -> bool:
        if language in self.available_languages:
            self.user_preferences[user_id] = language
            return True
        return False

    def get_language_name(self, lang_code: str) -> str:
        return self.translations.get(lang_code, {}).get("language_name", lang_code)


lang_manager = LanguageManager()

# ========================================
# INITIALISATION DU BOT
# ========================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
custom_commands = {}

# ========================================
# UTILITAIRES
# ========================================

def t(key: str, interaction: discord.Interaction = None, **kwargs) -> str:
    user_id = interaction.user.id if interaction else None
    return lang_manager.get(key, user_id, **kwargs)

def is_admin(interaction: discord.Interaction) -> bool:
    if not ADMIN_ROLE_ID:
        logger.warning("⚠️ ADMIN_ROLE_ID non défini")
        return False
    try:
        admin_role_id = int(ADMIN_ROLE_ID)
        if interaction.user.guild_permissions.administrator:
            return True
        return any(role.id == admin_role_id for role in interaction.user.roles)
    except ValueError:
        logger.error(f"❌ ADMIN_ROLE_ID invalide : {ADMIN_ROLE_ID}")
        return False

# ========================================
# COMMANDES CSV
# ========================================

def load_custom_commands():
    global custom_commands
    custom_commands.clear()
    if not COMMANDS_CSV.exists():
        COMMANDS_CSV.touch()
        return
    try:
        with open(COMMANDS_CSV, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    custom_commands[row[0].strip().lower()] = row[1].strip()
        logger.info(f"✅ {len(custom_commands)} commandes personnalisées chargées")
    except Exception as e:
        logger.error(f"❌ Erreur chargement CSV : {e}")

def save_custom_commands():
    try:
        with open(COMMANDS_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for name, resp in custom_commands.items():
                writer.writerow([name, resp])
        return True
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde CSV : {e}")
        return False

# ========================================
# ANTI-SPAM POUR COMMANDES
# ========================================

command_cooldowns = defaultdict(lambda: 0)
COMMAND_COOLDOWN = 3

async def check_command_cooldown(user_id: int, channel) -> bool:
    now = time.time()
    if now < command_cooldowns[user_id]:
        await channel.send(f"⏱️ Cooldown actif ({command_cooldowns[user_id]-now:.1f}s restant)", delete_after=3)
        return False
    command_cooldowns[user_id] = now + COMMAND_COOLDOWN
    return True

# ========================================
# MODÉRATION - WARN / KICK TEMPORAIRE
# ========================================

WARN_LIMIT = 2
KICK_DURATION = 30

def load_warns():
    warns = {}
    try:
        with open(WARN_FILE, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    warns[int(row[0])] = {"count": int(row[1]), "reasons": json.loads(row[2])}
    except Exception as e:
        logger.error(f"Erreur chargement warns: {e}")
    return warns

def save_warns(warns):
    try:
        with open(WARN_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for uid, data in warns.items():
                writer.writerow([uid, data["count"], json.dumps(data["reasons"])])
    except Exception as e:
        logger.error(f"Erreur sauvegarde warns: {e}")

warns_data = load_warns()

# ========================================
# ÉVÉNEMENTS
# ========================================

@bot.event
async def on_ready():
    logger.info(f"✅ Bot connecté en tant que {bot.user}")
    try:
        lang_manager.load_languages()
    except Exception as e:
        logger.critical(f"Impossible de charger les langues : {e}")
        await bot.close()
        return
    load_custom_commands()
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
    except Exception as e:
        logger.error(f"Erreur synchronisation commandes : {e}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith('/'):
        command_name = message.content[1:].split()[0].lower()
        if command_name in custom_commands:
            await message.channel.send(custom_commands[command_name])
    await bot.process_commands(message)

# ========================================
# COMMANDES SLASH DE BASE
# ========================================

@bot.tree.command(name="ping", description="Teste la réactivité du bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(t("ping_response", interaction), ephemeral=True)

@bot.tree.command(name="help", description="Affiche toutes les commandes disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title=t("help_title", interaction),
        color=discord.Color.blue()
    )

    # Commandes système
    system_commands = (
        f"🟢 `/ping` - {t('help_ping', interaction)}\n"
        f"🟡 `/reboot` - {t('help_reboot', interaction)}\n"
        f"🟡 `/upgrade` - {t('help_upgrade', interaction)}\n"
        f"🟡 `/bot_update` - {t('help_bot_update', interaction)}"
    )
    embed.add_field(name=t("help_system", interaction), value=system_commands, inline=False)

    # Commandes CSV personnalisées
    csv_commands = (
        f"🟢 `/create` - {t('help_create', interaction)}\n"
        f"🟢 `/modif` - {t('help_modif', interaction)}\n"
        f"🟢 `/delete` - {t('help_delete', interaction)}\n"
        f"🟢 `/list` - {t('help_list', interaction)}\n"
        f"🟢 `/reload_commands` - {t('help_reload', interaction)}"
    )
    embed.add_field(name=t("help_csv", interaction), value=csv_commands, inline=False)

    # Commandes modération
    mod_commands = (
        f"🟠 `/warn` - Met un warn à un utilisateur\n"
        f"🟠 `/warns` - Voir les warns d'un utilisateur"
    )
    embed.add_field(name="⚠️ Modération", value=mod_commands, inline=False)

    # Commandes logs
    log_commands = (
        f"🔵 `/logs` - Affiche les derniers logs du bot\n"
        f"🔵 `/systemlog` - Affiche les logs système (systemd)"
    )
    embed.add_field(name="📜 Logs", value=log_commands, inline=False)

    # Commandes de langue
    embed.add_field(name=t("help_lang", interaction), value=f"🟢 `/language` - {t('help_language', interaction)}", inline=False)

    # Footer
    embed.set_footer(text=t("help_footer", interaction))

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================================
# COMMANDES MODÉRATION / LOGS
# ========================================

# WARN / KICK TEMPORAIRE
@bot.tree.command(name="warn", description="Met un warn à un utilisateur")
@app_commands.describe(user="Utilisateur", reason="Raison")
async def warn_command(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Pas la permission", ephemeral=True)
        return
    uid = user.id
    warns_data.setdefault(uid, {"count":0,"reasons":[]})
    warns_data[uid]["count"] += 1
    warns_data[uid]["reasons"].append(reason)
    save_warns(warns_data)
    await interaction.response.send_message(f"{user.mention} reçoit un warn ({reason}). Total: {warns_data[uid]['count']}", ephemeral=True)
    if warns_data[uid]["count"] >= WARN_LIMIT:
        await interaction.channel.send(f"{user.mention} kick temporaire ({KICK_DURATION}s)")
        try:
            await user.edit(communication_disabled_until=datetime.utcnow()+timedelta(seconds=KICK_DURATION))
        except Exception as e:
            logger.error(f"Erreur kick temporaire: {e}")

@bot.tree.command(name="warns", description="Voir warns utilisateur")
@app_commands.describe(user="Utilisateur")
async def warns_check(interaction: discord.Interaction, user: discord.Member):
    uid = user.id
    data = warns_data.get(uid)
    if not data:
        await interaction.response.send_message(f"{user.mention} aucun warn.", ephemeral=True)
        return
    reasons = "\n".join([f"{i+1}. {r}" for i,r in enumerate(data["reasons"])])
    await interaction.response.send_message(f"{user.mention} - {data['count']} warns :\n{reasons}", ephemeral=True)

# LOGS
@bot.tree.command(name="logs", description="Afficher derniers logs du bot")
@app_commands.describe(lines="Nombre de lignes")
async def logs_command(interaction: discord.Interaction, lines: int = 10):
    log_files = sorted(BASE_DIR.joinpath("logs").glob("bot_*.log"), reverse=True)
    if not log_files:
        await interaction.response.send_message("Aucun log", ephemeral=True)
        return
    last_log = log_files[0]
    with open(last_log,"r",encoding="utf-8") as f:
        content = f.readlines()[-lines:]
    embed = discord.Embed(title=f"Logs {last_log.name}", description="```\n" + "".join(content) + "\n```", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="systemlog", description="Afficher logs systemd")
@app_commands.describe(type="error/output", lines="Nombre de lignes")
async def systemlog_command(interaction: discord.Interaction, type: str, lines: int = 10):
    type = type.lower()
    if type not in ["error","output"]:
        await interaction.response.send_message("Type invalide", ephemeral=True)
        return
    log_file = BASE_DIR / f"logs/systemd_{type}.log"
    if not log_file.exists():
        await interaction.response.send_message(f"{log_file.name} introuvable", ephemeral=True)
        return
    with open(log_file,"r",encoding="utf-8") as f:
        content = f.readlines()[-lines:]
    embed = discord.Embed(title=f"Systemd {type} log", description="```\n" + "".join(content) + "\n```", color=discord.Color.orange() if type=="error" else discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================================
# LANCEMENT DU BOT
# ========================================

if __name__ == "__main__":
    try:
        logger.info("🚀 Démarrage du bot...")
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Arrêt manuel")
    except Exception as e:
        logger.critical(f"Erreur critique: {e}", exc_info=True)
        sys.exit(1)
