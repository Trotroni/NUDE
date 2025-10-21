# 🌍 Guide du système de traductions

## 📁 Structure des fichiers

```
votre_projet/
├── main.py                  # Script principal du bot
├── .env                     # Variables d'environnement
├── commands.csv             # Commandes personnalisées
├── languages/               # 📂 Dossier des traductions
│   ├── fr.json             # Français (par défaut)
│   ├── en.json             # Anglais
│   └── es.json             # Espagnol (exemple)
└── logs/                    # Logs du bot
```

## 🚀 Installation rapide

1. **Créer le dossier `languages/`** dans le même répertoire que `main.py`
2. **Copier les fichiers JSON** (`fr.json`, `en.json`, etc.) dans ce dossier
3. **Configurer la langue par défaut** dans `.env` :
   ```env
   DEFAULT_LANGUAGE=fr
   ```

## ✏️ Ajouter une nouvelle langue

### Étape 1 : Créer le fichier JSON

Créez un nouveau fichier dans `languages/` avec le code de langue (ex: `de.json` pour l'allemand).

### Étape 2 : Structure du fichier

Copiez la structure d'un fichier existant et traduisez toutes les clés :

```json
{
  "language_name": "Deutsch",
  "ping_response": "Pong! 🏓",
  "help_title": "📚 Hilfe - Verfügbare Befehle",
  ...
}
```

### Étape 3 : Redémarrer le bot

Le bot détectera automatiquement la nouvelle langue au démarrage.

## 🔑 Liste des clés de traduction

### Informations générales
- `language_name` : Nom de la langue (affiché dans `/language`)
- `ping_response` : Réponse de la commande `/ping`

### Commande `/help`
- `help_title` : Titre de l'embed d'aide
- `help_system` : Section des commandes système
- `help_csv` : Section des commandes CSV
- `help_lang` : Section langue
- `help_footer` : Pied de page
- `help_ping`, `help_reboot`, `help_upgrade` : Descriptions
- `help_create`, `help_modif`, `help_reload`, `help_list` : Descriptions
- `help_language` : Description

### Commande `/list`
- `list_title` : Titre de la liste
- `list_empty` : Message si aucune commande
- `list_footer` : Pied de page (utilise `{count}`)

### Commande `/create`
- `create_exists` : Commande existe déjà (utilise `{name}`)
- `create_success` : Succès (utilise `{name}`)
- `create_error` : Erreur

### Commande `/modif`
- `modif_not_found` : Commande introuvable (utilise `{name}`)
- `modif_success` : Succès (utilise `{name}`)
- `modif_error` : Erreur

### Commande `/reload_commands`
- `reload_success` : Succès (utilise `{count}`)
- `reload_error` : Erreur (utilise `{error}`)

### Commande `/upgrade`
- `upgrade_updating` : Message en cours
- `upgrade_success` : Succès (utilise `{output}`)
- `upgrade_restarting` : Redémarrage
- `upgrade_timeout` : Timeout
- `upgrade_error` : Erreur (utilise `{error}`)

### Commande `/reboot`
- `reboot_message` : Message de redémarrage

### Commande `/bot_update`
- `bot_update_sent` : Notification envoyée
- `bot_update_not_configured` : Non configuré
- `bot_update_channel_not_found` : Salon introuvable
- `bot_update_notification` : Message de notification
- `bot_update_error` : Erreur (utilise `{error}`)

### Commande `/language`
- `language_changed` : Langue changée (utilise `{language}`)
- `language_list` : Titre de la liste
- `language_current` : Langue actuelle (utilise `{language}`)

### Messages généraux
- `no_permission` : Pas de permission
- `bot_online` : Message de démarrage

## 💡 Variables dynamiques

Certaines traductions contiennent des variables entre accolades :

- `{count}` : Nombre de commandes
- `{name}` : Nom d'une commande
- `{error}` : Message d'erreur
- `{output}` : Sortie de commande
- `{language}` : Nom de la langue

**Exemple :**
```json
"reload_success": "✅ Commandes rechargées ! {count} commande(s) disponible(s)."
```

## 🎯 Utilisation par les utilisateurs

### Changer de langue
```
/language fr    → Passer en français
/language en    → Passer en anglais
/language       → Voir les langues disponibles
```

### Préférences
- Chaque utilisateur peut avoir **sa propre langue**
- La préférence est stockée **en mémoire** (réinitialisée au redémarrage)
- La langue par défaut est définie dans `.env` avec `DEFAULT_LANGUAGE`

## ⚙️ Configuration avancée

### Langue par défaut
Dans `.env` :
```env
DEFAULT_LANGUAGE=fr
```

### Langue de secours
Si une langue n'est pas trouvée, le bot utilise :
1. La langue de l'utilisateur (si définie)
2. `DEFAULT_LANGUAGE`
3. La première langue disponible dans `/languages/`

### Fichiers manquants
Si aucun fichier de traduction n'existe au démarrage, le bot affiche un avertissement dans les logs mais continue de fonctionner.

## 🔧 Dépannage

### Le bot ne trouve pas les traductions
✅ Vérifiez que le dossier `languages/` existe  
✅ Vérifiez que les fichiers JSON sont bien encodés en UTF-8  
✅ Vérifiez les logs dans `/logs/` pour voir les erreurs

### Une clé de traduction manque
Le bot affichera la **clé elle-même** si une traduction est manquante :
```
help_title  (au lieu du texte traduit)
```

### Ajouter des traductions personnalisées
Vous pouvez ajouter vos propres clés dans les fichiers JSON et les utiliser dans le code avec :
```python
t("ma_cle_personnalisee", interaction)
```

## 📝 Exemple complet

### Créer une nouvelle langue (italien)

**Fichier : `languages/it.json`**
```json
{
  "language_name": "Italiano",
  "ping_response": "Pong! 🏓",
  "help_title": "📚 Aiuto - Comandi disponibili",
  "no_permission": "⚠️ Non hai il permesso di usare questo comando.",
  ...
}
```

Redémarrez le bot, puis :
```
/language it
```

✅ Le bot parlera maintenant italien pour cet utilisateur !

## 🌟 Langues suggérées

Voici des codes de langue ISO 639-1 courants :

| Code | Langue        | Fichier      | Disponible |
|------|---------------|--------------|---------------|
| `fr` | Français      | `fr.json`    |      Oui      |
| `en` | Anglais       | `en.json`    |      Non      |
| `es` | Espagnol      | `es.json`    |      Non      |
| `de` | Allemand      | `de.json`    |      Non      |
| `it` | Italien       | `it.json`    |      Non      |
| `pt` | Portugais     | `pt.json`    |      Non      |
| `ja` | Japonais      | `ja.json`    |      Non      |
| `zh` | Chinois       | `zh.json`    |      Non      |
| `ru` | Russe         | `ru.json`    |      Non      |
| `ar` | Arabe         | `ar.json`    |      Non      |

---

💬 **Besoin d'aide ?** Consultez les logs dans `/logs/` pour tout problème lié aux traductions.
