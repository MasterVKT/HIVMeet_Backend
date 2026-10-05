"""
Script d'analyse complète des utilisateurs.
Vérifie :
1. Tous les utilisateurs Django + leurs profils
2. Le statut premium/freemium
3. La synchronisation Firebase
4. Les profils dans la découverte
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from profiles.models import Profile, ProfilePhoto
from subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()

print("=" * 80)
print("ANALYSE COMPLETE DE LA BASE DE DONNEES HIVMeet")
print("=" * 80)

# 1. Tous les utilisateurs
print("\n\n1. LISTE COMPLETE DES UTILISATEURS (Django)")
print("-" * 80)
users = User.objects.all().order_by('date_joined')
for u in users:
    premium = "OUI" if u.is_premium else "NON"
    fb_uid = u.firebase_uid or "NON DEFINI"
    print(f"ID: {str(u.id)[:8]}... | Email: {u.email[:30]:30} | Nom: {u.display_name[:20]:20} | Firebase: {fb_uid[:30]:30} | Premium: {premium} | Date: {str(u.date_joined)[:19]}")
print(f"\nTotal: {users.count()} utilisateurs")

# 2. Profils
print("\n\n2. PROFILS ASSOCIES")
print("-" * 80)
profiles = Profile.objects.select_related('user').all()
print(f"Nombre de profils: {profiles.count()}")
missing = []
for u in users:
    if not hasattr(u, 'profile'):
        missing.append(u)
if missing:
    print(f"*** Utilisateurs SANS profil: {len(missing)}")
    for u in missing:
        print(f"   - {u.display_name} ({u.email})")
else:
    print("OK: Tous les utilisateurs ont un profil")

for p in profiles:
    print(f"  {p.user.display_name[:20]:20} | Genre: {p.gender[:15]:15} | Age: {p.user.age or 'N/A':<5} | "
          f"Ville: {p.city or 'N/A':15} | Cache: {p.is_hidden} | Discovery: {p.allow_profile_in_discovery}")

# 3. Photos de profil
print("\n\n3. PHOTOS DE PROFIL")
print("-" * 80)
photos = ProfilePhoto.objects.select_related('profile__user').all()
print(f"Nombre total de photos: {photos.count()}")
profiles_with_photos = set(photos.values_list('profile_id', flat=True))
profiles_without_photos = profiles.exclude(id__in=profiles_with_photos)
if profiles_without_photos.exists():
    print(f"*** Profils SANS photo: {profiles_without_photos.count()}")
    for p in profiles_without_photos:
        print(f"   - {p.user.display_name} ({p.user.email})")
else:
    print("OK: Tous les profils ont au moins une photo")

# 4. Statut Premium
print("\n\n4. STATUT PREMIUM / FREEMIUM")
print("-" * 80)
premium_users = users.filter(is_premium=True)
freemium_users = users.filter(is_premium=False)
print(f"PREMIUM: {premium_users.count()} utilisateur(s)")
for u in premium_users:
    print(f"  * {u.display_name[:20]:20} | Premium jusqu'a: {u.premium_until or 'Non defini'}")

print(f"\nFREEMIUM: {freemium_users.count()} utilisateur(s)")
for u in freemium_users:
    print(f"  * {u.display_name[:20]:20} | Email: {u.email}")

# 5. Abonnements
print("\n\n5. ABONNEMENTS ACTIFS")
print("-" * 80)
try:
    subscriptions = Subscription.objects.select_related('user', 'plan').all()
    print(f"Nombre d'abonnements: {subscriptions.count()}")
    for s in subscriptions:
        print(f"  {s.user.display_name[:20]:20} | Plan: {s.plan.name if s.plan else 'N/A':20} | "
              f"Actif: {s.is_active} | Fin: {s.end_date or 'N/A'}")
except Exception as e:
    print(f"Erreur lecture abonnements: {e}")

# 6. Plans d'abonnement
print("\n\n6. PLANS D'ABONNEMENT")
print("-" * 80)
try:
    plans = SubscriptionPlan.objects.all()
    print(f"Nombre de plans: {plans.count()}")
    for p in plans:
        print(f"  {p.name:20} | Prix: {str(p.price):10} | Duree: {p.duration_days:5} jours | StripeID: {p.stripe_price_id or 'N/A'}")
except Exception as e:
    print(f"Erreur lecture plans: {e}")

# 7. Firebase UID
print("\n\n7. SYNC FIREBASE")
print("-" * 80)
with_firebase = users.exclude(firebase_uid__isnull=True).exclude(firebase_uid__exact='')
without_firebase = users.filter(firebase_uid__isnull=True) | users.filter(firebase_uid__exact='')
print(f"Avec Firebase UID: {with_firebase.count()}")
print(f"Sans Firebase UID: {without_firebase.count()}")
if without_firebase.exists():
    print("*** Utilisateurs NON synchronises avec Firebase:")
    for u in without_firebase:
        print(f"   - {u.display_name[:20]:20} | Email: {u.email:30} | ID: {u.id}")

# 8. Eligibilite decouverte
print("\n\n8. ELIGIBILITE DECOUVERTE")
print("-" * 80)
eligible = profiles.filter(
    is_hidden=False,
    allow_profile_in_discovery=True,
    user__is_active=True
).select_related('user')
print(f"Profils eligibles pour la decouverte: {eligible.count()}")
for p in eligible:
    print(f"  {p.user.display_name[:20]:20} | Genre: {p.gender[:15]:15} | Age: {p.user.age or 'N/A':5} | Premium: {'OUI' if p.user.is_premium else 'NON'}")

print("\n" + "=" * 80)
print("RESUME STATISTIQUES")
print("=" * 80)
print(f"Utilisateurs totaux:        {users.count()}")
print(f"Profils crees:              {profiles.count()}")
print(f"Avec Firebase UID:          {with_firebase.count()}")
print(f"Sans Firebase UID:          {without_firebase.count()}")
print(f"Premium:                    {premium_users.count()}")
print(f"Freemium:                   {freemium_users.count()}")
print(f"Eligibles decouverte:       {eligible.count()}")
print(f"Avec photo(s):              {len(profiles_with_photos)}")
print(f"Sans photo:                 {profiles_without_photos.count()}")
print("=" * 80)