"""Test B3-12: Rewind (gratuit) - should return 403 for free users."""
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

# Try rewind
print("=== Testing REWIND for free user ALICE ===")
resp4 = requests.post(
    'http://127.0.0.1:8000/api/v1/discovery/interactions/rewind',
    headers=headers,
)
print(f"Rewind status: {resp4.status_code}")
print(f"Response: {json.dumps(resp4.json(), indent=2, default=str)[:500]}")

if resp4.status_code == 403:
    print("\n✅ B3-12 CONFIRMED: Rewind returns 403 for free users")
elif resp4.status_code == 200:
    print("\n⚠️ B3-12 ISSUE: Rewind succeeded for free user (should be 403)")
    print("This matches the known anomaly A-04: frontend shows button but backend returns 403")
else:
    print(f"\n⚠️ Unexpected status: {resp4.status_code}")