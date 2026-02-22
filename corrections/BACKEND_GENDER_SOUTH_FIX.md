# Backend – Correction `gender_sought` pour Discovery

## Problème
- Le filtre de compatibilité mutuelle dans l’API Discovery exclut tous les profils masculins car le champ `gender_sought` est `NULL` ou vide.
- Logs backend actuels : `After user's gender filter (seeking ['male']): 0 profiles` alors que des profils hommes existent.

## Cause racine
- Les profils créés (existants et nouveaux) ne définissent pas `gender_sought`.
- Le filtre backend impose `gender_sought='female'` (ou `all`) pour être compatible avec une utilisatrice cherchant des hommes.

## Plan de résolution (production-safe)

### 1) Migration de données immédiate (idempotente)
Créer une commande Django ou exécuter un script pour corriger les données existantes.

Pseudo-commande Django (à implémenter dans `profiles/management/commands/fix_gender_sought.py`):
```python
from django.core.management.base import BaseCommand
from django.db.models import Q
from profiles.models import Profile

class Command(BaseCommand):
    help = "Fix missing gender_sought values"

    def handle(self, *args, **options):
        males = Profile.objects.filter(Q(gender='male') & (Q(gender_sought__isnull=True) | Q(gender_sought='')))
        females = Profile.objects.filter(Q(gender='female') & (Q(gender_sought__isnull=True) | Q(gender_sought='')))
        others = Profile.objects.filter(Q(gender__in=['non_binary', 'other']) & (Q(gender_sought__isnull=True) | Q(gender_sought='')))

        m = males.update(gender_sought='female')
        f = females.update(gender_sought='male')
        o = others.update(gender_sought='all')

        self.stdout.write(self.style.SUCCESS(
            f"Fixed gender_sought -> males:{m}, females:{f}, others:{o}"
        ))
```

Exécution :
```bash
python manage.py fix_gender_sought
```

### 2) Validation modèle (prévention future)
Dans `profiles/models.py`, définir un défaut et interdire NULL/blank :
```python
gender_sought = models.CharField(
    max_length=20,
    choices=[('male','Male'), ('female','Female'), ('all','All')],
    default='female',    # empêche les NULL
    null=False,
    blank=False,
    help_text="Gender sought for mutual compatibility"
)
```
Puis migrations :
```bash
python manage.py makemigrations profiles
python manage.py migrate
```

### 3) Tests
Ajouter un test pour garantir qu’aucun profil n’a `gender_sought` manquant :
```python
from django.test import TestCase
from profiles.models import Profile

class ProfileGenderSoughtTest(TestCase):
    def test_all_profiles_have_gender_sought(self):
        missing = Profile.objects.filter(Q(gender_sought__isnull=True) | Q(gender_sought='')).count()
        self.assertEqual(missing, 0, "All profiles must define gender_sought")
```

### 4) Vérifications post-correction
SQL rapide :
```sql
SELECT COUNT(*) FROM profiles_profile WHERE gender_sought IS NULL OR gender_sought='';
-- Attendu: 0

SELECT gender, gender_sought, COUNT(*)
FROM profiles_profile
GROUP BY gender, gender_sought;
-- Attendu: male|female > 0 si des hommes existent
```

API Discovery (après correction) :
- Log attendu : `After user's gender filter (seeking ['male']): N>0 profiles`
- L’application Flutter ne montrera plus "Plus de profils" en boucle.

### 5) Scripts existants déjà alignés (côté repo)
- `create_male_profiles.py` a été mis à jour pour définir `gender_sought='female'` lors de la création de nouveaux profils de test.
- Un script autonome `fix_gender_sought.py` (dans ce repo) montre la logique de correction si besoin d’exemple.

## À faire par l’agent backend
1) Implémenter la commande Django `fix_gender_sought` (ou exécuter un script équivalent) en production/staging.
2) Ajouter le `default` et `null=False/blank=False` dans `profiles/models.py`, puis migrations.
3) Ajouter le test de non-régression.
4) Déployer, exécuter la commande de fix, et vérifier Discovery retourne >0 profils pour une utilisatrice cherchant des hommes.

## Notes
- L’opération est idempotente : on peut relancer la commande sans effet de bord.
- Aucun delete, seulement des UPDATE.
- Risque faible, bénéfice immédiat : rétablit l’alimentation de la Discovery.
