"""
Base test classes and utilities for HIVMeet.
File: tests/base.py
"""
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from faker import Faker
import factory
from datetime import timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
import io

User = get_user_model()
fake = Faker()


class BaseTestCase(TestCase):
    """Base test case with common utilities."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the whole TestCase."""
        super().setUpTestData()
        cls.faker = Faker()
    
    def create_user(self, **kwargs):
        """Create a test user."""
        defaults = {
            'email': self.faker.email(),
            'display_name': self.faker.name(),
            'password': 'testpass123',
            'birth_date': self.faker.date_of_birth(minimum_age=18, maximum_age=80),
            'is_email_verified': True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)
    
    def create_premium_user(self, **kwargs):
        """Create a premium test user."""
        kwargs['is_premium'] = True
        kwargs['premium_until'] = timezone.now() + timedelta(days=30)
        return self.create_user(**kwargs)
    
    def create_image_file(self, name='test.jpg', size=(100, 100)):
        """Create a test image file."""
        file = io.BytesIO()
        image = Image.new('RGB', size)
        image.save(file, 'JPEG')
        file.seek(0)
        return SimpleUploadedFile(name, file.getvalue(), content_type='image/jpeg')


class APIBaseTestCase(APITestCase):
    """Base API test case with authentication utilities."""
    
    def setUp(self):
        """Set up API test case."""
        super().setUp()
        self.faker = Faker()
        self.client = APIClient()
    
    def create_user(self, **kwargs):
        """Create a test user."""
        defaults = {
            'email': self.faker.email(),
            'display_name': self.faker.name(),
            'password': 'testpass123',
            'birth_date': self.faker.date_of_birth(minimum_age=18, maximum_age=80),
            'is_email_verified': True,
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)
    
    def authenticate(self, user=None):
        """Authenticate the test client."""
        if not user:
            user = self.create_user()
        
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return user
    
    def create_authenticated_user(self, **kwargs):
        """Create and authenticate a user."""
        user = self.create_user(**kwargs)
        self.authenticate(user)
        return user


class TransactionalTestCase(TransactionTestCase):
    """Base transactional test case for tests requiring transactions."""
    
    def setUp(self):
        """Set up transactional test case."""
        super().setUp()
        self.faker = Faker()


# Factory classes for generating test data
class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    email = factory.Faker('email')
    display_name = factory.Faker('name')
    birth_date = factory.Faker('date_of_birth', minimum_age=18, maximum_age=80)
    is_email_verified = True
    is_active = True
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if create and extracted:
            obj.set_password(extracted)
        else:
            obj.set_password('testpass123')


class ProfileFactory(factory.django.DjangoModelFactory):
    """Factory for creating Profile instances."""
    
    class Meta:
        model = 'profiles.Profile'
    
    user = factory.SubFactory(UserFactory)
    bio = factory.Faker('text', max_nb_chars=500)
    gender = factory.Faker('random_element', elements=['male', 'female', 'non_binary'])
    interests = factory.List([factory.Faker('word') for _ in range(5)])
    city = factory.Faker('city')
    country = factory.Faker('country')
    latitude = factory.Faker('latitude')
    longitude = factory.Faker('longitude')


class SubscriptionPlanFactory(factory.django.DjangoModelFactory):
    """Factory for creating SubscriptionPlan instances."""
    
    class Meta:
        model = 'subscriptions.SubscriptionPlan'
    
    plan_id = factory.Sequence(lambda n: f'test_plan_{n}')
    name = factory.Faker('sentence', nb_words=3)
    name_en = factory.Faker('sentence', nb_words=3)
    name_fr = factory.Faker('sentence', nb_words=3)
    description = factory.Faker('text')
    description_en = factory.Faker('text')
    description_fr = factory.Faker('text')
    price = factory.Faker('pydecimal', left_digits=2, right_digits=2, positive=True)
    currency = 'EUR'
    billing_interval = factory.Faker('random_element', elements=['month', 'year'])
    is_active = True


class SubscriptionFactory(factory.django.DjangoModelFactory):
    """Factory for creating Subscription instances."""
    
    class Meta:
        model = 'subscriptions.Subscription'
    
    subscription_id = factory.Faker('uuid4')
    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(SubscriptionPlanFactory)
    status = 'active'
    current_period_start = factory.LazyFunction(timezone.now)
    current_period_end = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))


class ConversationFactory(factory.django.DjangoModelFactory):
    """Factory for creating Conversation instances."""
    
    class Meta:
        model = 'messaging.Conversation'
    
    @factory.post_generation
    def participants(self, create, extracted, **kwargs):
        if create and extracted:
            for participant in extracted:
                self.participants.add(participant)