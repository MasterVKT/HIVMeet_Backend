# Règles locales — backend HIVMeet

Les règles transversales sont dans `../../../.agents/PROJECT_RULES.md`. Ce service
est un backend Django REST Framework manipulant des données sensibles de santé.

- Ne jamais coder secret, clé, jeton ou identifiant de service; utiliser la
  configuration d'environnement existante.
- Toute entrée utilisateur traverse un serializer DRF et toute ressource protégée
  applique l'authentification Firebase et les permissions nécessaires.
- Préserver exactement les contrats de `docs/API_DOCUMENTATION.md`; coordonner le
  frontend avant une évolution de schéma, de DTO, de statut ou d'erreur.
- Une évolution de modèle implique migration, stratégie de données et rollback;
  employer des transactions pour les écritures multi-modèles critiques.
- Les logs sont utiles mais ne contiennent jamais jeton, mot de passe, statut VIH,
  e-mail complet ou autre donnée personnelle sensible. Les messages utilisateur
  restent internationalisables FR/EN.
- Utiliser le graphe de revue avant une exploration textuelle quand disponible et
  ne pas écraser les modifications non liées du dépôt.
