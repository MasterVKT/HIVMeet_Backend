"""Test discovery API endpoint with ALICE's Firebase token - E2E test version."""
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

# Create a custom token for ALICE
custom_token = auth.create_custom_token('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
if isinstance(custom_token, bytes):
    custom_token = custom_token.decode()

# Exchange custom token for ID token via Identity Toolkit
FIREBASE_WEB_API_KEY = 'AIzaSyB_Osga8cc7BEyXYP7hEsmH1yE4i5tctgo'
resp = requests.post(
    f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}',
    json={
        'token': custom_token,
        'returnSecureToken': True,
    }
)
data = resp.json()
id_token = data.get('idToken')

if not id_token:
    print("Failed to get ID token:", json.dumps(data, indent=2))
    exit(1)

# Now call the backend's firebase-exchange endpoint
resp2 = requests.post(
    'http://127.0.0.1:8000/api/v1/auth/firebase-exchange/',
    json={'firebase_token': id_token},
)
exchange_data = resp2.json()
jwt_token = exchange_data.get('token') or exchange_data.get('access')

if not jwt_token:
    print("Failed to get JWT:", json.dumps(exchange_data, indent=2))
    exit(1)

print(f"JWT obtained: {jwt_token[:50]}...")

# Call discovery endpoint (no trailing slash in URL conf)
resp3 = requests.get(
    'http://127.0.0.1:8000/api/v1/discovery/profiles',
    headers={'Authorization': f'Bearer {jwt_token}'},
    params={'limit': 5},
)
print(f"\nDiscovery API status: {resp3.status_code}")
if resp3.status_code == 200:
    print(f"Discovery response: {json.dumps(resp3.json(), indent=2, default=str)[:3000]}")
else:
    print(f"Response text: {resp3.text[:1000]}")