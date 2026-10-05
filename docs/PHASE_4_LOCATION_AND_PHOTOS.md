# Phase 4 — Profil, localisation et photos

> Registration, gender migration, and GeoNames manifest details: `PHASE_4_ACCOUNT_PROFILE_CATALOG.md`.

## Migration et déploiement

1. Déployer le backend qui contient `profiles.0008_phase4_registration_gender_catalog`.
2. Exécuter `python manage.py migrate`.
   La migration crée les tables `geo_countries` et `geo_cities`, initialise le
   catalogue ISO/GeoNames des pays depuis `profiles/data/countryInfo.txt` et
   conserve intégralement `profiles.city` et `profiles.country` pour la
   compatibilité des clients antérieurs.
3. Fournir une copie vérifiée de `cities500.zip` issue de GeoNames et lancer :

   ```bash
   python manage.py sync_geonames_catalog --source /releases/geonames/cities500.zip --sha256 <published-sha256>
   python manage.py verify_geonames_catalog
   ```

   La commande est idempotente et reprise par lots de 2 000 lignes. Elle ne
   télécharge aucune donnée pendant une migration. Les données GeoNames doivent
   conserver l’attribution : https://www.geonames.org/about.html.
4. Déployer l’application Flutter compatible. Les clients plus anciens restent
   fonctionnels grâce aux champs de ville/pays historiques ; ils ne reçoivent
   pas les coordonnées d’un autre profil.

## Contrats ajoutés

- `GET /api/v1/user-profiles/geo/countries/?q=&page=` : pays paginés, avec
  libellé localisé et version du catalogue.
- `GET /api/v1/user-profiles/geo/cities/?country=CM&q=&page=` : villes
  dépendantes du pays, paginées et recherchables.
- `PUT /api/v1/user-profiles/me/location/` :
  - `location_enabled=true`, `latitude`, `longitude`, `accuracy_m` pour une
    mesure de premier plan ;
  - `location_enabled=false`, `city_id` pour la sélection manuelle ;
  - `location_enabled=false` sans ville pour supprimer des coordonnées
    précises déjà enregistrées.
- `PUT /api/v1/user-profiles/me/photos/reorder/` avec la liste complète et
  ordonnée `photo_ids`. Le serveur vérifie un abonnement Premium actif et
  traite l’opération sous transaction.

Les DTO publics retournent seulement `distance_from_me_km`,
`distance_estimated` et `same_city`. Les coordonnées ne font partie d’aucun
DTO public. Une mesure de moins de 24 heures est utilisée pour la distance
précise ; sinon le serveur calcule une estimation entre centres de villes. Deux
sélections manuelles de la même ville retournent `same_city=true` sans `0 km`.

## Retour arrière

Le retour arrière applicatif conserve les colonnes historiques `city` et
`country`. Avant de revenir avant la migration, exporter les valeurs de
`geo_city_id`, `location_enabled`, `location_mode`, `location_accuracy_m` et
`location_updated_at` si elles doivent être conservées. La suppression des
nouvelles tables doit intervenir seulement après cette exportation. Les objets
média de profil sont supprimés du stockage uniquement après la validation de
la transaction de suppression.

## Confidentialité et permissions

La demande de permission n’est jamais faite au chargement d’un écran. Elle est
faite après l’action explicite sur le switch ou le bouton de localisation et
utilise une seule lecture de premier plan. Un refus, un refus permanent ou un
service désactivé laisse la sélection manuelle disponible. Android déclare les
permissions de position fine/approximative, caméra et images ; iOS décrit les
usages dans `Info.plist`.
