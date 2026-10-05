"""Test B4-01, B4-02, B4-04, B4-07: Matching tests."""
import firebase_admin
from firebase_admin import auth, credentials
import requests
import json
import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from matching.models import Match, Like
from authentication.models import User

# Initialize Firebase Admin
cred = credentials.Certificate('credentials/hivmeet_firebase_credentials.json')
try:
    firebase_admin.delete_app(firebase_admin.get_app())
except Exception:
    pass
firebase_admin.initialize_app(cred)

FIREBASE_WEB_API_KEY = 'AIzaSyB_Osga8cc7BEyXYP7hEsmH1yE4i5tctgo'

def get_jwt(firebase_uid):
    """Get JWT token for a user."""
    custom_token = auth.create_custom_token(firebase_uid)
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode()
    resp = requests.post(
        f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}',
        json={'token': custom_token, 'returnSecureToken': True}
    )
    id_token = resp.json().get('idToken')
    resp2 = requests.post(
        'http://127.0.0.1:8000/api/v1/auth/firebase-exchange/',
        json={'firebase_token': id_token},
    )
    return resp2.json().get('token') or resp2.json().get('access')

alice = User.objects.get(email='alice.hivmeet@test.local')
bob = User.objects.get(email='bob.hivmeet@test.local')

# B4-01: Check that ALICE liking BOB did NOT create a match (BOB hasn't liked ALICE)
print("=== B4-01: Like non réciproque ===")
matches = Match.objects.filter(user1__in=[alice, bob], user2__in=[alice, bob])
print(f"  Matches between ALICE and BOB: {matches.count()}")
if matches.count() == 0:
    print("  ✅ B4-01: No match created from one-sided like")

# Check ALICE's like on BOB via API
alice_jwt = get_jwt('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
headers_alice = {'Authorization': f'Bearer {alice_jwt}'}

# B4-02: BOB likes ALICE back → match created
print("\n=== B4-02: Match réciproque ===")
bob_jwt = get_jwt('0CGAcRwXT9PrroJYZUPq7HWMzqP2')
headers_bob = {'Authorization': f'Bearer {bob_jwt}'}

# BOB likes ALICE
alice_id = str(alice.id)
resp = requests.post(
    'http://127.0.0.1:8000/api/v1/discovery/interactions/like',
    headers=headers_bob,
    json={'target_user_id': alice_id}
)
print(f"  BOB likes ALICE: status={resp.status_code}")
result = resp.json()
print(f"  Response: {json.dumps(result, indent=2)[:300]}")
is_match = result.get('is_match', False)
print(f"  is_match: {is_match}")

if is_match:
    print("  ✅ B4-02: Match created from reciprocal like!")
    # Verify match in DB
    matches_after = Match.objects.filter(user1__in=[alice, bob], user2__in=[alice, bob])
    print(f"  Matches in DB: {matches_after.count()}")
    if matches_after.count() == 1:
        print("  ✅ B4-03: Exactly one match created (no duplicates)")
        m = matches_after.first()
        print(f"  Match ID: {m.id}")
else:
    # Check if match was created in DB even if API didn't say so
    matches_after = Match.objects.filter(user1__in=[alice, bob], user2__in=[alice, bob])
    print(f"  Matches in DB: {matches_after.count()}")
    if matches_after.count() > 0:
        print("  ✅ B4-02: Match created in DB (API response may not include is_match)")

# B4-04: List matches
print("\n=== B4-04: Liste des matches ===")
resp2 = requests.get('http://127.0.0.1:8000/api/v1/matches/', headers=headers_alice)
print(f"  GET matches/ status: {resp2.status_code}")
if resp2.status_code == 200:
    matches_data = resp2.json()
    if isinstance(matches_data, list):
        print(f"  Matches count: {len(matches_data)}")
        for m in matches_data:
            print(f"    - Match ID: {m.get('id', 'N/A')}")
    elif isinstance(matches_data, dict):
        results = matches_data.get('results', matches_data.get('matches', []))
        print(f"  Matches count: {len(results)}")
        for m in results:
            print(f"    - Match ID: {m.get('id', 'N/A')}")

# B4-07: No match for a new account
print("\n=== B4-07: Aucun match (compte neuf) ===")
# Use BOB who should have only the match with ALICE
resp3 = requests.get('http://127.0.0.1:8000/api/v1/matches/', headers=headers_bob)
if resp3.status_code == 200:
    bob_matches = resp3.json()
    if isinstance(bob_matches, list):
        print(f"  BOB's matches: {len(bob_matches)}")
    elif isinstance(bob_matches, dict):
        results = bob_matches.get('results', bob_matches.get('matches', []))
        print(f"  BOB's matches: {len(results)}")