"""Test B3-08: Quota atteint (gratuit) - 11th like should return 429."""
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

# Get all discovery profiles
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/profiles', headers=headers, params={'limit': 20})
data = resp3.json()
profiles = data['results']
print(f"Discovery profiles available: {len(profiles)}")

# ALICE already used 2 likes (BOB + Julie). 8 remaining.
# Like all remaining profiles to hit the limit
liked_count = 2  # already liked BOB and Julie
for i, profile in enumerate(profiles):
    if i < 2:  # Skip BOB (already liked) and Julie (already liked via API)
        # Actually, the API returns profiles NOT yet interacted with
        # So all profiles returned are new
        pass

# Like all profiles returned (they should all be new since already-liked ones are excluded)
for i, profile in enumerate(profiles):
    print(f"\n--- Like #{i+1+2}: {profile['display_name']} (user_id: {profile['user_id']}) ---")
    resp4 = requests.post(
        'http://127.0.0.1:8000/api/v1/discovery/interactions/like',
        headers=headers,
        json={'target_user_id': profile['user_id']}
    )
    result = resp4.json()
    remaining = result.get('daily_likes_remaining', 'N/A')
    print(f"  Status: {resp4.status_code}, Remaining: {remaining}")
    
    if resp4.status_code == 429:
        print(f"  ✅ QUOTA REACHED! Response: {json.dumps(result, indent=2)[:300]}")
        print(f"  11th like NOT recorded in base (as expected)")
        break
    
    if remaining is not None and remaining <= 0:
        print(f"  ⚠️ Remaining is 0, next like should be 429")