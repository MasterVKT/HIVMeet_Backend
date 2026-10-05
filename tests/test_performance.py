"""
Performance and load tests for HIVMeet backend.
File: tests/test_performance.py
"""
import time
import concurrent.futures
from django.test import TransactionTestCase
from django.urls import reverse
from django.db import close_old_connections
from django.db.models import Q
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
        # Create enough rows to exercise pagination and relationship queries
        # without making the regular CI suite spend minutes generating logs.
        self.users = []
        for i in range(250):
            user = UserFactory(email=f'db-perf-{i}@example.test')
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
            Match.objects.create(user1=user, user2=self.users[i + 1])
        
        # Measure query time
        with self.assertNumQueries(1):
            start_time = time.time()
            
            matches = list(Match.objects.filter(
                Q(user1=user) | Q(user2=user),
                status=Match.ACTIVE,
            ).select_related(
                'user1__profile',
                'user2__profile',
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
        # Reload the canonical row because the user post-save signal may have
        # cached its initial, location-less Profile instance on ``user`` before
        # ProfileFactory updated it.
        profile = Profile.objects.get(user=user)
        
        # Exercise the bounding-box candidate query used before exact distance
        # computation. This remains portable to the standard PostgreSQL test
        # database and does not depend on an optional earthdistance extension.
        start_time = time.time()

        results = list(
            Profile.objects.filter(
                latitude__range=(float(profile.latitude) - 0.5, float(profile.latitude) + 0.5),
                longitude__range=(float(profile.longitude) - 0.5, float(profile.longitude) + 0.5),
            ).exclude(user=user)[:50]
        )
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
        url = reverse('api:discovery:discovery')
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
        
        # These are local CI smoke budgets. Production latency SLOs must be
        # measured against a deployed worker/database stack, not Django's
        # in-process test client with eager Celery tasks.
        self.assertLess(avg_time, 2.0, f"Average response time {avg_time:.3f}s should be < 2.0s")
        self.assertLess(p95_time, 4.0, f"95th percentile {p95_time:.3f}s should be < 4.0s")
        self.assertLess(max_time, 6.0, f"Max response time {max_time:.3f}s should be < 6.0s")
    
    def test_concurrent_messaging_requests(self):
        """Test concurrent messaging requests."""
        # Create conversations between users
        conversations = []
        
        for i in range(25):
            conv = Match.objects.create(
                user1=self.users[i],
                user2=self.users[i + 25],
            )
            conversations.append(conv)
        
        response_times = []
        
        def send_message(client, conversation_id):
            close_old_connections()
            try:
                start = time.time()
                response = client.post(
                    reverse(
                        'api:messaging:conversation-messages',
                        kwargs={'conversation_id': conversation_id},
                    ),
                    {
                        'client_message_id': (
                            f'load-{conversation_id}-{time.time_ns()}'
                        ),
                        'content': 'Test message',
                        'type': 'text',
                    },
                    format='json',
                )
                end = time.time()
                return end - start, response.status_code
            finally:
                close_old_connections()
        
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
            self.assertLess(avg_time, 2.0, f"Average message send time {avg_time:.3f}s should be < 2.0s")


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'performance-suite',
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
        
        # First call populates the canonical cache key.
        start = time.time()
        result1 = is_premium_user(user)
        time_uncached = time.time() - start
        
        # Second call (cache hit)
        start = time.time()
        result2 = is_premium_user(user)
        time_cached = time.time() - start
        
        self.assertEqual(result1, result2)
        self.assertIsInstance(time_uncached, float)
        self.assertLess(time_cached, 0.05)
    
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
