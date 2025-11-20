"""
Configuration Firebase Admin SDK pour HIVMeet backend.
Selon les instructions détaillées du document INSTRUCTIONS_BACKEND_DJANGO_FIREBASE.md
"""
import firebase_admin
from firebase_admin import credentials
import os
from django.conf import settings
import logging

logger = logging.getLogger('hivmeet.firebase')

def initialize_firebase():
    """
    Initialiser Firebase Admin SDK selon les instructions détaillées.
    """
    # Vérifier si Firebase Admin SDK n'est pas déjà initialisé
    if firebase_admin._apps:
        logger.info("🔥 Firebase Admin SDK déjà initialisé")
        return
    
    try:
        # Option A (Production) : Utiliser un fichier service account JSON
        if hasattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY'):
            service_account_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY
            if os.path.exists(service_account_path):
                logger.info("🔥 Initialisation Firebase avec fichier service account")
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK initialisé avec fichier de credentials")
                return
        
        # Option B (Développement) : Utiliser les variables d'environnement
        logger.info("🔥 Tentative d'initialisation Firebase avec variables d'environnement")
        
        # Construire un dictionnaire de configuration avec les clés
        config_dict = {
            "type": "service_account",
            "project_id": os.getenv('FIREBASE_PROJECT_ID', 'hivmeet-f76f8'),
            "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
            "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.getenv('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
        }
        
        # Vérifier que les variables critiques sont présentes
        critical_vars = ['private_key_id', 'private_key', 'client_email', 'client_id']
        missing_vars = [var for var in critical_vars if not config_dict.get(var)]
        
        if missing_vars:
            logger.warning(f"⚠️ Variables Firebase manquantes: {missing_vars}")
            logger.info("🔄 Utilisation du service Firebase existant à la place")
            return
        
        # Créer les credentials avec le dictionnaire de configuration
        cred = credentials.Certificate(config_dict)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase Admin SDK initialisé avec variables d'environnement")
        
    except Exception as e:
        logger.error(f"❌ Erreur d'initialisation Firebase: {str(e)}")
        logger.info("🔄 Le service Firebase existant sera utilisé")

# Exécuter la fonction d'initialisation au niveau module
initialize_firebase() 