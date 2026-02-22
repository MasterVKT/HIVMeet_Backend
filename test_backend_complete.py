#!/usr/bin/env python3
"""
Backend de test complet pour HIVMeet avec profils de découverte
Usage: python test_backend_complete.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Compteur de likes pour simulation
likes_remaining = 10

# Profils de test
TEST_PROFILES = [
    {
        "id": str(uuid.uuid4()),
        "display_name": "Sophie",
        "age": 28,
        "bio": "Passionnée de voyages et de photographie 📸",
        "city": "Paris",
        "country": "France",
        "photos": [
            {"photo_url": "http://10.0.2.2:8000/media/default_female.jpg", "is_main": True}
        ],
        "interests": ["Voyages", "Photographie", "Cuisine"],
        "is_verified": True,
        "is_online": False,
        "last_active": (datetime.now() - timedelta(hours=2)).isoformat(),
        "distance_km": 5.2
    },
    {
        "id": str(uuid.uuid4()),
        "display_name": "Thomas",
        "age": 32,
        "bio": "Amateur de cuisine et de randonnée 🏔️",
        "city": "Lyon",
        "country": "France",
        "photos": [
            {"photo_url": "http://10.0.2.2:8000/media/default_male.jpg", "is_main": True}
        ],
        "interests": ["Cuisine", "Randonnée", "Musique"],
        "is_verified": False,
        "is_online": True,
        "last_active": datetime.now().isoformat(),
        "distance_km": 12.8
    },
    {
        "id": str(uuid.uuid4()),
        "display_name": "Emma",
        "age": 26,
        "bio": "Yoga, méditation et vie saine 🧘‍♀️",
        "city": "Paris",
        "country": "France",
        "photos": [
            {"photo_url": "http://10.0.2.2:8000/media/default_female.jpg", "is_main": True}
        ],
        "interests": ["Yoga", "Méditation", "Sport"],
        "is_verified": True,
        "is_online": False,
        "last_active": (datetime.now() - timedelta(days=1)).isoformat(),
        "distance_km": 3.5
    },
    {
        "id": str(uuid.uuid4()),
        "display_name": "Lucas",
        "age": 30,
        "bio": "Développeur et gamer passionné 🎮",
        "city": "Paris",
        "country": "France",
        "photos": [
            {"photo_url": "http://10.0.2.2:8000/media/default_male.jpg", "is_main": True}
        ],
        "interests": ["Gaming", "Tech", "Cinéma"],
        "is_verified": False,
        "is_online": True,
        "last_active": datetime.now().isoformat(),
        "distance_km": 8.2
    },
    {
        "id": str(uuid.uuid4()),
        "display_name": "Léa",
        "age": 27,
        "bio": "Artiste et musicienne 🎨🎵",
        "city": "Paris",
        "country": "France",
        "photos": [
            {"photo_url": "http://10.0.2.2:8000/media/default_female.jpg", "is_main": True}
        ],
        "interests": ["Art", "Musique", "Culture"],
        "is_verified": True,
        "is_online": False,
        "last_active": (datetime.now() - timedelta(hours=5)).isoformat(),
        "distance_km": 6.7
    }
]

@app.route('/api/v1/discovery/profiles', methods=['GET'])
def discovery_profiles():
    """Retourne les profils de découverte"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token manquant ou invalide'}), 401
    
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size
    profiles_page = TEST_PROFILES[start:end]
    
    return jsonify({
        'count': len(TEST_PROFILES),
        'next': f'/api/v1/discovery/profiles?page={page+1}&page_size={page_size}' if end < len(TEST_PROFILES) else None,
        'previous': f'/api/v1/discovery/profiles?page={page-1}&page_size={page_size}' if page > 1 else None,
        'results': profiles_page
    })

@app.route('/api/v1/discovery/interactions/like', methods=['POST'])
def like_profile():
    """Like un profil"""
    global likes_remaining
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token manquant ou invalide'}), 401
    
    data = request.get_json()
    target_user_id = data.get('target_user_id')
    
    if not target_user_id:
        return jsonify({'error': 'target_user_id requis'}), 400
    
    # Décrémenter les likes restants
    if likes_remaining > 0:
        likes_remaining -= 1
    
    # Simuler un match 20% du temps
    is_match = (likes_remaining % 5 == 0)
    
    return jsonify({
        'result': 'match' if is_match else 'like_sent',
        'match_id': str(uuid.uuid4()) if is_match else None,
        'daily_likes_remaining': likes_remaining,
        'super_likes_remaining': 3,
        'message': "It's a match!" if is_match else "Like envoyé"
    })

@app.route('/api/v1/discovery/interactions/dislike', methods=['POST'])
def dislike_profile():
    """Dislike un profil"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token manquant ou invalide'}), 401
    
    data = request.get_json()
    target_user_id = data.get('target_user_id')
    
    if not target_user_id:
        return jsonify({'error': 'target_user_id requis'}), 400
    
    return jsonify({
        'result': 'dislike_sent',
        'message': 'Profil ignoré'
    })

@app.route('/api/v1/discovery/interactions/superlike', methods=['POST'])
def superlike_profile():
    """Super-like un profil"""
    global likes_remaining
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Token manquant ou invalide'}), 401
    
    data = request.get_json()
    target_user_id = data.get('target_user_id')
    
    if not target_user_id:
        return jsonify({'error': 'target_user_id requis'}), 400
    
    # Simuler un match 50% du temps avec super-like
    is_match = (likes_remaining % 2 == 0)
    
    return jsonify({
        'result': 'match' if is_match else 'superlike_sent',
        'match_id': str(uuid.uuid4()) if is_match else None,
        'daily_likes_remaining': likes_remaining,
        'super_likes_remaining': 2,
        'message': "It's a match!" if is_match else "Super-like envoyé"
    })

@app.route('/api/v1/auth/firebase-exchange/', methods=['POST'])
def firebase_exchange():
    """Échange token Firebase"""
    data = request.get_json()
    firebase_token = data.get('firebase_token')
    
    if not firebase_token:
        return jsonify({'error': 'firebase_token requis'}), 400
    
    return jsonify({
        'access_token': 'test-access-token-123',
        'refresh_token': 'test-refresh-token-456',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'user': {
            'id': '0e5ac2cb-07d8-4160-9f36-90393356f8c0',
            'email': 'marie.claire@test.com',
            'display_name': 'Marie',
            'profile_complete': True
        }
    })

@app.route('/api/v1/health/')
def health():
    """Endpoint de santé"""
    return jsonify({
        'status': 'ok',
        'message': 'Backend de test avec profils',
        'profiles_count': len(TEST_PROFILES),
        'likes_remaining': likes_remaining
    })

@app.route('/admin/')
def admin():
    """Simulation de la page d'admin"""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Backend Test HIVMeet</title></head>
    <body>
        <h1>Backend de Test HIVMeet</h1>
        <p>✅ Backend opérationnel avec profils de test</p>
        <ul>
            <li>Profils disponibles: ''' + str(len(TEST_PROFILES)) + '''</li>
            <li>Likes restants: ''' + str(likes_remaining) + '''</li>
        </ul>
    </body>
    </html>
    '''

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'code': 'NOT_FOUND',
        'message': 'Endpoint non trouvé',
        'detail': f'Aucun endpoint configuré pour: {request.path}'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'code': 'INTERNAL_ERROR',
        'message': 'Erreur interne du serveur',
        'detail': str(error)
    }), 500

if __name__ == '__main__':
    print("🚀 Démarrage backend de test HIVMeet")
    print(f"📊 {len(TEST_PROFILES)} profils de test disponibles")
    print("📍 URL: http://0.0.0.0:8000")
    print("📍 URL Émulateur: http://10.0.2.2:8000")
    print("\n✅ Endpoints disponibles:")
    print("   - GET  /api/v1/discovery/profiles")
    print("   - POST /api/v1/discovery/interactions/like")
    print("   - POST /api/v1/discovery/interactions/dislike")
    print("   - POST /api/v1/discovery/interactions/superlike")
    print("   - POST /api/v1/auth/firebase-exchange/")
    print("   - GET  /api/v1/health/")
    print("   - GET  /admin/")
    print("\n⚠️  IMPORTANT: Ce backend est pour les tests uniquement!")
    print("    Il ne persiste pas les données et réinitialise à chaque démarrage.\n")
    
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)
