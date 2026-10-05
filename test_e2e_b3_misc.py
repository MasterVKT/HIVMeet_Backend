"""Test B3-03, B3-04, B3-15, B3-22, B3-23: Card content, profile detail, gender filter, no self-display, no repetition."""
import firebase_admin
from firebase_admin import auth, credentials
import requests
import json

# Initialize Firebase Admin
cred = credentials.Certificate('credentials/hivmeet_firebase_credentials.json')
try:
    firebase_admin.delete_app(firebase_admin.get_app())
except Exception:
    pass
firebase_admin.initialize_app(cred)

FIREBASE_WEB_API_KEY = 'AIzaSyB_Osga8cc7BEyXYP7hEsmH1yE4i5tctgo'

# Get ALICE's ID token
custom_token = auth.create_custom_token('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
if isinstance(custom_token, bytes):
    custom_token = custom_token.decode()

resp = requests.post(
    f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}',
    json={'token': custom_token, 'returnSecureToken': True}
)
id_token = resp.json().get('idToken')

# Exchange for JWT
resp2 = requests.post(
    'http://127.0.0.1:8000/api/v1/auth/firebase-exchange/',
    json={'firebase_token': id_token},
)
jwt_token = resp2.json().get('token') or resp2.json().get('access')
headers = {'Authorization': f'Bearer {jwt_token}'}

# B3-22: No self-display
print("=== B3-22: Pas d'auto-affichage ===")
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 20})
data = resp3.json()
alice_id = '8a0042c6-ccb9-4e9f-b050-1f8b0d5be350'
self_found = any(p['user_id'] == alice_id for p in data['results'])
print(f"  ALICE appears in her own deck? {self_found}")
if not self_found:
    print("  ✅ B3-22: ALICE does not see herself in discovery")

# B3-03: Card content - verify all expected fields are present
print("\n=== B3-03: Contenu de la carte ===")
if data['results']:
    p = data['results'][0]
    expected_fields = ['user_id', 'display_name', 'age', 'bio', 'city', 'country', 'photos', 'interests', 'is_verified', 'is_online', 'distance_km']
    missing = [f for f in expected_fields if f not in p]
    print(f"  Profile fields: {list(p.keys())}")
    print(f"  Missing fields: {missing if missing else 'None'}")
    if not missing:
        print("  ✅ B3-03: All expected fields present in card data")

# B3-04: Profile detail - GET user-profiles/<user_id>/
print("\n=== B3-04: Détail d'un profil ===")
if data['results']:
    target_id = data['results'][0]['user_id']
    resp4 = requests.get(f'http://127.0.0.1:8000/api/v1/user-profiles/{target_id}/', headers=headers)
    print(f"  GET user-profiles/{target_id[:8]}.../ status: {resp4.status_code}")
    if resp4.status_code == 200:
        profile_data = resp4.json()
        print(f"  Profile fields: {list(profile_data.keys())}")
        # Check no sensitive data exposed
        sensitive = ['hiv_status', 'email', 'phone', 'password']
        exposed = [s for s in sensitive if s in profile_data]
        print(f"  Sensitive data exposed: {exposed if exposed else 'None'}")
        if not exposed:
            print("  ✅ B3-04: Profile detail accessible, no sensitive data exposed")
    else:
        print(f"  Response: {resp4.text[:300]}")

# B3-23: No repetition - already liked profiles don't reappear
print("\n=== B3-23: Pas de répétition ===")
# ALICE already liked BOB - check he doesn't appear
bob_id = '54690440-d73d-417c-8110-54d32819fd55'
bob_in_deck = any(p['user_id'] == bob_id for p in data['results'])
print(f"  BOB (already liked) appears in deck? {bob_in_deck}")
if not bob_in_deck:
    print("  ✅ B3-23: Already-liked profiles don't reappear")

# B3-15: Gender filter
print("\n=== B3-15: Filtre de genre ===")
resp5 = requests.put(
    'http://127.0.0.1:8000/api/v1/discovery/filters',
    headers=headers,
    json={'genders': ['female'], 'age_min': 18, 'age_max': 99}
)
print(f"  PUT filters (genders=['female']) status: {resp5.status_code}")

resp6 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 20})
data6 = resp6.json()
print(f"  Profiles with female filter: {data6['count']}")
for p in data6['results'][:5]:
    print(f"    - {p['display_name']}, age={p.get('age')}")

# Reset gender filter
requests.put(
    'http://127.0.0.1:8000/api/v1/discovery/filters',
    headers=headers,
    json={'genders': [], 'age_min': 18, 'age_max': 99}
)
print("  Reset gender filter to default")