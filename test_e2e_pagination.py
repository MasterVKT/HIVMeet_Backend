"""Test B3-24: Pagination / cyclage - verify page 2 loads without duplicates."""
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

# Get page 1
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'page': 1, 'page_size': 5})
data1 = resp3.json()
page1_ids = set(p['user_id'] for p in data1['results'])
print(f"Page 1: {len(data1['results'])} profiles, count={data1['count']}, next={data1['next']}")
for p in data1['results']:
    print(f"  - {p['display_name']} (id: {p['user_id'][:8]}...)")

# Get page 2
resp4 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'page': 2, 'page_size': 5})
data2 = resp4.json()
page2_ids = set(p['user_id'] for p in data2['results'])
print(f"\nPage 2: {len(data2['results'])} profiles, count={data2['count']}, next={data2.get('next')}")
for p in data2['results']:
    print(f"  - {p['display_name']} (id: {p['user_id'][:8]}...)")

# Check for duplicates between pages
duplicates = page1_ids & page2_ids
print(f"\nDuplicates between page 1 and 2: {len(duplicates)}")
if len(duplicates) == 0:
    print("✅ B3-24: No duplicates between pages - pagination works correctly")
else:
    print(f"❌ B3-24: Found duplicates: {duplicates}")

# Check total unique profiles across pages
all_ids = page1_ids | page2_ids
print(f"\nTotal unique profiles across 2 pages: {len(all_ids)} (expected: {data1['count']})")