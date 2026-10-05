"""Test B3-20: Boost (gratuit) - should return 403."""
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

# B3-20: Try boost as free user
print("=== B3-20: Boost (gratuit) ===")
resp = requests.post(
    'http://127.0.0.1:8000/api/v1/discovery/boost/activate',
    headers=headers,
)
print(f"Boost status: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), indent=2, default=str)[:500]}")

if resp.status_code == 403:
    print("\n✅ B3-20 CONFIRMED: Boost returns 403 for free users")
else:
    print(f"\n⚠️ Unexpected status: {resp.status_code}")

# Reset ALICE's filters to default
print("\n=== Resetting ALICE's filters to default ===")
resp3 = requests.put(
    'http://127.0.0.1:8000/api/v1/discovery/filters',
    headers=headers,
    json={'age_min': 18, 'age_max': 99, 'distance_max_km': 25}
)
print(f"Reset filters status: {resp3.status_code}")