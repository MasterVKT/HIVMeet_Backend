"""Generate a Firebase custom token for API testing."""
import firebase_admin
from firebase_admin import auth, credentials

cred = credentials.Certificate('credentials/hivmeet_firebase_credentials.json')
try:
    firebase_admin.delete_app(firebase_admin.get_app())
except Exception:
    pass
firebase_admin.initialize_app(cred)

# ALICE's Firebase UID
token = auth.create_custom_token('7bf8fyLAnYTg6xnhwaJFr4tshvx2')
print(token.decode() if isinstance(token, bytes) else token)