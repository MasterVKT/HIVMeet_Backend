# HIVMeet Backend 🎯

**Application de rencontre spécialisée pour les personnes atteintes du VIH/SIDA**

Une API REST développée avec Django pour connecter les personnes vivant avec le VIH dans un environnement sécurisé et bienveillant.

## 🚀 Fonctionnalités Principales

### 👥 Gestion des Utilisateurs
- ✅ Inscription/Connexion avec Firebase Auth
- ✅ Profils détaillés avec photos
- ✅ Vérification d'email obligatoire
- ✅ Système de préférences de matching

### 💖 Système de Matching
- ✅ Algorithme de matching basé sur les critères
- ✅ Likes/SuperLikes/Boosts
- ✅ Système de matches mutuel
- ✅ Découverte de profils

### 💬 Messagerie
- ✅ Messages texte en temps réel
- ✅ Messages média (images, vidéos, audio)
- ✅ Appels audio/vidéo WebRTC
- ✅ Statuts de livraison et lecture

### 💎 Système Premium
- ✅ Abonnements mensuels/annuels via MyCoolPay
- ✅ Fonctionnalités premium (likes illimités, voir qui a liké, etc.)
- ✅ Gestion des webhooks de paiement
- ✅ Système de boosts et super-likes

### 📚 Ressources Éducatives
- ✅ Articles informatifs
- ✅ Catégorisation des contenus
- ✅ Support multilingue (FR/EN)

## 🛠️ Technologies Utilisées

- **Backend**: Django 4.2+ avec Django REST Framework
- **Base de données**: PostgreSQL
- **Cache**: Redis
- **Authentification**: Firebase Auth
- **Stockage**: Firebase Storage
- **Paiements**: MyCoolPay
- **Tâches asynchrones**: Celery
- **Documentation API**: Swagger/OpenAPI
- **Containerisation**: Docker & Docker Compose

## 📋 Prérequis

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js (pour certains outils de développement)
- Docker & Docker Compose (optionnel)

## ⚡ Installation Rapide

### 1. Cloner le Repository
```bash
git clone https://github.com/your-org/hivmeet-backend.git
cd hivmeet-backend
```

### 2. Installation avec Docker (Recommandé)
```bash
# Démarrer tous les services
docker-compose up -d

# Exécuter les migrations
docker-compose exec web python manage.py migrate

# Créer un superutilisateur
docker-compose exec web python manage.py createsuperuser

# Installer les données initiales
docker-compose exec web python manage.py populate_resources
```

### 3. Installation Manuelle

#### Créer l'environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

#### Installer les dépendances
```bash
pip install -r requirements.txt
```

#### Configurer les variables d'environnement
```bash
cp env.example .env
# Éditer .env avec vos configurations
```

#### Configurer la base de données
```bash
# Créer la base de données PostgreSQL
createdb hivmeet_db

# Exécuter les migrations
python manage.py migrate

# Créer un superutilisateur
python manage.py createsuperuser
```

#### Démarrer les services
```bash
# Serveur Django
python manage.py runserver

# Dans un autre terminal - Worker Celery
celery -A hivmeet_backend worker -l info

# Dans un autre terminal - Celery Beat
celery -A hivmeet_backend beat -l info
```

## ⚙️ Configuration

### Variables d'Environnement

Créez un fichier `.env` basé sur `env.example`:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de données
DATABASE_URL=postgresql://user:password@localhost:5432/hivmeet_db

# Firebase
FIREBASE_CREDENTIALS_PATH=credentials/firebase_credentials.json
FIREBASE_STORAGE_BUCKET=your-bucket.firebasestorage.app

# MyCoolPay
MYCOOLPAY_API_KEY=your_api_key
MYCOOLPAY_API_SECRET=your_secret
MYCOOLPAY_BASE_URL=https://api.mycoolpay.com/v1
MYCOOLPAY_WEBHOOK_SECRET=your_webhook_secret

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Configuration Firebase

1. Téléchargez le fichier `google-services.json` depuis votre console Firebase
2. Placez-le dans `credentials/firebase_credentials.json`
3. Configurez les règles de sécurité Firestore et Storage

### Configuration MyCoolPay

1. Créez un compte sur MyCoolPay
2. Récupérez vos clés API
3. Configurez les webhooks dans votre tableau de bord MyCoolPay

## 🧪 Tests

### Tests Automatiques
```bash
# Tous les tests
python manage.py test

# Tests spécifiques
python manage.py test authentication
python manage.py test matching
python manage.py test messaging
```

### Tests de Validation Complète
```bash
# Script de validation complète
python run_complete_tests.py

# Validation de la configuration
python validate_configuration.py

# Test Firebase
python test_firebase_complete.py
```

## 📊 Monitoring & Santé

### Endpoints de Santé
- `GET /health/` - État de santé complet
- `GET /health/simple/` - Vérification basique
- `GET /health/ready/` - Prêt pour le trafic
- `GET /metrics/` - Métriques de l'application

### Logs
```bash
# Logs Django
tail -f /var/log/hivmeet/django.log

# Logs Celery
tail -f /var/log/celery/worker1.log
```

## 📚 Documentation API

Une fois l'application démarrée, accédez à:
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## 🚀 Déploiement

### Déploiement avec Docker
```bash
# Production
docker-compose -f docker-compose.prod.yml up -d
```

### Déploiement Manuel
```bash
# Utiliser le script de déploiement
chmod +x deploy/deploy.sh
./deploy/deploy.sh production
```

### Variables de Production
- Configurez `DEBUG=False`
- Utilisez une base de données PostgreSQL dédiée
- Configurez Redis pour la production
- Activez HTTPS/SSL
- Configurez les backups automatiques

## 🔐 Sécurité

- ✅ Authentification JWT avec Firebase
- ✅ Middleware de validation premium
- ✅ Protection CSRF
- ✅ Headers de sécurité HTTP
- ✅ Validation des entrées utilisateur
- ✅ Chiffrement des données sensibles
- ✅ Rate limiting sur les API

## 📈 Performance

- ✅ Cache Redis pour les sessions et données fréquentes
- ✅ Pagination automatique des listes
- ✅ Optimisation des requêtes ORM
- ✅ Tâches asynchrones avec Celery
- ✅ Compression des réponses HTTP

## 🌍 Support International

- **Langues supportées**: Français, Anglais
- **Localisation**: Django i18n
- **Fuseaux horaires**: Support complet UTC

## 🤝 Contribution

1. Fork le projet
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commitez vos changements (`git commit -m 'Ajout nouvelle fonctionnalité'`)
4. Pushez vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Ouvrez une Pull Request

## 📝 Licence

Ce projet est sous licence propriétaire. Tous droits réservés.

## 📞 Support

- **Email**: support@hivmeet.com
- **Documentation**: [docs.hivmeet.com](https://docs.hivmeet.com)
- **Status**: [status.hivmeet.com](https://status.hivmeet.com)

## 🏗️ Architecture

```
hivmeet_backend/
├── authentication/     # Gestion des utilisateurs
├── profiles/          # Profils utilisateurs
├── matching/          # Algorithme de matching
├── messaging/         # Messagerie et appels
├── subscriptions/     # Système premium
├── resources/         # Ressources éducatives
├── hivmeet_backend/   # Configuration Django
├── deploy/           # Scripts de déploiement
├── tests/            # Tests d'intégration
└── docs/             # Documentation
```

## 🎯 Roadmap

- [ ] Notifications push natives
- [ ] Géolocalisation avancée
- [ ] IA pour améliorer le matching
- [ ] Application mobile Flutter
- [ ] Intégration vidéo en direct
- [ ] Support de plus de langues

---

**Développé avec ❤️ pour la communauté VIH+** 