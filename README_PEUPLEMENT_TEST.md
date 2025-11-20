# Peuplement de la Base de Données de Test - HIVMeet

Ce dossier contient les scripts pour peupler la base de données de l'application HIVMeet avec des données de test variées et réalistes.

## 📋 Vue d'Ensemble

Les scripts créent un environnement de test complet avec :
- **15 utilisateurs de test** avec des profils variés
- **Différents statuts de vérification** (vérifié, en attente, rejeté, expiré)
- **Utilisateurs premium et gratuits**
- **Photos de profil** téléchargées automatiquement
- **Likes et matches** entre utilisateurs compatibles
- **Messages de conversation** dans les matches
- **Blocages** entre certains utilisateurs
- **Activité récente** variée

## 🚀 Utilisation Rapide

### Option 1 : Script Principal (Recommandé)
```bash
python run_test_population.py
```

### Option 2 : Scripts Individuels
```bash
# 1. Créer les utilisateurs
python populate_test_users.py

# 2. Créer les interactions
python populate_test_interactions.py
```

## 📊 Utilisateurs de Test Créés

### 👨 Utilisateurs Masculins
- **Thomas** (35 ans) - Paris - Vérifié Premium
- **Marc** (39 ans) - Lyon - Vérifié Gratuit
- **Pierre** (29 ans) - Marseille - En attente Gratuit
- **Alex** (36 ans) - Toulouse - Vérifié Premium (Trans)
- **Samuel** (42 ans) - Bordeaux - Vérifié Premium
- **Paul** (33 ans) - Nice - Rejeté Gratuit
- **Antoine** (38 ans) - Montpellier - Vérifié Premium

### 👩 Utilisateurs Féminins
- **Sophie** (32 ans) - Paris - Vérifiée Premium
- **Marie** (37 ans) - Lyon - Vérifiée Gratuit
- **Julie** (28 ans) - Marseille - Non vérifiée Gratuit
- **Emma** (34 ans) - Toulouse - Vérifiée Premium (Trans)
- **Camille** (39 ans) - Bordeaux - Vérifiée Premium
- **Lisa** (36 ans) - Strasbourg - Expirée Gratuit
- **Nina** (30 ans) - Nantes - Vérifiée Gratuit

### 🏳️‍⚧️ Utilisateurs Non-Binaires
- **Riley** (31 ans) - Paris - Vérifié Gratuit
- **Jordan** (35 ans) - Lyon - Vérifié Premium

### 👨‍💼 Administrateur
- **Admin HIVMeet** - Paris - Admin Premium

## 🔑 Informations de Connexion

### Compte Administrateur
- **Email**: admin@hivmeet.com
- **Mot de passe**: adminpass123

### Comptes Utilisateurs
- **Mot de passe**: testpass123 (pour tous les utilisateurs)
- **Emails**: Voir la liste complète dans le rapport final

## 🎯 Caractéristiques des Utilisateurs

### Statuts de Vérification
- ✅ **Vérifiés** (11 utilisateurs)
- ⏳ **En attente** (1 utilisateur)
- ❌ **Rejetés** (1 utilisateur)
- ⏰ **Expirés** (1 utilisateur)
- 🔒 **Non vérifiés** (1 utilisateur)

### Statuts Premium
- 💎 **Premium** (8 utilisateurs)
- 🆓 **Gratuit** (7 utilisateurs)

### Répartition Géographique
- **Paris**: 3 utilisateurs
- **Lyon**: 3 utilisateurs
- **Marseille**: 2 utilisateurs
- **Toulouse**: 2 utilisateurs
- **Bordeaux**: 2 utilisateurs
- **Autres villes**: 3 utilisateurs

### Types de Relations Recherchées
- **Long terme**: 10 utilisateurs
- **Amitié**: 6 utilisateurs
- **Court terme**: 3 utilisateurs
- **Casual**: 3 utilisateurs

## 📸 Photos de Profil

### Téléchargement Automatique
- Photos téléchargées depuis Unsplash
- Catégories adaptées au genre de l'utilisateur
- Photos principales pour tous les utilisateurs
- Photos supplémentaires pour les utilisateurs premium (1-3 photos)

### Gestion des Erreurs
- Fallback vers des images par défaut en cas d'échec
- Gestion des timeouts et erreurs réseau
- Logs détaillés des tentatives de téléchargement

## 💕 Interactions Créées

### Likes
- Likes entre utilisateurs compatibles
- Super likes pour certains utilisateurs
- Timestamps répartis sur les 30 derniers jours

### Matches
- Matches basés sur les likes mutuels
- Statuts actifs pour tous les matches
- Timestamps cohérents avec les likes

### Messages
- 3-8 messages par conversation
- Messages variés et réalistes
- Statuts de lecture aléatoires
- Timestamps progressifs

### Blocages
- 2-5 blocages aléatoires
- Logs détaillés des blocages créés

## 🔧 Configuration Requise

### Dépendances Python
```bash
pip install django requests python-dateutil
```

### Configuration Django
- Base de données configurée et accessible
- Migrations appliquées
- Modèles d'authentification et de profils disponibles

### Modèles Requis
- `authentication.models.User`
- `profiles.models.Profile`
- `profiles.models.ProfilePhoto`
- `matching.models.Match`
- `matching.models.Like`
- `messaging.models.Message`

## ⚠️ Précautions

### Sauvegarde Automatique
- Le script principal crée une sauvegarde avant le peuplement
- Nom du fichier : `backup_before_population_YYYYMMDD_HHMMSS.json`

### Vérifications Préliminaires
- Contrôle des dépendances installées
- Vérification de la configuration Django
- Test de connexion à la base de données

### Gestion des Erreurs
- Timeout de 5 minutes par script
- Logs détaillés des erreurs
- Continuation en cas d'erreur partielle

## 📈 Statistiques Générées

### Données Créées
- **15 utilisateurs** de test
- **15 profils** complets
- **15-45 photos** de profil
- **20-60 likes** entre utilisateurs
- **10-30 matches** basés sur les likes mutuels
- **30-80 messages** dans les conversations
- **2-5 blocages** entre utilisateurs

### Métriques de Qualité
- Répartition équilibrée par genre
- Couverture géographique française
- Variété des statuts de vérification
- Mix premium/gratuit réaliste

## 🧪 Scénarios de Test

### 1. Test de Matching
- Connexion avec différents utilisateurs
- Test des filtres d'âge et de distance
- Vérification des préférences de genre

### 2. Test des Conversations
- Accès aux matches créés
- Lecture des messages
- Test des statuts de lecture

### 3. Test Premium
- Fonctionnalités premium (photos multiples)
- Différences entre comptes gratuits et premium
- Test des limitations

### 4. Test de Modération
- Connexion admin
- Gestion des utilisateurs non vérifiés
- Traitement des comptes rejetés

### 5. Test de Blocage
- Vérification des blocages créés
- Test de l'impact sur le matching
- Gestion des utilisateurs bloqués

## 🔄 Réinitialisation

### Nettoyage Complet
```bash
# Supprimer toutes les données de test
python manage.py flush --noinput

# Ou supprimer manuellement
python manage.py shell
>>> from authentication.models import User
>>> User.objects.filter(email__endswith='@test.com').delete()
```

### Restauration
```bash
# Restaurer depuis la sauvegarde
python manage.py loaddata backup_before_population_YYYYMMDD_HHMMSS.json
```

## 📝 Logs et Debugging

### Niveaux de Log
- ✅ Succès avec détails
- ⚠️ Avertissements
- ❌ Erreurs avec contexte
- 📊 Statistiques détaillées

### Fichiers de Log
- Sortie console détaillée
- Sauvegarde automatique
- Rapport final complet

## 🎯 Personnalisation

### Ajout d'Utilisateurs
Modifiez `TEST_USERS_DATA` dans `populate_test_users.py` :
```python
{
    'email': 'nouveau@test.com',
    'display_name': 'Nouveau',
    'birth_date': datetime(1990, 1, 1),
    'gender': 'male',
    # ... autres champs
}
```

### Modification des Interactions
Ajustez les paramètres dans `populate_test_interactions.py` :
- Nombre de likes par utilisateur
- Nombre de messages par conversation
- Types de messages

### Photos Personnalisées
Modifiez `download_random_photo()` pour :
- Utiliser d'autres sources d'images
- Changer les catégories de photos
- Ajuster les dimensions

## 📞 Support

En cas de problème :
1. Vérifiez les logs d'erreur
2. Contrôlez la configuration Django
3. Vérifiez les dépendances
4. Testez la connexion à la base de données

## 📄 Licence

Ces scripts sont fournis pour les tests de développement de l'application HIVMeet. 