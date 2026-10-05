"""Test B3-05, B3-06 via API: like and dislike profiles."""
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

# Get discovery profiles
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 5})
data = resp3.json()
print(f"Discovery status: {resp3.status_code}")
print(f"Profiles count: {data['count']}")
print(f"First profile: {data['results'][0]['display_name']}, {data['results'][0]['age']}")

# Get the first profile (should be next after BOB was already liked)
first_profile = data['results'][0]
print(f"\n=== Testing LIKE on {first_profile['display_name']} (user_id: {first_profile['user_id']}) ===")

# Like the first profile
resp4 = requests.post(
    'http://127.0.0.1:8000/api/v1/discovery/interactions/like',
    headers=headers,
    json={'target_user_id': first_profile['user_id']}
)
print(f"Like status: {resp4.status_code}")
print(f"Like response: {json.dumps(resp4.json(), indent=2, default=str)[:500]}")

# Check daily likes remaining
resp5 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 1})
if resp5.status_code == 200:
    next_data = resp5.json()
    if next_data['results']:
        print(f"\nNext profile after like: {next_data['results'][0]['display_name']}, {next_data['results'][0]['age']}")
    
# Now test DISLIKE on the next profile
if next_data['results']:
    second_profile = next_data['results'][0]
    print(f"\n=== Testing DISLIKE on {second_profile['display_name']} (user_id: {second_profile['user_id']}) ===")
    resp6 = requests.post(
        'http://127.0.0.1:8000/api/v1/discovery/interactions/dislike',
        headers=headers,
        json={'target_user_id': second_profile['user_id']}
    )
    print(f"Dislike status: {resp6.status_code}")
    print(f"Dislike response: {json.dumps(resp6.json(), indent=2, default=str)[:500]}")