#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord complet avec commandes CSV, multilingue, modération et logs
Nécessite: discord.py 2.x, python-dotenv
Installation: pip install discord.py python-dotenv
"""

# ========================================
# IMPORTS
# ========================================

import os
import sys
import csv
import json
import logging
import asyncio
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# ========================================
# CONFIGURATION ET INITIALISATION
# ========================================

# Charger les variables d'environnement
load_dotenv(dotenv_path="var.env")
load_dotenv(dotenv_path="token.env", override=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID_BOT = os.getenv("CHANNEL_ID_BOT")
ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "fr")

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant dans les fichiers .env")

# Chemins des fichiers
BASE_DIR = Path(__file__).parent
COMMANDS_CSV = BASE_DIR / "commands.csv"
LOGS_DIR = BASE_DIR / "logs"
LANG_DIR = BASE_DIR / "languages"
WARN_FILE = BASE_DIR / "warns.csv"

# Créer les dossiers/fichiers si nécessaires
LOGS_DIR.mkdir(exist_ok=True)
LANG_DIR.mkdir(exist_ok=True)
COMMANDS_CSV.touch(exist_ok=True)
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
logger = logging.getLogger("DiscordBot")

# ========================================
# GESTION DES LANGUES
# ========================================

class LanguageManager:
    """Gestionnaire de traductions multilingues"""
    def __init__(self):
        self.translations = {}
        self.available_languages = []
        self.user_preferences = {}

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
                logger.error(f"❌ Erreur chargement {file}: {e}")
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
# ANTI-SPAM COMMANDES
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
# MODÉRATION
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
    embed = discord.Embed(title=t("help_title", interaction), color=discord.Color.blue())
    
    system_commands = (
        f"🟢 `/ping` - {t('help_ping', interaction)}\n"
        f"🟡 `/reboot` - {t('help_reboot', interaction)}\n"
        f"🟡 `/upgrade` - {t('help_upgrade', interaction)}\n"
        f"🟡 `/bot_update` - {t('help_bot_update', interaction)}"
    )
    embed.add_field(name=t("help_system", interaction), value=system_commands, inline=False)
    
    csv_commands = (
        f"🟢 `/create` - {t('help_create', interaction)}\n"
        f"🟢 `/modif` - {t('help_modif', interaction)}\n"
        f"🟢 `/delete` - {t('help_delete', interaction)}\n"
        f"🟢 `/list` - {t('help_list', interaction)}\n"
        f"🟢 `/reload_commands` - {t('help_reload', interaction)}"
    )
    embed.add_field(name=t("help_csv", interaction), value=csv_commands, inline=False)

    mod_commands = (
        f"🟠 `/warn` - Met un warn à un utilisateur\n"
        f"🟠 `/warns` - Voir les warns d'un utilisateur"
    )
    embed.add_field(name="⚠️ Modération", value=mod_commands, inline=False)

    log_commands = (
        f"🔵 `/logs` - Affiche les derniers logs du bot\n"
        f"🔵 `/systemlog` - Affiche les logs système (systemd)"
    )
    embed.add_field(name="📜 Logs", value=log_commands, inline=False)

    embed.add_field(name=t("help_lang", interaction), value=f"🟢 `/language` - {t('help_language', interaction)}", inline=False)
    embed.set_footer(text=t("help_footer", interaction))

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================================
# COMMANDES LANGUE
# ========================================

@bot.tree.command(name="language", description="Change la langue du bot")
@app_commands.describe(lang="Code de la langue (ex: fr, en)")
async def language_command(interaction: discord.Interaction, lang: str = None):
    if lang is None:
        embed = discord.Embed(title=t("language_title", interaction), color=discord.Color.blue())
        current_lang = lang_manager.user_preferences.get(interaction.user.id, DEFAULT_LANGUAGE)
        current_name = lang_manager.get_language_name(current_lang)
        embed.description = t("language_current", interaction, language=current_name) + "\n\n"
        embed.description += t("language_available", interaction) + "\n"
        for lang_code in sorted(lang_manager.available_languages):
            embed.description += f"• `{lang_code}` - {lang_manager.get_language_name(lang_code)}\n"
        embed.set_footer(text=t("language_usage", interaction))
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        lang = lang.lower().strip()
        if lang_manager.set_user_language(interaction.user.id, lang):
            await interaction.response.send_message(t("language_changed", interaction, language=lang_manager.get_language_name(lang)), ephemeral=True)
        else:
            await interaction.response.send_message(t("language_invalid", interaction, lang=lang), ephemeral=True)

# ========================================
# COMMANDES CSV GESTION
# ========================================

@bot.tree.command(name="list", description="Liste toutes les commandes personnalisées")
async def list_commands(interaction: discord.Interaction):
    if not custom_commands:
        await interaction.response.send_message(t("list_empty", interaction), ephemeral=True)
        return
    embed = discord.Embed(title=t("list_title", interaction), color=discord.Color.green())
    embed.description = "\n".join([f"• `/{name}`" for name in sorted(custom_commands.keys())])
    embed.set_footer(text=t("list_footer", interaction, count=len(custom_commands)))
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="create", description="Crée une nouvelle commande personnalisée")
@app_commands.describe(name="Nom de la commande", response="Réponse du bot")
async def create_command(interaction: discord.Interaction, name: str, response: str):
    name_lower = name.lower().strip()
    if name_lower in custom_commands:
        await interaction.response.send_message(t("create_exists", interaction, name=name_lower), ephemeral=True)
        return
    custom_commands[name_lower] = response.strip()
    if save_custom_commands():
        await interaction.response.send_message(t("create_success", interaction, name=name_lower), ephemeral=True)
    else:
        await interaction.response.send_message(t("create_error", interaction), ephemeral=True)

@bot.tree.command(name="modif", description="Modifie une commande personnalisée existante")
@app_commands.describe(old_name="Ancien nom", new_response="Nouvelle réponse", new_name="Nouveau nom (optionnel)")
async def modify_command(interaction: discord.Interaction, old_name: str, new_response: str, new_name: str = None):
    old_name_lower = old_name.lower().strip()
    if old_name_lower not in custom_commands:
        await interaction.response.send_message(t("modif_not_found", interaction, name=old_name_lower), ephemeral=True)
        return
    if new_name:
        new_name_lower = new_name.lower().strip()
        if new_name_lower != old_name_lower and new_name_lower in custom_commands:
            await interaction.response.send_message(t("modif_name_exists", interaction, name=new_name_lower), ephemeral=True)
            return
        del custom_commands[old_name_lower]
        custom_commands[new_name_lower] = new_response.strip()
        if save_custom_commands():
            await interaction.response.send_message(t("modif_success_rename", interaction, old_name=old_name_lower, new_name=new_name_lower), ephemeral=True)
        else:
            await interaction.response.send_message(t("modif_error", interaction), ephemeral=True)
    else:
        custom_commands[old_name_lower] = new_response.strip()
        if save_custom_commands():
            await interaction.response.send_message(t("modif_success", interaction, name=old_name_lower), ephemeral=True)
        else:
            await interaction.response.send_message(t("modif_error", interaction), ephemeral=True)

@bot.tree.command(name="delete", description="Supprime une commande personnalisée")
@app_commands.describe(name="Nom de la commande à supprimer")
async def delete_command(interaction: discord.Interaction, name: str):
    name_lower = name.lower().strip()
    if name_lower not in custom_commands:
        await interaction.response.send_message(t("delete_not_found", interaction, name=name_lower), ephemeral=True)
        return
    del custom_commands[name_lower]
    if save_custom_commands():
        await interaction.response.send_message(t("delete_success", interaction, name=name_lower), ephemeral=True)
    else:
        await interaction.response.send_message(t("delete_error", interaction), ephemeral=True)

@bot.tree.command(name="reload_commands", description="Recharge les commandes depuis le CSV")
async def reload_commands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        load_custom_commands()
        await interaction.followup.send(t("reload_success", interaction, count=len(custom_commands)), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(t("reload_error", interaction, error=str(e)), ephemeral=True)

# ========================================
# COMMANDES MODÉRATION
# ========================================

@bot.tree.command(name="warn", description="Met un warn à un utilisateur")
@app_commands.describe(user="Utilisateur", reason="Raison")
async def warn_command(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Pas la permission", ephemeral=True)
        return
    uid = user.id
    warns_data.setdefault(uid, {"count": 0, "reasons": []})
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
        await interaction.response.send