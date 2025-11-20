"""
Health check system for HIVMeet Backend.
"""
import time
from datetime import datetime
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger('hivmeet.health')

class HealthCheckService:
    """Service pour vérifier l'état de santé de l'application."""
    
    @staticmethod
    def check_database():
        """Vérifie la connexion à la base de données."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True, "Database OK"
        except Exception as e:
            return False, f"Database Error: {str(e)}"
    
    @staticmethod
    def check_cache():
        """Vérifie la connexion au cache Redis."""
        try:
            cache_key = 'health_check_test'
            test_value = f'test_{int(time.time())}'
            
            cache.set(cache_key, test_value, 30)
            retrieved_value = cache.get(cache_key)
            
            if retrieved_value == test_value:
                cache.delete(cache_key)
                return True, "Cache OK"
            else:
                return False, "Cache value mismatch"
                
        except Exception as e:
            return False, f"Cache Error: {str(e)}"
    
    @staticmethod
    def check_firebase():
        """Vérifie la connexion Firebase."""
        try:
            from hivmeet_backend.firebase_service import firebase_service
            
            # Test d'accès aux services
            auth_service = firebase_service.auth
            db_service = firebase_service.db
            bucket_service = firebase_service.bucket
            
            # Test simple d'accès à Firestore
            test_collection = db_service.collection('health_check')
            
            return True, "Firebase OK"
            
        except Exception as e:
            return False, f"Firebase Error: {str(e)}"
    
    @staticmethod
    def check_static_files():
        """Vérifie l'accès aux fichiers statiques."""
        try:
            from django.contrib.staticfiles.finders import find
            # Chercher un fichier statique de base
            static_file = find('admin/css/base.css')
            if static_file:
                return True, "Static files OK"
            else:
                return False, "Static files not found"
        except Exception as e:
            return False, f"Static files Error: {str(e)}"
    
    @staticmethod
    def check_celery():
        """Vérifie l'état de Celery."""
        try:
            from celery import current_app
            
            # Vérifier la connexion au broker
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                active_workers = len(stats)
                return True, f"Celery OK ({active_workers} workers)"
            else:
                return False, "No Celery workers available"
                
        except Exception as e:
            return False, f"Celery Error: {str(e)}"
    
    @classmethod
    def get_comprehensive_health(cls):
        """Retourne un état de santé complet de l'application."""
        checks = {
            'database': cls.check_database(),
            'cache': cls.check_cache(),
            'firebase': cls.check_firebase(),
            'static_files': cls.check_static_files(),
            'celery': cls.check_celery(),
        }
        
        # Calcul du statut global
        all_healthy = all(check[0] for check in checks.values())
        
        # Informations système
        system_info = {
            'timestamp': datetime.now().isoformat(),
            'debug': settings.DEBUG,
            'version': getattr(settings, 'APP_VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
        }
        
        return {
            'status': 'healthy' if all_healthy else 'unhealthy',
            'checks': {
                name: {
                    'status': 'pass' if status else 'fail',
                    'message': message
                }
                for name, (status, message) in checks.items()
            },
            'system': system_info
        }

def health_check_view(request):
    """Vue pour le health check HTTP."""
    health_data = HealthCheckService.get_comprehensive_health()
    
    # Status code basé sur l'état de santé
    status_code = 200 if health_data['status'] == 'healthy' else 503
    
    # Log des problèmes de santé
    if health_data['status'] != 'healthy':
        failed_checks = [
            name for name, check in health_data['checks'].items()
            if check['status'] == 'fail'
        ]
        logger.warning(f"Health check failed: {', '.join(failed_checks)}")
    
    return JsonResponse(health_data, status=status_code)

def simple_health_check_view(request):
    """Vue simple pour le health check (juste DB)."""
    try:
        db_ok, db_message = HealthCheckService.check_database()
        
        if db_ok:
            return JsonResponse({
                'status': 'healthy',
                'message': 'Service operational',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return JsonResponse({
                'status': 'unhealthy',
                'message': db_message,
                'timestamp': datetime.now().isoformat()
            }, status=503)
            
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'message': f'Health check error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=503)

def readiness_check_view(request):
    """Vue pour vérifier si l'application est prête à recevoir du trafic."""
    # Vérifications critiques pour la readiness
    critical_checks = {
        'database': HealthCheckService.check_database(),
        'cache': HealthCheckService.check_cache(),
    }
    
    all_ready = all(check[0] for check in critical_checks.values())
    
    response_data = {
        'ready': all_ready,
        'checks': {
            name: {
                'status': 'pass' if status else 'fail',
                'message': message
            }
            for name, (status, message) in critical_checks.items()
        },
        'timestamp': datetime.now().isoformat()
    }
    
    status_code = 200 if all_ready else 503
    return JsonResponse(response_data, status=status_code)

def metrics_view(request):
    """Vue pour exposer des métriques basiques."""
    try:
        from django.contrib.auth import get_user_model
        from matching.models import Match
        from messaging.models import Message
        from subscriptions.models import Subscription
        
        User = get_user_model()
        
        # Métriques de base
        metrics = {
            'users': {
                'total': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'premium': User.objects.filter(is_premium=True).count(),
            },
            'matches': {
                'total': Match.objects.count(),
                'today': Match.objects.filter(
                    created_at__date=datetime.now().date()
                ).count(),
            },
            'messages': {
                'total': Message.objects.count(),
                'today': Message.objects.filter(
                    created_at__date=datetime.now().date()
                ).count(),
            },
            'subscriptions': {
                'active': Subscription.objects.filter(
                    is_active=True
                ).count(),
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return JsonResponse(metrics)
        
    except Exception as e:
        return JsonResponse({
            'error': f'Metrics error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=500) 