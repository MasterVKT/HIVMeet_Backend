"""Test B3-02: Deck vide - check if ALICE has exhausted all profiles."""
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

# Check discovery profiles
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 50})
data = resp3.json()
print(f"Discovery profiles available: {data['count']}")
if data['count'] == 0:
    print("✅ B3-02: Deck is EMPTY - ALICE has interacted with all profiles")
    print("The frontend should show an empty state, not a white screen or infinite spinner")
else:
    print(f"Deck still has {data['count']} profiles")
    print("To test B3-02 (empty deck), we need to interact with all remaining profiles")
    # List remaining profiles
    for p in data['results']:
        print(f"  - {p['display_name']}, age={p.get('age', 'N/A')}")