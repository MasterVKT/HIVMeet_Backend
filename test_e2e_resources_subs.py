"""Test B9-01, B9-02: Resources and B10-01, B10-02: Subscriptions."""
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

# B9-01: Resources list (no trailing slash)
print("=== B9-01: Liste des ressources ===")
resp = requests.get('http://127.0.0.1:8000/api/v1/content/resources', headers=headers)
print(f"GET resources/ status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Resources count: {len(results)}")
    for r in results[:5]:
        print(f"    - {r.get('title', 'N/A')} (type: {r.get('type', r.get('resource_type', 'N/A'))})")
    print("  ✅ B9-01: Resources list accessible")
else:
    print(f"  Response: {resp.text[:300]}")

# B9-02: Resource detail
print("\n=== B9-02: Détail d'une ressource ===")
if resp.status_code == 200:
    data = resp.json()
    results = data if isinstance(data, list) else data.get('results', [])
    if results:
        resource_id = results[0].get('id')
        resp2 = requests.get(f'http://127.0.0.1:8000/api/v1/content/resources/{resource_id}', headers=headers)
        print(f"GET resources/{resource_id[:8]}.../ status: {resp2.status_code}")
        if resp2.status_code == 200:
            print(f"  Title: {resp2.json().get('title', 'N/A')}")
            print("  ✅ B9-02: Resource detail accessible")

# B9-03: Feed list
print("\n=== B9-03: Feed communautaire ===")
resp3 = requests.get('http://127.0.0.1:8000/api/v1/feed/posts', headers=headers)
print(f"GET feed/posts/ status: {resp3.status_code}")
if resp3.status_code == 200:
    data = resp3.json()
    results = data if isinstance(data, list) else data.get('results', [])
    print(f"  Feed posts count: {len(results)}")
    print("  ✅ B9-03: Feed list accessible")
else:
    print(f"  Response: {resp3.text[:300]}")

# B10-01: Subscription plans
print("\n=== B10-01: Plans d'abonnement ===")
resp4 = requests.get('http://127.0.0.1:8000/api/v1/subscriptions/plans/', headers=headers)
print(f"GET subscriptions/plans/ status: {resp4.status_code}")
if resp4.status_code == 200:
    data = resp4.json()
    plans = data if isinstance(data, list) else data.get('results', data.get('plans', []))
    print(f"  Plans count: {len(plans)}")
    for p in plans:
        print(f"    - {p.get('name', p.get('plan_id', 'N/A'))}: {p.get('price', 'N/A')} {p.get('currency', 'N/A')}")
    print("  ✅ B10-01: Subscription plans accessible")
else:
    print(f"  Response: {resp4.text[:300]}")

# B10-02: Current subscription status
print("\n=== B10-02: Statut d'abonnement ===")
resp5 = requests.get('http://127.0.0.1:8000/api/v1/subscriptions/current/', headers=headers)
print(f"GET subscriptions/status/ status: {resp5.status_code}")
if resp5.status_code == 200:
    print(f"  Response: {json.dumps(resp5.json(), indent=2)[:500]}")
    print("  ✅ B10-02: Subscription status accessible")
else:
    print(f"  Response: {resp5.text[:300]}")

# B10-03: Premium status
print("\n=== B10-03: Statut premium ===")
resp6 = requests.get('http://127.0.0.1:8000/api/v1/user-profiles/premium-status/', headers=headers)
print(f"GET premium-status/ status: {resp6.status_code}")
if resp6.status_code == 200:
    print(f"  Response: {json.dumps(resp6.json(), indent=2)[:500]}")
    print("  ✅ B10-03: Premium status accessible")
else:
    print(f"  Response: {resp6.text[:300]}")