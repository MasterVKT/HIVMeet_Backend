# Audit de complétude — KYC phase 4

## Périmètre

Cette phase raccorde le client mobile au contrat KYC v1 et aux signaux sûrs du
backend. Elle reste en développement, avec données synthétiques uniquement.

## Exigences → preuves

| Exigence de phase 4 | Preuve |
|---|---|
| Domaine KYC isolé et contrat v1 | `hivmeet/lib/domain/entities/kyc.dart`, `domain/repositories/kyc_repository.dart`, `data/datasources/remote/kyc_api.dart`, `data/repositories/kyc_repository_impl.dart` ; les cinq routes client correspondent à `KYC_V1_CONTRACT.openapi.yaml`. |
| États et parcours explicites | `KycCubit`, `KycState` et `VerificationPage` affichent démarrage, pièces, défi selfie, envoi, revue, vérification, refus et expiration sans intégrer les routes internes de revue. |
| Capture locale sans biométrie | `kyc_capture_port.dart`, `android/app/build.gradle`, `MainActivity.kt` et `ios/Runner/AppDelegate.swift` : ML Kit document scanner / Vision rectangle, décodage local, recadrage vers une copie ; aucun SDK de reconnaissance faciale ou prestataire KYC. |
| Transport direct sûr | `KycRepositoryImpl` vérifie HTTPS, expiration, en-têtes liés et absence d’`Authorization`, avec `followRedirects: false`; `ApiClient` ne transporte pas les octets de pièce. |
| Brouillons, cache, fond et captures | `KycCapturePort`, `KycMediaCacheCleaner`, `KycScreenPrivacy`, `main.dart` et `VerificationPage` effacent les copies sur les transitions pertinentes, purgent les caches et activent `FLAG_SECURE` Android. |
| Habilitations mobiles restrictives | `KycAccessController`, `AppRouter` et l’interception de `kyc_required` dans `ApiClient` refusent l’accès client aux parcours sociaux et Premium sans statut vérifié non expiré. Les permissions backend des phases 1–3 demeurent l’autorité. |
| Synchronisation et messages sûrs | `verification_update` est mappé dans les services FCM/WebSocket et déclenche un rafraîchissement KYC sans inclure de détail de décision, de pièce, de défi ou d’URL. |
| I18n et tests | Sections `kyc` FR/EN ; `test/kyc/kyc_access_and_flow_test.dart` couvre le refus sans expiration, la purge de cache et les trois documents vers `pending_review`. |

## Changements → exigences

| Changement | Exigence satisfaite |
|---|---|
| Module KYC Flutter, injection et écran de vérification | Séparation de l’ancien `ProfileBloc`, workflow client canonique et états sûrs. |
| Routeur, cycle de session, événements realtime et `ApiClient` | Défense client restrictive, retour de premier plan, invalidation par serveur et cache purgé. |
| Android ML Kit, iOS Vision et déclarations de permission | Capture guidée et contrôle local sans biométrie ni fournisseur externe. |
| Traductions, `pubspec` et verrouillage des dépendances | UX FR/EN et dépendances nécessaires (`crypto`, cache privé, ML Kit Android). |
| Ce document et `KYC_PHASE_4_IMPLEMENTATION.md` | Limites de simulation, recette mobile et gates externes explicites. |

## Impact

- Backend : aucun endpoint utilisateur ni migration supplémentaire n’est requis
  par cette phase. Le contrat existant reste inchangé. `verification_update`
  est maintenant consommé par le client.
- Frontend : ajout du module KYC, remplacement du parcours de vérification
  historique, garde de navigation et protection de capture. Les profils et
  réglages propres restent accessibles ; les données sociales restent fermées
  sans KYC actif.
- Exploitation : le stockage mémoire local ne permet pas un PUT mobile réel.
  Une recette E2E nécessite le gate Plateforme décrit dans
  `KYC_PHASE_4_IMPLEMENTATION.md`, avec objets synthétiques et TLS privé.

## Validation indépendante

- `flutter test --no-pub test/kyc/kyc_access_and_flow_test.dart` : 4 tests
  réussis.
- Les 64 tests ciblés des services realtime et de leurs consommateurs BLoC
  réussissent, ce qui couvre la compatibilité de l'événement
  `verification_update` avec les flux existants.
- `dart analyze` sur le module, le routeur, l’injection, le transport et les
  consommateurs realtime : aucune anomalie.
- `android/gradlew.bat :app:compileDebugKotlin --console=plain` : réussi avec
  le scanner ML Kit. La compilation iOS nécessite encore un hôte macOS/Xcode.
- `python manage.py test profiles.tests.test_kyc_phase1
  profiles.tests.test_kyc_phase2 profiles.tests.test_kyc_phase3
  profiles.tests.test_location_and_photos --settings=hivmeet_backend.test_settings`
  avec une base de test isolée : 66 tests réussis ; contrat, upload mémoire
  synthétique, permissions et revue humaine validés.

## Décision de non-activation

Cette phase ne modifie pas `KYC_SOCIAL_ACCESS_ENFORCEMENT`, ne définit aucun
paramètre de production, n’active aucun bucket, CMEK, fournisseur KYC ou revue
réelle. Les validations externes précédemment consignées restent bloquantes.
