#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord avec gestion de commandes personnalisées CSV et support multilingue
Nécessite: discord.py 2.x, python-dotenv
Installation: pip install discord.py python-dotenv
"""

import discord
from discord import app_commands
from discord.ext import commands
import os
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import sys
import subprocess

# ========================================
# CONFIGURATION ET INITIALISATION
# ========================================

# Charger les variables d'environnement
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')  # Optionnel
CHANNEL_ID_BOT = os.getenv('CHANNEL_ID_BOT')  # Optionnel
ADMIN_ROLE_ID = os.getenv('ADMIN_ROLE_ID')  # ID du rôle admin
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'fr')  # Langue par défaut

# Vérification du token
if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN manquant dans le fichier .env")

# Chemins des fichiers
BASE_DIR = Path(__file__).parent
COMMANDS_CSV = BASE_DIR / "commands.csv"
LOGS_DIR = BASE_DIR / "logs"
LANG_DIR = BASE_DIR / "languages"

# Créer les dossiers s'ils n'existent pas
LOGS_DIR.mkdir(exist_ok=True)
LANG_DIR.mkdir(exist_ok=True)

# Configuration du logging
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
# SYSTÈME DE TRADUCTION
# ========================================

class LanguageManager:
    """Gestionnaire de traductions multilingues."""
    
    def __init__(self):
        self.translations = {}
        self.available_languages = []
        self.user_preferences = {}  # user_id: language_code
        
    def load_languages(self):
        """Charge tous les fichiers de langue disponibles."""
        self.translations.clear()
        self.available_languages.clear()
        
        if not list(LANG_DIR.glob("*.json")):
            logger.error(f"❌ Aucun fichier de langue trouvé dans {LANG_DIR}/")
            logger.error("📝 Créez au moins un fichier JSON (ex: fr.json, en.json)")
            raise FileNotFoundError(f"Aucun fichier de traduction dans {LANG_DIR}/")
        
        for lang_file in LANG_DIR.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                    self.available_languages.append(lang_code)
                logger.info(f"✅ Langue chargée : {lang_code} ({self.translations[lang_code].get('language_name', lang_code)})")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur JSON dans {lang_file} : {e}")
            except Exception as e:
                logger.error(f"❌ Erreur lors du chargement de {lang_file} : {e}")
        
        if not self.available_languages:
            raise ValueError("❌ Aucune langue valide n'a pu être chargée")
        
        logger.info(f"✅ {len(self.available_languages)} langue(s) disponible(s) : {', '.join(self.available_languages)}")
    
    def get(self, key: str, user_id: int = None, **kwargs) -> str:
        """
        Récupère une traduction pour un utilisateur spécifique.
        
        Args:
            key: Clé de traduction
            user_id: ID de l'utilisateur (optionnel)
            **kwargs: Variables à formater dans la traduction
        """
        # Déterminer la langue de l'utilisateur
        lang = self.user_preferences.get(user_id, DEFAULT_LANGUAGE)
        
        # Si la langue n'existe pas, utiliser la langue par défaut
        if lang not in self.translations:
            lang = DEFAULT_LANGUAGE
        
        # Si la langue par défaut n'existe pas non plus, utiliser la première disponible
        if lang not in self.translations and self.available_languages:
            lang = self.available_languages[0]
        
        # Récupérer la traduction
        translation = self.translations.get(lang, {}).get(key, f"[{key}]")
        
        # Formater avec les variables
        try:
            return translation.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ Variable manquante dans la traduction '{key}': {e}")
            return translation
    
    def set_user_language(self, user_id: int, language: str):
        """Définit la langue préférée d'un utilisateur."""
        if language in self.available_languages:
            self.user_preferences[user_id] = language
            return True
        return False
    
    def get_language_name(self, lang_code: str) -> str:
        """Récupère le nom d'une langue."""
        return self.translations.get(lang_code, {}).get("language_name", lang_code)


# Initialiser le gestionnaire de langues
lang_manager = LanguageManager()


# ========================================
# INITIALISATION DU BOT
# ========================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Dictionnaire pour stocker les commandes personnalisées
custom_commands = {}


# ========================================
# FONCTIONS UTILITAIRES
# ========================================

def load_custom_commands():
    """Charge les commandes personnalisées depuis le fichier CSV."""
    global custom_commands
    custom_commands.clear()
    
    if not COMMANDS_CSV.exists():
        logger.warning(f"Fichier {COMMANDS_CSV} introuvable. Création d'un fichier vide.")
        COMMANDS_CSV.touch()
        return
    
    try:
        with open(COMMANDS_CSV, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    name = row[0].strip()
                    response = row[1].strip()
                    if name and response:
                        custom_commands[name.lower()] = response
        
        logger.info(f"✅ {len(custom_commands)} commandes personnalisées chargées depuis {COMMANDS_CSV}")
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des commandes CSV : {e}")


def save_custom_commands():
    """Sauvegarde les commandes personnalisées dans le fichier CSV."""
    try:
        with open(COMMANDS_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for name, response in custom_commands.items():
                writer.writerow([name, response])
        
        logger.info(f"✅ Commandes sauvegardées dans {COMMANDS_CSV}")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde des commandes : {e}")
        return False


def is_admin(interaction: discord.Interaction) -> bool:
    """Vérifie si l'utilisateur a le rôle admin."""
    if not ADMIN_ROLE_ID:
        logger.warning("⚠️ ADMIN_ROLE_ID non défini, accès refusé par défaut")
        return False
    
    try:
        admin_role_id = int(ADMIN_ROLE_ID)
        if interaction.user.guild_permissions.administrator:
            return True
        return any(role.id == admin_role_id for role in interaction.user.roles)
    except ValueError:
        logger.error(f"❌ ADMIN_ROLE_ID invalide : {ADMIN_ROLE_ID}")
        return False


def t(key: str, interaction: discord.Interaction = None, **kwargs) -> str:
    """Raccourci pour obtenir une traduction."""
    user_id = interaction.user.id if interaction else None
    return lang_manager.get(key, user_id, **kwargs)


# ========================================
# ÉVÉNEMENTS DU BOT
# ========================================

@bot.event
async def on_ready():
    """Événement déclenché lorsque le bot est prêt."""
    logger.info(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")
    
    # Charger les langues
    try:
        lang_manager.load_languages()
    except Exception as e:
        logger.critical(f"❌ Impossible de charger les langues : {e}")
        logger.critical("🛑 Arrêt du bot")
        await bot.close()
        return
    
    # Charger les commandes personnalisées
    load_custom_commands()
    
    # Synchroniser les commandes slash
    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info(f"✅ Commandes synchronisées pour la guilde {GUILD_ID}")
        else:
            await bot.tree.sync()
            logger.info("✅ Commandes synchronisées globalement")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation des commandes : {e}")
    
    # Envoyer notification de démarrage
    if CHANNEL_ID_BOT:
        try:
            channel = bot.get_channel(int(CHANNEL_ID_BOT))
            if channel:
                await channel.send(lang_manager.get("bot_online"))
                logger.info(f"✅ Notification envoyée au salon {CHANNEL_ID_BOT}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi de la notification : {e}")


@bot.event
async def on_message(message):
    """Gestion des messages pour les commandes personnalisées."""
    # Ignorer les messages du bot
    if message.author == bot.user:
        return
    
    # Vérifier si c'est une commande personnalisée
    if message.content.startswith('/'):
        command_name = message.content[1:].split()[0].lower()
        
        if command_name in custom_commands:
            try:
                await message.channel.send(custom_commands[command_name])
                logger.info(f"Commande personnalisée /{command_name} exécutée par {message.author}")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi de la réponse : {e}")
    
    # Traiter les autres commandes
    await bot.process_commands(message)


# ========================================
# COMMANDES SLASH - SYSTÈME
# ========================================

@bot.tree.command(name="ping", description="Teste la réactivité du bot")
async def ping(interaction: discord.Interaction):
    """Commande ping simple."""
    await interaction.response.send_message(t("ping_response", interaction), ephemeral=True)
    logger.info(f"Commande /ping exécutée par {interaction.user}")


@bot.tree.command(name="help", description="Affiche toutes les commandes disponibles")
async def help_command(interaction: discord.Interaction):
    """Affiche l'aide avec toutes les commandes disponibles."""
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
    
    # Commandes CSV
    csv_commands = (
        f"🟢 `/create` - {t('help_create', interaction)}\n"
        f"🟢 `/modif` - {t('help_modif', interaction)}\n"
        f"🟢 `/reload_commands` - {t('help_reload', interaction)}\n"
        f"🟢 `/list` - {t('help_list', interaction)}"
    )
    embed.add_field(name=t("help_csv", interaction), value=csv_commands, inline=False)
    
    # Commande langue
    lang_commands = f"🟢 `/language` - {t('help_language', interaction)}"
    embed.add_field(name=t("help_lang", interaction), value=lang_commands, inline=False)
    
    embed.set_footer(text=t("help_footer", interaction))
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"Commande /help exécutée par {interaction.user}")


# ========================================
# COMMANDES SLASH - LANGUE
# ========================================

@bot.tree.command(name="language", description="Change la langue du bot")
@app_commands.describe(lang="Code de la langue (ex: fr, en)")
async def language_command(interaction: discord.Interaction, lang: str = None):
    """Change la langue du bot pour l'utilisateur."""
    if lang is None:
        # Afficher les langues disponibles
        embed = discord.Embed(
            title=t("language_title", interaction),
            color=discord.Color.blue()
        )
        
        current_lang = lang_manager.user_preferences.get(interaction.user.id, DEFAULT_LANGUAGE)
        current_name = lang_manager.get_language_name(current_lang)
        
        embed.description = t("language_current", interaction, language=current_name) + "\n\n"
        embed.description += t("language_available", interaction) + "\n"
        
        for lang_code in sorted(lang_manager.available_languages):
            lang_name = lang_manager.get_language_name(lang_code)
            embed.description += f"• `{lang_code}` - {lang_name}\n"
        
        embed.set_footer(text=t("language_usage", interaction))
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Commande /language (affichage) exécutée par {interaction.user}")
    else:
        # Changer la langue
        lang = lang.lower().strip()
        if lang_manager.set_user_language(interaction.user.id, lang):
            lang_name = lang_manager.get_language_name(lang)
            await interaction.response.send_message(
                t("language_changed", interaction, language=lang_name),
                ephemeral=True
            )
            logger.info(f"Langue changée en {lang} pour {interaction.user}")
        else:
            await interaction.response.send_message(
                t("language_invalid", interaction, lang=lang),
                ephemeral=True
            )
            logger.warning(f"Tentative de changement vers langue invalide '{lang}' par {interaction.user}")


# ========================================
# COMMANDES SLASH - GESTION CSV
# ========================================

@bot.tree.command(name="list", description="Liste toutes les commandes personnalisées")
async def list_commands(interaction: discord.Interaction):
    """Liste toutes les commandes personnalisées."""
    if not custom_commands:
        await interaction.response.send_message(
            t("list_empty", interaction),
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title=t("list_title", interaction),
        color=discord.Color.green()
    )
    
    commands_list = "\n".join([f"• `/{name}`" for name in sorted(custom_commands.keys())])
    embed.description = commands_list
    embed.set_footer(text=t("list_footer", interaction, count=len(custom_commands)))
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(f"Commande /list exécutée par {interaction.user}")


@bot.tree.command(name="create", description="Crée une nouvelle commande personnalisée")
@app_commands.describe(
    name="Nom de la commande (sans le /)",
    response="Réponse que le bot enverra"
)
async def create_command(interaction: discord.Interaction, name: str, response: str):
    """Crée une nouvelle commande personnalisée."""
    name_lower = name.lower().strip()
    
    # Vérifier si la commande existe déjà
    if name_lower in custom_commands:
        await interaction.response.send_message(
            t("create_exists", interaction, name=name_lower),
            ephemeral=True
        )
        return
    
    # Ajouter la commande
    custom_commands[name_lower] = response.strip()
    
    if save_custom_commands():
        await interaction.response.send_message(
            t("create_success", interaction, name=name_lower),
            ephemeral=True
        )
        logger.info(f"Commande /{name_lower} créée par {interaction.user}")
    else:
        await interaction.response.send_message(
            t("create_error", interaction),
            ephemeral=True
        )


@bot.tree.command(name="modif", description="Modifie une commande personnalisée existante")
@app_commands.describe(
    old_name="Ancien nom de la commande",
    new_name="Nouveau nom de la commande (optionnel, laissez vide pour garder le même)",
    new_response="Nouvelle réponse"
)
async def modify_command(interaction: discord.Interaction, old_name: str, new_response: str, new_name: str = None):
    """Modifie une commande personnalisée existante."""
    old_name_lower = old_name.lower().strip()
    
    # Vérifier si la commande existe
    if old_name_lower not in custom_commands:
        await interaction.response.send_message(
            t("modif_not_found", interaction, name=old_name_lower),
            ephemeral=True
        )
        return
    
    # Si un nouveau nom est fourni
    if new_name:
        new_name_lower = new_name.lower().strip()
        
        # Vérifier que le nouveau nom n'existe pas déjà (sauf si c'est le même)
        if new_name_lower != old_name_lower and new_name_lower in custom_commands:
            await interaction.response.send_message(
                t("modif_name_exists", interaction, name=new_name_lower),
                ephemeral=True
            )
            return
        
        # Supprimer l'ancienne commande et créer la nouvelle
        del custom_commands[old_name_lower]
        custom_commands[new_name_lower] = new_response.strip()
        
        if save_custom_commands():
            await interaction.response.send_message(
                t("modif_success_rename", interaction, old_name=old_name_lower, new_name=new_name_lower),
                ephemeral=True
            )
            logger.info(f"Commande /{old_name_lower} renommée en /{new_name_lower} et modifiée par {interaction.user}")
        else:
            await interaction.response.send_message(
                t("modif_error", interaction),
                ephemeral=True
            )
    else:
        # Modifier seulement la réponse
        custom_commands[old_name_lower] = new_response.strip()
        
        if save_custom_commands():
            await interaction.response.send_message(
                t("modif_success", interaction, name=old_name_lower),
                ephemeral=True
            )
            logger.info(f"Commande /{old_name_lower} modifiée par {interaction.user}")
        else:
            await interaction.response.send_message(
                t("modif_error", interaction),
                ephemeral=True
            )


@bot.tree.command(name="delete", description="Supprime une commande personnalisée")
@app_commands.describe(
    name="Nom de la commande à supprimer"
)
async def delete_command(interaction: discord.Interaction, name: str):
    """Supprime une commande personnalisée."""
    name_lower = name.lower().strip()
    
    # Vérifier si la commande existe
    if name_lower not in custom_commands:
        await interaction.response.send_message(
            t("delete_not_found", interaction, name=name_lower),
            ephemeral=True
        )
        return
    
    # Supprimer la commande
    del custom_commands[name_lower]
    
    if save_custom_commands():
        await interaction.response.send_message(
            t("delete_success", interaction, name=name_lower),
            ephemeral=True
        )
        logger.info(f"Commande /{name_lower} supprimée par {interaction.user}")
    else:
        await interaction.response.send_message(
            t("delete_error", interaction),
            ephemeral=True
        )


@bot.tree.command(name="reload_commands", description="Recharge les commandes depuis le fichier CSV")
async def reload_commands(interaction: discord.Interaction):
    """Recharge les commandes personnalisées depuis le CSV."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        load_custom_commands()
        await interaction.followup.send(
            t("reload_success", interaction, count=len(custom_commands)),
            ephemeral=True
        )
        logger.info(f"Commandes rechargées par {interaction.user}")
    except Exception as e:
        await interaction.followup.send(
            t("reload_error", interaction, error=str(e)),
            ephemeral=True
        )
        logger.error(f"Erreur lors du rechargement des commandes : {e}")


# ========================================
# COMMANDES SLASH - ADMIN
# ========================================

@bot.tree.command(name="upgrade", description="Met à jour le bot via git pull et le relance")
async def upgrade(interaction: discord.Interaction):
    """Met à jour le bot via git et le relance (admin seulement)."""
    if not is_admin(interaction):
        await interaction.response.send_message(
            t("no_permission", interaction),
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Notification dans le salon bot
        if CHANNEL_ID_BOT:
            channel = bot.get_channel(int(CHANNEL_ID_BOT))
            if channel:
                await channel.send(t("upgrade_updating", interaction))
        
        # Exécuter git pull
        result = subprocess.run(
            ['git', 'pull'],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        logger.info(f"Git pull exécuté par {interaction.user} : {result.stdout}")
        
        await interaction.followup.send(
            t("upgrade_success", interaction, output=result.stdout),
            ephemeral=True
        )
        
        # Notification finale
        if CHANNEL_ID_BOT:
            channel = bot.get_channel(int(CHANNEL_ID_BOT))
            if channel:
                await channel.send(t("upgrade_restarting", interaction))
        
        # Relancer le bot
        logger.info("Relance du bot après upgrade")
        await bot.close()
        os.execv(sys.executable, ['python'] + sys.argv)
        
    except subprocess.TimeoutExpired:
        await interaction.followup.send(t("upgrade_timeout", interaction), ephemeral=True)
        logger.error("Timeout lors de git pull")
    except Exception as e:
        await interaction.followup.send(t("upgrade_error", interaction, error=str(e)), ephemeral=True)
        logger.error(f"Erreur lors de l'upgrade : {e}")


@bot.tree.command(name="reboot", description="Redémarre le serveur")
async def reboot(interaction: discord.Interaction):
    """Redémarre le serveur (admin seulement)."""
    if not is_admin(interaction):
        await interaction.response.send_message(
            t("no_permission", interaction),
            ephemeral=True
        )
        return
    
    await interaction.response.send_message(
        t("reboot_message", interaction),
        ephemeral=True
    )
    
    logger.warning(f"Reboot du serveur initié par {interaction.user}")
    
    try:
        subprocess.run(['sudo', 'reboot', 'now'], check=True)
    except Exception as e:
        logger.error(f"Erreur lors du reboot : {e}")
        await interaction.followup.send(
            t("reboot_error", interaction, error=str(e)),
            ephemeral=True
        )


@bot.tree.command(name="bot_update", description="Envoie une notification de mise à jour dans le salon bot")
async def bot_update(interaction: discord.Interaction):
    """Envoie une notification dans le salon bot (admin seulement)."""
    if not is_admin(interaction):
        await interaction.response.send_message(
            t("no_permission", interaction),
            ephemeral=True
        )
        return
    
    if not CHANNEL_ID_BOT:
        await interaction.response.send_message(
            t("bot_update_not_configured", interaction),
            ephemeral=True
        )
        return
    
    try:
        channel = bot.get_channel(int(CHANNEL_ID_BOT))
        if channel:
            await channel.send(t("bot_update_notification", interaction))
            await interaction.response.send_message(
                t("bot_update_sent", interaction),
                ephemeral=True
            )
            logger.info(f"Notification bot_update envoyée par {interaction.user}")
        else:
            await interaction.response.send_message(
                t("bot_update_channel_not_found", interaction),
                ephemeral=True
            )
    except Exception as e:
        await interaction.response.send_message(
            t("bot_update_error", interaction, error=str(e)),
            ephemeral=True
        )
        logger.error(f"Erreur lors de bot_update : {e}")


# ========================================
# GESTION DES ERREURS GLOBALES
# ========================================

@bot.event
async def on_error(event, *args, **kwargs):
    """Gestion des erreurs globales du bot."""
    logger.error(f"❌ Erreur dans l'événement {event}", exc_info=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Gestion des erreurs des commandes slash."""
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏱️ Commande en cooldown. Réessayez dans {error.retry_after:.1f}s",
            ephemeral=True
        )
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            t("no_permission", interaction),
            ephemeral=True
        )
    else:
        logger.error(f"❌ Erreur commande slash par {interaction.user}: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Une erreur s'est produite : {str(error)}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Une erreur s'est produite : {str(error)}",
                    ephemeral=True
                )
        except:
            pass


# ========================================
# LANCEMENT DU BOT
# ========================================

if __name__ == "__main__":
    try:
        logger.info("🚀 Démarrage du bot Discord...")
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt du bot par l'utilisateur (Ctrl+C)")
    except Exception as e:
        logger.critical(f"❌ Erreur critique lors du démarrage : {e}", exc_info=True)
        sys.exit(1)