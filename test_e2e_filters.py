"""Test B3-14, B3-19: Age filter and filter persistence."""
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

# B3-19: Get current filters
print("=== B3-19: Get current filters ===")
resp = requests.get('http://127.0.0.1:8000/api/v1/discovery/filters/get', headers=headers)
print(f"GET filters status: {resp.status_code}")
print(f"Current filters: {json.dumps(resp.json(), indent=2)[:500]}")

# B3-14: Set age filter 30-35
print("\n=== B3-14: Set age filter 30-35 ===")
resp3 = requests.put(
    'http://127.0.0.1:8000/api/v1/discovery/filters',
    headers=headers,
    json={'age_min': 30, 'age_max': 35}
)
print(f"PUT filters status: {resp3.status_code}")
print(f"Response: {json.dumps(resp3.json(), indent=2)[:500]}")

# Verify filters were saved
print("\n=== B3-19: Verify filters persisted ===")
resp4 = requests.get('http://127.0.0.1:8000/api/v1/discovery/filters/get', headers=headers)
print(f"GET filters status: {resp4.status_code}")
print(f"Persisted filters: {json.dumps(resp4.json(), indent=2)[:500]}")

# Check discovery profiles with age filter
print("\n=== B3-14: Check profiles with age 30-35 ===")
resp5 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 20})
data = resp5.json()
print(f"Profiles count: {data['count']}")
for p in data['results'][:10]:
    age = p.get('age', 'N/A')
    name = p.get('display_name', 'N/A')
    in_range = "✅" if age and 30 <= age <= 35 else "❌"
    print(f"  {in_range} {name}, age={age}")