"""Test B4-06: Unmatch and B6-01, B6-02: Messaging."""
import firebase_admin
from firebase_admin import auth, credentials
import requests
import json
import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hivmeet_backend.settings')
django.setup()

from matching.models import Match
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

# Get the match
match = Match.objects.filter(user1__in=[alice, bob], user2__in=[alice, bob]).first()
print(f"=== B4-06: Unmatch ===")
print(f"Match ID: {match.id if match else 'None'}")

if match:
    alice_jwt = get_jwt('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
    headers_alice = {'Authorization': f'Bearer {alice_jwt}'}
    
    # Delete the match (unmatch) - no trailing slash in URL conf
    resp = requests.delete(
        f'http://127.0.0.1:8000/api/v1/matches/{match.id}',
        headers=headers_alice,
    )
    print(f"DELETE matches/{match.id}/ status: {resp.status_code}")
    if resp.status_code in [204, 200]:
        print("  ✅ B4-06: Unmatch successful")
        # Verify match is gone from DB
        match_after = Match.objects.filter(id=match.id).exists()
        print(f"  Match still in DB? {match_after}")
        if not match_after:
            print("  ✅ B4-06: Match removed from DB")
    else:
        print(f"  Response: {resp.text[:300]}")

# B6-01: Re-create match and test conversations
print(f"\n=== B6-01: Conversations after match ===")
# Re-like BOB → ALICE to recreate match
bob_jwt = get_jwt('0CGAcRwXT9PrroJYZUPq7HWMzqP2')
headers_bob = {'Authorization': f'Bearer {bob_jwt}'}

# BOB likes ALICE again
resp2 = requests.post(
    'http://127.0.0.1:8000/api/v1/discovery/interactions/like',
    headers=headers_bob,
    json={'target_user_id': str(alice.id)}
)
print(f"BOB likes ALICE again: status={resp2.status_code}")
match_id = None
if resp2.status_code == 200:
    result = resp2.json()
    print(f"  status: {result.get('status')}")
    match_id = result.get('match_id')
    if match_id:
        print(f"  Match ID: {match_id}")

# B6-02: Send a message using the match ID as conversation ID
print(f"\n=== B6-02: Envoi de message ===")
if match_id:
    # Send message from ALICE to BOB
    import uuid
    resp5 = requests.post(
        f'http://127.0.0.1:8000/api/v1/conversations/{match_id}/messages/',
        headers={**headers_alice, 'Content-Type': 'application/json'},
        json={'content': 'Hello BOB, nice to meet you!', 'client_message_id': str(uuid.uuid4())}
    )
    print(f"  POST messages/ status: {resp5.status_code}")
    if resp5.status_code in [200, 201]:
        print(f"  ✅ B6-02: Message sent successfully")
        print(f"  Response: {json.dumps(resp5.json(), indent=2, default=str)[:300]}")
    else:
        print(f"  Response: {resp5.text[:500]}")
    
    # Now check conversations - should appear after first message
    resp6 = requests.get('http://127.0.0.1:8000/api/v1/conversations/', headers=headers_alice)
    print(f"\n  GET conversations/ after message: status={resp6.status_code}")
    if resp6.status_code == 200:
        conv_data = resp6.json()
        results = conv_data.get('results', []) if isinstance(conv_data, dict) else conv_data
        print(f"  Conversations count: {len(results)}")
        for c in results:
            print(f"    - ID: {c.get('id', 'N/A')}, last_message: {c.get('last_message', {}).get('content', 'N/A')[:50]}")
else:
    print("  No match created, cannot test messaging")