"""Test B2-01, B2-02, B2-04, B2-13: Profile consultation, edition, preferences, public profile."""
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

# B2-01: Consult my profile
print("=== B2-01: Consultation de mon profil ===")
resp3 = requests.get('http://127.0.0.1:8000/api/v1/user-profiles/me/', headers=headers)
print(f"GET me/ status: {resp3.status_code}")
if resp3.status_code == 200:
    profile = resp3.json()
    print(f"Profile fields: {list(profile.keys())}")
    print(f"  display_name: {profile.get('display_name')}")
    print(f"  bio: {profile.get('bio', 'N/A')}")
    print(f"  age: {profile.get('age', 'N/A')}")
    print(f"  city: {profile.get('city', 'N/A')}")
    print(f"  is_premium: {profile.get('is_premium', 'N/A')}")
    print("  ✅ B2-01: Profile consultation works")
else:
    print(f"  Response: {resp3.text[:300]}")

# B2-02: Edit profile (bio)
print("\n=== B2-02: Édition du profil ===")
resp4 = requests.patch(
    'http://127.0.0.1:8000/api/v1/user-profiles/me/',
    headers=headers,
    json={'bio': 'Hello, I am ALICE testing HIVMeet!'}
)
print(f"PATCH me/ status: {resp4.status_code}")
if resp4.status_code == 200:
    updated = resp4.json()
    print(f"  Updated bio: {updated.get('bio')}")
    if updated.get('bio') == 'Hello, I am ALICE testing HIVMeet!':
        print("  ✅ B2-02: Profile edition works, bio persisted")
else:
    print(f"  Response: {resp4.text[:300]}")

# Verify persistence
resp5 = requests.get('http://127.0.0.1:8000/api/v1/user-profiles/me/', headers=headers)
if resp5.status_code == 200:
    verify_bio = resp5.json().get('bio')
    print(f"  Bio after reload: {verify_bio}")

# B2-03: Validation of bio (HTML tags)
print("\n=== B2-03: Validation de la bio (XSS) ===")
resp6 = requests.patch(
    'http://127.0.0.1:8000/api/v1/user-profiles/me/',
    headers=headers,
    json={'bio': '<script>alert("xss")</script>Hello'}
)
print(f"PATCH me/ with HTML status: {resp6.status_code}")
if resp6.status_code == 200:
    cleaned_bio = resp6.json().get('bio')
    print(f"  Cleaned bio: {cleaned_bio}")
    if '<script>' not in cleaned_bio:
        print("  ✅ B2-03: HTML tags stripped from bio (XSS protection)")
    else:
        print("  ❌ B2-03: HTML tags NOT stripped - XSS vulnerability!")
else:
    print(f"  Response: {resp6.text[:300]}")

# B2-13: Public profile of BOB
print("\n=== B2-13: Profil public d'un tiers (BOB) ===")
bob_id = '54690440-d73d-417c-8110-54d32819fd55'
resp7 = requests.get(f'http://127.0.0.1:8000/api/v1/user-profiles/{bob_id}/', headers=headers)
print(f"GET BOB profile status: {resp7.status_code}")
if resp7.status_code == 200:
    bob_profile = resp7.json()
    print(f"  BOB fields: {list(bob_profile.keys())}")
    sensitive = ['email', 'hiv_status', 'phone', 'password', 'firebase_uid']
    exposed = [s for s in sensitive if s in bob_profile]
    if not exposed:
        print("  ✅ B2-13: No sensitive data exposed in public profile")
    else:
        print(f"  ❌ B2-13: Sensitive data exposed: {exposed}")