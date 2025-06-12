@echo off
REM Utilisation de ^ pour la continuation de ligne dans les fichiers batch Windows.
REM Les données JSON sont mises sur une seule ligne et les guillemets doubles dans le JSON sont échappés.
curl -X POST http://localhost:8000/api/v1/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"email\": \"test@example.com\", \"password\": \"Test@1234\", \"password_confirm\": \"Test@1234\", \"birth_date\": \"1990-01-01\", \"display_name\": \"Test User\"}"