"""Test B5-01, B5-02, B5-03: Interaction history and B8-01: Notifications."""
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

# ALICE's JWT
alice_jwt = get_jwt('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
headers = {'Authorization': f'Bearer {alice_jwt}'}

# B5-01: My likes history
print("=== B5-01: Historique des likes (my-likes) ===")
resp = requests.get('http://127.0.0.1:8000/api/v1/discovery/interactions/my-likes', headers=headers)
print(f"GET my-likes status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Likes count: {len(results)}")
    for r in results[:5]:
        print(f"    - {r.get('target_user', {}).get('display_name', r.get('display_name', 'N/A'))}")
    print("  ✅ B5-01: My likes history accessible")
else:
    print(f"  Response: {resp.text[:300]}")

# B5-02: My passes (dislikes) history
print("\n=== B5-02: Historique des passes (my-passes) ===")
resp2 = requests.get('http://127.0.0.1:8000/api/v1/discovery/interactions/my-passes', headers=headers)
print(f"GET my-passes status: {resp2.status_code}")
if resp2.status_code == 200:
    data = resp2.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Passes count: {len(results)}")
    print("  ✅ B5-02: My passes history accessible")
else:
    print(f"  Response: {resp2.text[:300]}")

# B5-03: Stats
print("\n=== B5-03: Statistiques d'interactions ===")
resp3 = requests.get('http://127.0.0.1:8000/api/v1/discovery/interactions/status', headers=headers)
print(f"GET interactions/status: {resp3.status_code}")
if resp3.status_code == 200:
    print(f"  Response: {json.dumps(resp3.json(), indent=2, default=str)[:500]}")
    print("  ✅ B5-03: Interaction stats accessible")
else:
    print(f"  Response: {resp3.text[:300]}")

# B8-01: Notifications list
print("\n=== B8-01: Liste des notifications ===")
resp4 = requests.get('http://127.0.0.1:8000/api/v1/notifications/', headers=headers)
print(f"GET notifications/ status: {resp4.status_code}")
if resp4.status_code == 200:
    data = resp4.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Notifications count: {len(results)}")
    for n in results[:5]:
        print(f"    - type: {n.get('type', 'N/A')}, title: {n.get('title', 'N/A')[:40]}")
    print("  ✅ B8-01: Notifications list accessible")
else:
    print(f"  Response: {resp4.text[:300]}")

# B5-04: Likes received (premium feature - ALICE is free, should get 403 or limited)
print("\n=== B5-04: Likes received (premium feature for free user) ===")
resp5 = requests.get('http://127.0.0.1:8000/api/v1/user-profiles/likes-received/', headers=headers)
print(f"GET likes-received/ status: {resp5.status_code}")
if resp5.status_code == 200:
    data = resp5.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Likes received count: {len(results)}")
    print("  ⚠️ B5-04: Free user can see likes received (may need premium gating)")
elif resp5.status_code == 403:
    print("  ✅ B5-04: Free user blocked from likes received (premium feature)")
else:
    print(f"  Response: {resp5.text[:300]}")