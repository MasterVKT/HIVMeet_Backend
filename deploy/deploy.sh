#!/bin/bash
# Script de déploiement HIVMeet Backend
# Usage: ./deploy.sh [staging|production]

set -e  # Exit on any error

ENVIRONMENT=${1:-staging}
APP_NAME="hivmeet_backend"
DOMAIN="api.hivmeet.com"
REPO_URL="https://github.com/your-org/hivmeet-backend.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 DÉPLOIEMENT HIVMEET BACKEND - ${ENVIRONMENT^^}${NC}"
echo "================================================="

# Check environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}❌ Environnement invalide. Utilisez 'staging' ou 'production'${NC}"
    exit 1
fi

# Set environment-specific variables
if [[ "$ENVIRONMENT" == "production" ]]; then
    APP_DIR="/var/www/hivmeet_backend"
    VENV_DIR="/var/www/hivmeet_backend/venv"
    SETTINGS_MODULE="hivmeet_backend.production_settings"
    NGINX_CONF="/etc/nginx/sites-available/hivmeet_backend"
    SSL_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
else
    APP_DIR="/var/www/hivmeet_backend_staging"
    VENV_DIR="/var/www/hivmeet_backend_staging/venv"
    SETTINGS_MODULE="hivmeet_backend.settings"
    NGINX_CONF="/etc/nginx/sites-available/hivmeet_backend_staging"
    DOMAIN="staging-api.hivmeet.com"
fi

echo -e "${YELLOW}📂 Répertoire: ${APP_DIR}${NC}"
echo -e "${YELLOW}🔧 Settings: ${SETTINGS_MODULE}${NC}"

# Function to run commands with error handling
run_cmd() {
    echo -e "${BLUE}🔧 $1${NC}"
    if eval "$2"; then
        echo -e "${GREEN}✅ $1 - SUCCÈS${NC}"
    else
        echo -e "${RED}❌ $1 - ÉCHEC${NC}"
        exit 1
    fi
}

# Stop services
echo -e "\n${YELLOW}🛑 ARRÊT DES SERVICES${NC}"
run_cmd "Arrêt Gunicorn" "sudo systemctl stop gunicorn-${APP_NAME} || true"
run_cmd "Arrêt Celery" "sudo systemctl stop celery-${APP_NAME} || true"
run_cmd "Arrêt Celery Beat" "sudo systemctl stop celerybeat-${APP_NAME} || true"

# Backup current version
if [[ -d "$APP_DIR" ]]; then
    echo -e "\n${YELLOW}💾 SAUVEGARDE VERSION ACTUELLE${NC}"
    BACKUP_DIR="/var/backups/hivmeet_backend/$(date +%Y%m%d_%H%M%S)"
    run_cmd "Création répertoire sauvegarde" "sudo mkdir -p $BACKUP_DIR"
    run_cmd "Sauvegarde application" "sudo cp -r $APP_DIR $BACKUP_DIR/"
    echo -e "${GREEN}✅ Sauvegarde créée: $BACKUP_DIR${NC}"
fi

# Update code
echo -e "\n${YELLOW}📥 MISE À JOUR DU CODE${NC}"
if [[ -d "$APP_DIR" ]]; then
    run_cmd "Mise à jour dépôt Git" "cd $APP_DIR && sudo git pull origin main"
else
    run_cmd "Clonage dépôt" "sudo git clone $REPO_URL $APP_DIR"
fi

# Set permissions
run_cmd "Configuration permissions" "sudo chown -R www-data:www-data $APP_DIR"

# Virtual environment setup
echo -e "\n${YELLOW}🐍 CONFIGURATION ENVIRONNEMENT PYTHON${NC}"
if [[ ! -d "$VENV_DIR" ]]; then
    run_cmd "Création environnement virtuel" "sudo python3 -m venv $VENV_DIR"
fi

run_cmd "Activation environnement virtuel" "cd $APP_DIR && sudo $VENV_DIR/bin/pip install --upgrade pip"
run_cmd "Installation dépendances" "cd $APP_DIR && sudo $VENV_DIR/bin/pip install -r requirements.txt"

# Environment variables
echo -e "\n${YELLOW}⚙️ CONFIGURATION VARIABLES D'ENVIRONNEMENT${NC}"
ENV_FILE="$APP_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${YELLOW}📝 Création fichier .env${NC}"
    sudo tee "$ENV_FILE" > /dev/null <<EOF
# HIVMeet Backend Environment - $ENVIRONMENT
DEBUG=False
ALLOWED_HOSTS=$DOMAIN
DATABASE_URL=postgresql://hivmeet_user:your_password@localhost:5432/hivmeet_${ENVIRONMENT}
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=$(openssl rand -base64 32)
ENVIRONMENT=$ENVIRONMENT

# Firebase
FIREBASE_CREDENTIALS_PATH=/etc/hivmeet/firebase_credentials.json
FIREBASE_STORAGE_BUCKET=hivmeet-f76f8.firebasestorage.app

# MyCoolPay (à configurer)
MYCOOLPAY_API_KEY=your_api_key
MYCOOLPAY_API_SECRET=your_secret
MYCOOLPAY_BASE_URL=https://api.mycoolpay.com/v1
MYCOOLPAY_WEBHOOK_SECRET=your_webhook_secret

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=your_sendgrid_user
EMAIL_HOST_PASSWORD=your_sendgrid_password

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Static files
STATIC_ROOT=/var/www/hivmeet/static
MEDIA_ROOT=/var/www/hivmeet/media
EOF
    sudo chown www-data:www-data "$ENV_FILE"
    sudo chmod 600 "$ENV_FILE"
    echo -e "${GREEN}✅ Fichier .env créé${NC}"
else
    echo -e "${GREEN}✅ Fichier .env existant${NC}"
fi

# Database migration
echo -e "\n${YELLOW}🗃️ MIGRATION BASE DE DONNÉES${NC}"
run_cmd "Migration Django" "cd $APP_DIR && sudo -u www-data $VENV_DIR/bin/python manage.py migrate --settings=$SETTINGS_MODULE"

# Collect static files
echo -e "\n${YELLOW}📁 COLLECTION FICHIERS STATIQUES${NC}"
run_cmd "Collection static files" "cd $APP_DIR && sudo -u www-data $VENV_DIR/bin/python manage.py collectstatic --noinput --settings=$SETTINGS_MODULE"

# Create systemd services
echo -e "\n${YELLOW}⚙️ CONFIGURATION SERVICES SYSTEMD${NC}"

# Gunicorn service
GUNICORN_SERVICE="/etc/systemd/system/gunicorn-${APP_NAME}.service"
sudo tee "$GUNICORN_SERVICE" > /dev/null <<EOF
[Unit]
Description=Gunicorn instance to serve HIVMeet Backend ($ENVIRONMENT)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn --workers 3 --bind unix:$APP_DIR/gunicorn.sock hivmeet_backend.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Celery service
CELERY_SERVICE="/etc/systemd/system/celery-${APP_NAME}.service"
sudo tee "$CELERY_SERVICE" > /dev/null <<EOF
[Unit]
Description=Celery worker for HIVMeet Backend ($ENVIRONMENT)
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
EnvironmentFile=$APP_DIR/.env
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/celery multi start worker1 --app=hivmeet_backend --pidfile=/var/run/celery/%n.pid --logfile=/var/log/celery/%n.log --loglevel=info
ExecStop=$VENV_DIR/bin/celery multi stopwait worker1 --pidfile=/var/run/celery/%n.pid
ExecReload=$VENV_DIR/bin/celery multi restart worker1 --app=hivmeet_backend --pidfile=/var/run/celery/%n.pid --logfile=/var/log/celery/%n.log --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat service
CELERYBEAT_SERVICE="/etc/systemd/system/celerybeat-${APP_NAME}.service"
sudo tee "$CELERYBEAT_SERVICE" > /dev/null <<EOF
[Unit]
Description=Celery beat scheduler for HIVMeet Backend ($ENVIRONMENT)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
EnvironmentFile=$APP_DIR/.env
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/celery beat --app=hivmeet_backend --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create directories for Celery
sudo mkdir -p /var/run/celery /var/log/celery
sudo chown www-data:www-data /var/run/celery /var/log/celery

# Nginx configuration
echo -e "\n${YELLOW}🌐 CONFIGURATION NGINX${NC}"
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
    
    # Static files
    location /static/ {
        alias /var/www/hivmeet/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /var/www/hivmeet/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
    
    # API requests
    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Health check
    location /health/ {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# Enable Nginx site
if [[ ! -L "/etc/nginx/sites-enabled/$(basename $NGINX_CONF)" ]]; then
    run_cmd "Activation site Nginx" "sudo ln -s $NGINX_CONF /etc/nginx/sites-enabled/"
fi

# Reload systemd and start services
echo -e "\n${YELLOW}🔄 DÉMARRAGE DES SERVICES${NC}"
run_cmd "Rechargement systemd" "sudo systemctl daemon-reload"
run_cmd "Activation Gunicorn" "sudo systemctl enable gunicorn-${APP_NAME}"
run_cmd "Activation Celery" "sudo systemctl enable celery-${APP_NAME}"
run_cmd "Activation Celery Beat" "sudo systemctl enable celerybeat-${APP_NAME}"
run_cmd "Démarrage Gunicorn" "sudo systemctl start gunicorn-${APP_NAME}"
run_cmd "Démarrage Celery" "sudo systemctl start celery-${APP_NAME}"
run_cmd "Démarrage Celery Beat" "sudo systemctl start celerybeat-${APP_NAME}"
run_cmd "Test configuration Nginx" "sudo nginx -t"
run_cmd "Rechargement Nginx" "sudo systemctl reload nginx"

# Final checks
echo -e "\n${YELLOW}🔍 VÉRIFICATIONS FINALES${NC}"
sleep 5
run_cmd "Status Gunicorn" "sudo systemctl is-active gunicorn-${APP_NAME}"
run_cmd "Status Celery" "sudo systemctl is-active celery-${APP_NAME}"
run_cmd "Status Celery Beat" "sudo systemctl is-active celerybeat-${APP_NAME}"

echo -e "\n${GREEN}🎉 DÉPLOIEMENT TERMINÉ AVEC SUCCÈS!${NC}"
echo -e "${GREEN}🌐 Application disponible sur: https://$DOMAIN${NC}"
echo -e "${GREEN}🔧 Admin: https://$DOMAIN/admin${NC}"

# Display useful commands
echo -e "\n${BLUE}📋 COMMANDES UTILES:${NC}"
echo "Status services:     sudo systemctl status gunicorn-${APP_NAME}"
echo "Logs application:    sudo journalctl -f -u gunicorn-${APP_NAME}"
echo "Logs Celery:         sudo journalctl -f -u celery-${APP_NAME}"
echo "Redémarrage:         sudo systemctl restart gunicorn-${APP_NAME}"
echo "Django shell:        cd $APP_DIR && sudo -u www-data $VENV_DIR/bin/python manage.py shell" 