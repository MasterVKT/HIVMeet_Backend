# Réconciliation des interactions de découverte

## Contrat applicatif

Une interaction active est unique pour le couple `utilisateur → profil cible`,
quel que soit son type (`like`, `super_like` ou `dislike`). Une répétition de la
même action active conserve son identifiant et son horodatage. Une action après
révocation crée une nouvelle ligne et un nouvel identifiant.

Un rewind révoque uniquement son identifiant initial. Une répétition de ce rewind
reste idempotente, sans consommer un quota supplémentaire. Une nouvelle action
peut être rewindée selon sa propre fenêtre de cinq minutes et le quota Premium
de cinq rewinds par jour. Un like ayant créé un match actif reste protégé.

Les endpoints existants restent inchangés. Les réponses de like, pass et Super
Like exposent l’`interaction_id` à utiliser avec :

```
POST /api/v1/discovery/interactions/{interaction_id}/rewind/
```

Les historiques `my-likes` et `my-passes` excluent les interactions révoquées
par défaut. Un Super Like conserve `interaction_type: "super_like"`.

## Mise à disposition contrôlée

Cette opération ne doit pas être exécutée sur une base de production sans
sauvegarde, rapport de prévisualisation validé et autorisation de l’opérateur.
Les rapports contiennent des UUID d’interactions et doivent rester dans un
emplacement privé, hors dépôt et hors journaux applicatifs.

1. Sauvegarder la base et déployer le code.
2. Appliquer uniquement l’ajout de champ :

   ```powershell
   python manage.py migrate matching 0005_interaction_rewound_at
   ```

3. Générer puis examiner un rapport privé :

   ```powershell
   python manage.py reconcile_interaction_history --dry-run --report <chemin-prive>/preview.json
   ```

4. Appliquer la réconciliation avec un second rapport privé :

   ```powershell
   python manage.py reconcile_interaction_history --apply --report <chemin-prive>/applied.json
   ```

5. Vérifier le résumé du rapport, puis appliquer la contrainte :

   ```powershell
   python manage.py migrate matching 0006_enforce_one_active_interaction_per_pair
   ```

La commande révoque une interaction encore active mais marquée `rewound_at`.
Pour plusieurs interactions actives sur la même paire, elle préserve un like ou
Super Like lié à un match actif ; sinon elle conserve l’action la plus récente.
Elle ne supprime ni match ni historique, et ne modifie aucun compteur de swipe.

## Restauration

Le rapport `applied.json` contient l’état avant et après de chaque ligne touchée.
La restauration vérifie que les lignes n’ont pas changé depuis l’application.
Si elle doit recréer deux interactions actives pour une même paire, revenir
d’abord à la migration `0005_interaction_rewound_at`, restaurer, puis décider si
la contrainte `0006` doit être réappliquée après une nouvelle réconciliation.

```powershell
python manage.py migrate matching 0005_interaction_rewound_at
python manage.py reconcile_interaction_history --restore <chemin-prive>/applied.json
```
