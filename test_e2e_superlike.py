"""Test B3-10: Super-like (gratuit) - 1st should pass, 2nd should return 429."""
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

# Get discovery profiles (ALICE has used all 10 likes, so she may have 0 left)
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 5})
data = resp3.json()
print(f"Discovery profiles available: {data['count']}")
if data['results']:
    first = data['results'][0]
    print(f"First profile: {first['display_name']} (user_id: {first['user_id']})")
    
    # Try super-like
    print(f"\n=== Testing SUPER-LIKE on {first['display_name']} ===")
    resp4 = requests.post(
        'http://127.0.0.1:8000/api/v1/discovery/interactions/superlike',
        headers=headers,
        json={'target_user_id': first['user_id']}
    )
    print(f"Super-like #1 status: {resp4.status_code}")
    print(f"Response: {json.dumps(resp4.json(), indent=2, default=str)[:500]}")
    
    if data['count'] > 1:
        second = data['results'][1]
        print(f"\n=== Testing 2nd SUPER-LIKE on {second['display_name']} ===")
        resp5 = requests.post(
            'http://127.0.0.1:8000/api/v1/discovery/interactions/superlike',
            headers=headers,
            json={'target_user_id': second['user_id']}
        )
        print(f"Super-like #2 status: {resp5.status_code}")
        print(f"Response: {json.dumps(resp5.json(), indent=2, default=str)[:500]}")
else:
    print("No profiles available for super-like test (all profiles already interacted with)")
    print("Need to reset ALICE's interactions or use a different test account")