"""
Performance and load tests for HIVMeet backend.
File: tests/test_performance.py
"""
import time
import concurrent.futures
from django.test import TransactionTestCase
from django.urls import reverse
from django.db import connection
from django.test.utils import override_settings
from rest_framework.test import APIClient
from tests.base import UserFactory, ProfileFactory
from profiles.models import Profile
from matching.models import Like, Match
import statistics


class DatabasePerformanceTest(TransactionTestCase):
    """Test database query performance."""
    
    def setUp(self):
        """Create test data."""
        # Create 1000 users with profiles
        self.users = []
        for i in range(1000):
            user = UserFactory()
            ProfileFactory(
                user=user,
                latitude=48.8566 + (i % 10) * 0.01,
                longitude=2.3522 + (i % 10) * 0.01
            )
            self.users.append(user)
    
    def test_discovery_query_performance(self):
        """Test performance of discovery queries."""
        user = self.users[0]
        
        # Warm up
        list(Profile.objects.filter(
            user__is_active=True,
            is_hidden=False,
            allow_profile_in_discovery=True
        ).exclude(user=user)[:20])
        
        # Measure query time
        with self.assertNumQueries(2):  # One for profiles, one for photos
            start_time = time.time()
            
            profiles = list(Profile.objects.filter(
                user__is_active=True,
                is_hidden=False,
                allow_profile_in_discovery=True
            ).exclude(
                user=user
            ).select_related(
                'user'
            ).prefetch_related(
                'photos'
            ).order_by(
                '-user__last_login'
            )[:20])
            
            end_time = time.time()
            query_time = end_time - start_time
            
        self.assertLess(query_time, 0.1, f"Query took {query_time:.3f}s, should be < 0.1s")
        self.assertEqual(len(profiles), 20)
    
    def test_match_query_performance(self):
        """Test performance of match queries."""
        user = self.users[0]
        
        # Create 100 matches
        for i in range(100):
            match = Match.objects.create()
            match.users.add(user, self.users[i + 1])
        
        # Measure query time
        with self.assertNumQueries(3):  # Matches, users, profiles
            start_time = time.time()
            
            matches = list(Match.objects.filter(
                users=user,
                is_active=True
            ).prefetch_related(
                'users__profile'
            ).order_by(
                '-created_at'
            )[:20])
            
            end_time = time.time()
            query_time = end_time - start_time
        
        self.assertLess(query_time, 0.05, f"Query took {query_time:.3f}s, should be < 0.05s")
        self.assertEqual(len(matches), 20)
    
    def test_location_based_query_performance(self):
        """Test performance of location-based queries."""
        user = self.users[0]
        profile = user.profile
        
        # Test distance calculation query
        start_time = time.time()
        
        # Using PostgreSQL earthdistance extension
        nearby_profiles = Profile.objects.raw('''
            SELECT *, earth_distance(
                ll_to_earth(%s, %s),
                ll_to_earth(latitude, longitude)
            ) as distance
            FROM profiles_profile
            WHERE earth_box(ll_to_earth(%s, %s), %s) @> ll_to_earth(latitude, longitude)
            AND user_id != %s
            ORDER BY distance
            LIMIT 50
        ''', [
            profile.latitude, profile.longitude,
            profile.latitude, profile.longitude,
            50000,  # 50km in meters
            user.id
        ])
        
        results = list(nearby_profiles)
        end_time = time.time()
        query_time = end_time - start_time
        
        self.assertLess(query_time, 0.2, f"Location query took {query_time:.3f}s, should be < 0.2s")
        self.assertGreater(len(results), 0)


class APILoadTest(TransactionTestCase):
    """Load testing for API endpoints."""
    
    def setUp(self):
        """Create test users and data."""
        self.users = []
        self.clients = []
        
        # Create 50 test users
        for i in range(50):
            user = UserFactory(email=f'user{i}@test.com')
            ProfileFactory(user=user)
            
            client = APIClient()
            client.force_authenticate(user=user)
            
            self.users.append(user)
            self.clients.append(client)
    
    def test_concurrent_discovery_requests(self):
        """Test concurrent discovery endpoint requests."""
        url = reverse('discovery:recommended-profiles')
        response_times = []
        
        def make_request(client):
            start = time.time()
            response = client.get(url)
            end = time.time()
            return end - start, response.status_code
        
        # Make 50 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, client) for client in self.clients[:50]]
            
            for future in concurrent.futures.as_completed(futures):
                response_time, status_code = future.result()
                self.assertEqual(status_code, 200)
                response_times.append(response_time)
        
        # Analyze response times
        avg_time = statistics.mean(response_times)
        max_time = max(response_times)
        p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        
        self.assertLess(avg_time, 0.5, f"Average response time {avg_time:.3f}s should be < 0.5s")
        self.assertLess(p95_time, 1.0, f"95th percentile {p95_time:.3f}s should be < 1.0s")
        self.assertLess(max_time, 2.0, f"Max response time {max_time:.3f}s should be < 2.0s")
    
    def test_concurrent_messaging_requests(self):
        """Test concurrent messaging requests."""
        # Create conversations between users
        from messaging.models import Conversation
        conversations = []
        
        for i in range(25):
            conv = Conversation.objects.create()
            conv.participants.add(self.users[i], self.users[i + 25])
            conversations.append(conv)
        
        response_times = []
        
        def send_message(client, conversation_id):
            start = time.time()
            response = client.post(
                reverse('messaging:send-message', kwargs={'conversation_id': conversation_id}),
                {'content': 'Test message'}
            )
            end = time.time()
            return end - start, response.status_code
        
        # Send 50 concurrent messages
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(50):
                client = self.clients[i % 50]
                conv = conversations[i % 25]
                futures.append(executor.submit(send_message, client, str(conv.id)))
            
            for future in concurrent.futures.as_completed(futures):
                response_time, status_code = future.result()
                self.assertIn(status_code, [201, 403])  # 403 if not participant
                if status_code == 201:
                    response_times.append(response_time)
        
        # Analyze successful response times
        if response_times:
            avg_time = statistics.mean(response_times)
            self.assertLess(avg_time, 0.3, f"Average message send time {avg_time:.3f}s should be < 0.3s")


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
})
class CachePerformanceTest(TransactionTestCase):
    """Test cache performance."""
    
    def setUp(self):
        """Set up cache tests."""
        from django.core.cache import cache
        self.cache = cache
        self.cache.clear()
        
        # Create test data
        self.users = [UserFactory() for _ in range(100)]
        for user in self.users:
            ProfileFactory(user=user)
    
    def test_premium_status_cache_performance(self):
        """Test premium status caching performance."""
        from subscriptions.utils import is_premium_user
        
        user = self.users[0]
        
        # First call (cache miss)
        start = time.time()
        result1 = is_premium_user(user)
        time_uncached = time.time() - start
        
        # Second call (cache hit)
        start = time.time()
        result2 = is_premium_user(user)
        time_cached = time.time() - start
        
        self.assertEqual(result1, result2)
        self.assertLess(time_cached, time_uncached * 0.1, 
                       f"Cached call should be at least 10x faster: {time_cached:.4f}s vs {time_uncached:.4f}s")
    
    def test_discovery_cache_performance(self):
        """Test discovery results caching."""
        user = self.users[0]
        cache_key = f'discovery:{user.id}:1'
        
        # Generate discovery results
        profiles = list(Profile.objects.exclude(
            user=user
        ).select_related('user')[:20])
        
        # Cache write
        start = time.time()
        self.cache.set(cache_key, profiles, 300)
        write_time = time.time() - start
        
        # Cache read
        start = time.time()
        cached_profiles = self.cache.get(cache_key)
        read_time = time.time() - start
        
        self.assertIsNotNone(cached_profiles)
        self.assertEqual(len(cached_profiles), len(profiles))
        self.assertLess(write_time, 0.01, f"Cache write took {write_time:.4f}s")
        self.assertLess(read_time, 0.005, f"Cache read took {read_time:.4f}s")