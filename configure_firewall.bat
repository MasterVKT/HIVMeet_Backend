@echo off
echo 🔧 Configuration du pare-feu Windows pour HIVMeet Django Server
echo.
echo ⚠️  Ce script doit être exécuté EN TANT QU'ADMINISTRATEUR
echo    Clic droit sur ce fichier -> "Exécuter en tant qu'administrateur"
echo.
pause

echo 🔍 Vérification des privilèges administrateur...
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ Privilèges administrateur confirmés
) else (
    echo ❌ ERREUR: Privilèges administrateur requis
    echo.
    echo 💡 SOLUTION:
    echo    1. Clic droit sur ce fichier
    echo    2. Sélectionner "Exécuter en tant qu'administrateur"
    echo    3. Confirmer dans la boîte de dialogue UAC
    echo.
    pause
    exit /b 1
)

echo.
echo 🔥 Création de la règle pare-feu pour Django (port 8000)...
netsh advfirewall firewall add rule name="Python Django HIVMeet" dir=in action=allow protocol=TCP localport=8000

if %errorLevel% == 0 (
    echo ✅ Règle pare-feu créée avec succès !
) else (
    echo ❌ Erreur lors de la création de la règle pare-feu
    goto error
)

echo.
echo 🔍 Vérification de la règle créée...
netsh advfirewall firewall show rule name="Python Django HIVMeet"

if %errorLevel% == 0 (
    echo ✅ Règle pare-feu active et fonctionnelle !
) else (
    echo ⚠️ Impossible de vérifier la règle
)

echo.
echo 🎉 CONFIGURATION TERMINÉE !
echo.
echo 📋 PROCHAINES ÉTAPES:
echo    1. Démarrer le serveur Django:
echo       python manage.py runserver 0.0.0.0:8000
echo.
echo    2. Tester la connectivité:
echo       python test_flutter_simulation.py
echo.
echo    3. Dans Flutter, utiliser l'URL:
echo       http://10.0.2.2:8000
echo.
goto end

:error
echo.
echo 🚨 ERREUR DE CONFIGURATION
echo.
echo 💡 SOLUTIONS ALTERNATIVES:
echo.
echo 1. SOLUTION TEMPORAIRE (développement uniquement):
echo    Désactiver temporairement le pare-feu:
echo    netsh advfirewall set allprofiles state off
echo.
echo    ⚠️ NE PAS OUBLIER de le réactiver après:
echo    netsh advfirewall set allprofiles state on
echo.
echo 2. CONFIGURATION MANUELLE:
echo    - Ouvrir "Pare-feu Windows Defender avec sécurité avancée"
echo    - Règles de trafic entrant → Nouvelle règle
echo    - Type: Port → TCP → Port 8000
echo    - Action: Autoriser la connexion
echo    - Nom: "Python Django HIVMeet"
echo.

:end
echo.
pause 