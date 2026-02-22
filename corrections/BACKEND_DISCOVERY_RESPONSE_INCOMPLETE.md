# 🔴 PROBLÈME BACKEND - Réponse Discovery API Incomplète

**Statut**: 🚨 BLOQUANT  
**Date**: 2026-01-19  
**Affecte**: Frontend Discovery Page (Écran de Découverte)  
**Sévérité**: HAUTE

---

## 📋 Description du Problème

La page de découverte du frontend s'affiche maintenant correctement, **MAIS** les données reçues du backend sont **incomplètes** ou **mal formatées**, ce qui empêche l'affichage des profils :

### ✅ Ce qui fonctionne :
- L'authentification ✅
- La récupération des profils ✅ (HTTP 200)
- La pagination ✅

### ❌ Ce qui ne fonctionne pas :
1. **`display_name` vide** : Les profils reçus ont `display_name: ""` au lieu d'un vrai nom
2. **`photos` vide** : Les profils reçus ont `photos: []` au lieu d'URL d'images
3. **Format incohérent** : Le backend utilise `user_id` comme clé au lieu de `id`

---

## 🔍 Analyse Détaillée

### Réponse Backend Actuelle (problématique) :
```json
{
  "count": 5,
  "results": [
    {
      "user_id": "e79040cc-b90a-4d25-a84c-4ca323cefb03",
      "display_name": "",  // ❌ VIDE
      "age": 44,
      "bio": "Médecin. Humain et attentionné...",
      "city": "Paris",
      "country": "FR",
      "photos": [],  // ❌ VIDE - Pas d'images
      "interests": [],
      "relationship_types_sought": ["long_term", "friendship", "casual"],
      "is_verified": false,
      "is_online": false,
      "distance_km": null
    }
  ]
}
```

### Réponse Attendue par le Frontend :
```json
{
  "count": 5,
  "results": [
    {
      "user_id": "e79040cc-b90a-4d25-a84c-4ca323cefb03",
      "display_name": "Clément F.",  // ✅ Prénom + première lettre nom
      "age": 44,
      "bio": "Médecin. Humain et attentionné...",
      "city": "Paris",
      "country": "FR",
      "photos": [
        "https://storage.googleapis.com/hivmeet-prod.appspot.com/photos/user_123/photo_1.jpg"
      ],  // ✅ Au minimum 1 photo
      "interests": ["Médecine", "Photographie"],
      "relationship_types_sought": ["long_term", "friendship", "casual"],
      "is_verified": false,
      "is_online": false,
      "distance_km": 12.5
    }
  ]
}
```

---

## 🎯 Problèmes Spécifiques à Corriger

### 1. **`display_name` Vide**
**Cause Probable** : 
- Le modèle Profile n'a pas de champ `display_name` direct
- Les champs `first_name` et `last_name` de l'utilisateur ne sont pas sérialisés dans la réponse

**Solution** :
```python
# Dans le serializer de Discovery (views_discovery.py ou services.py)

def get_display_name(profile):
    """Construire le display_name à partir des données disponibles"""
    user = profile.user
    
    # Priorité 1 : Utiliser first_name + première lettre du last_name
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name[0]}."
    
    # Priorité 2 : Juste first_name
    if user.first_name:
        return user.first_name
    
    # Fallback : Utiliser l'email (avant @)
    return user.email.split('@')[0]
```

### 2. **`photos` Vide (Pas d'Images)**
**Cause Probable** :
- Les profils test créés (`create_male_profiles.py`) n'ont pas de photos associées
- Le serializer ne retourne pas les photos du storage Firebase

**Solution** :
```python
# Option A : Ajouter une photo par défaut (avatar placeholder)
def get_photo_urls(profile):
    """Récupérer les URLs des photos du profil"""
    photos = profile.photos.all()
    
    if not photos:
        # Retourner un avatar par défaut basé sur le genre
        if profile.gender == 'male':
            return ["https://storage.googleapis.com/hivmeet-prod.appspot.com/defaults/avatar_male.png"]
        else:
            return ["https://storage.googleapis.com/hivmeet-prod.appspot.com/defaults/avatar_female.png"]
    
    return [photo.url for photo in photos]

# Option B : Créer des photos test pour les profils test
# Voir section "Script de Correction" ci-dessous
```

### 3. **Champs Manquants ou Mal Nommés**

| Champ Frontend | Champ Backend | Statut | Solution |
|---|---|---|---|
| `id` | `user_id` | ✅ Mappé côté frontend | Aucune action |
| `display_name` | ❌ Vide | ❌ BLOQUANT | Construire depuis `first_name`/`last_name` |
| `photos` | ❌ Toujours `[]` | ❌ BLOQUANT | Récupérer depuis `Profile.photos` ou avatar par défaut |
| `distance_km` | `distance_km` | ⚠️ Souvent `null` | Calculer distance réelle ou laisser `null` |

---

## 🔧 Solutions Proposées

### Solution 1 : Corriger le Serializer Discovery (PRIORITÉ 1)

**Fichier** : `env/hivmeet_backend/matching/serializers.py` ou `views_discovery.py`

```python
from profiles.models import Photo

class DiscoveryProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.id')
    display_name = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'user_id', 'display_name', 'age', 'bio', 'city', 'country',
            'photos', 'interests', 'relationship_types_sought',
            'is_verified', 'is_online', 'distance_km'
        ]
    
    def get_display_name(self, obj):
        """Construire un nom d'affichage lisible"""
        user = obj.user
        if user.first_name:
            return user.first_name
        return user.email.split('@')[0]
    
    def get_photos(self, obj):
        """Retourner les URLs des photos ou un avatar par défaut"""
        photos = obj.photos.all()
        if not photos:
            # Avatar par défaut basé sur le genre
            if obj.gender == 'male':
                return ["https://storage.googleapis.com/hivmeet-prod.appspot.com/defaults/male_avatar.png"]
            else:
                return ["https://storage.googleapis.com/hivmeet-prod.appspot.com/defaults/female_avatar.png"]
        
        return [photo.url for photo in photos]
```

### Solution 2 : Ajouter des Photos aux Profils Test (PRIORITÉ 2)

**Script pour créer des photos test** :

```python
# env/hivmeet_backend/add_photos_to_test_profiles.py

import os
import sys
import django
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile, Photo

User = get_user_model()

def create_placeholder_image(name, gender='male'):
    """Créer une image de placeholder en mémoire"""
    img = Image.new('RGB', (400, 500))
    # Fond coloré basé sur le genre
    color = (52, 73, 94) if gender == 'male' else (200, 120, 150)  # Gris/Rose
    img.paste(color)
    
    # Sauvegarder en BytesIO
    img_io = BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    return img_io

def add_photos_to_test_profiles():
    """Ajouter une photo à chaque profil test"""
    test_emails = [
        'thomas.martin@test.com',
        'julien.rousseau@test.com',
        'alexandre.blanc@test.com',
        'nicolas.petit@test.com',
        'pierre.garcia@test.com',
        'antoine.martinez@test.com',
        'maxime.lopez@test.com',
        'clement.fernandez@test.com',
    ]
    
    for email in test_emails:
        try:
            user = User.objects.get(email=email)
            profile = Profile.objects.get(user=user)
            
            # Créer une photo si elle n'existe pas
            if not profile.photos.exists():
                img = create_placeholder_image(f"photo_{email}.png", gender=profile.gender)
                photo = Photo.objects.create(
                    profile=profile,
                    image=ContentFile(img.read(), name=f"photo_{email}.png"),
                    is_primary=True,
                    order=0,
                )
                print(f"✅ Photo créée pour {email}")
            else:
                print(f"⏭️  {email} a déjà des photos")
        except (User.DoesNotExist, Profile.DoesNotExist):
            print(f"❌ Profile non trouvé pour {email}")

if __name__ == '__main__':
    add_photos_to_test_profiles()
```

**Ou plus simple, utiliser des URLs externes** :
```python
def get_photos(self, obj):
    """Retourner les URLs des photos ou des avatars Gravatar"""
    photos = obj.photos.all()
    if not photos:
        # Utiliser Gravatar avec le hash de l'email
        import hashlib
        email_hash = hashlib.md5(obj.user.email.encode()).hexdigest()
        avatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=identicon&s=400"
        return [avatar_url]
    
    return [photo.url for photo in photos]
```

---

## 📋 Checklist de Correction

- [ ] Mettre à jour le serializer Discovery pour remplir `display_name`
- [ ] Mettre à jour le serializer Discovery pour retourner `photos` (URL réelles ou placeholders)
- [ ] Tester la réponse API : `GET /api/v1/discovery/profiles?page=1`
- [ ] Vérifier que `display_name` n'est jamais vide
- [ ] Vérifier que chaque profil a au moins 1 URL de photo
- [ ] Valider les logs backend pour confirmer la génération des données

---

## 🧪 Tests de Validation

### Test 1 : Vérifier la Réponse API
```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/api/v1/discovery/profiles?page=1

# Vérifier:
# ✅ "display_name" non vide
# ✅ "photos" contient au moins 1 URL
# ✅ Tous les champs présents
```

### Test 2 : Vérifier dans l'App Flutter
- Lancer l'app
- Aller à la page Discovery
- Voir les noms des profils affichés
- Voir les images de profil affichées

---

## 📞 Notes Additionnelles

**Utilisateur Testé** : Marie (marie.claire@test.com)  
**Profils Retournés** : 6 profils masculins (35-45 ans)  
**Date du Problème** : 2026-01-19 01:50:42  
**Logs Backend Disponibles** : Voir les logs dans la console Django

---

## 🎯 Priorité

**HAUTE** - Le frontend affiche maintenant la page, mais sans données ce n'est pas utilisable.

Merci de corriger ces points rapidement ! 🙏
