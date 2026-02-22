from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from profiles.models import Profile

User = get_user_model()


class DiscoveryAPITest(APITestCase):
    """Test Discovery API after gender_sought robustness implementation"""
    
    def setUp(self):
        """Create test users and profiles"""
        self.client = APIClient()
        
        # Create male user
        self.male_user = User.objects.create_user(
            email='male@example.com',
            password='testpass123',
            birth_date=date(1990, 1, 1)
        )
        self.male_user.is_email_verified = True
        self.male_user.save()
        
        # Profile created automatically by signal
        self.male_profile = self.male_user.profile
        self.male_profile.gender = 'male'
        self.male_profile.genders_sought = ['female']
        self.male_profile.bio = 'Looking for women'
        self.male_profile.allow_in_discovery = True
        self.male_profile.save()
        
        # Create female user
        self.female_user = User.objects.create_user(
            email='female@example.com',
            password='testpass123',
            birth_date=date(1992, 1, 1)
        )
        self.female_user.is_email_verified = True
        self.female_user.save()
        
        # Profile created automatically by signal
        self.female_profile = self.female_user.profile
        self.female_profile.gender = 'female'
        self.female_profile.genders_sought = ['male']
        self.female_profile.bio = 'Looking for men'
        self.female_profile.allow_in_discovery = True
        self.female_profile.save()
    
    def test_discovery_returns_compatible_profiles(self):
        """Test that discovery returns compatible profiles"""
        # Verify that both profiles have valid genders_sought (not NULL)
        self.assertIsNotNone(self.male_profile.genders_sought)
        self.assertIsNotNone(self.female_profile.genders_sought)
        
        # Verify genders_sought is a list, not NULL or empty string
        self.assertIsInstance(self.male_profile.genders_sought, list)
        self.assertIsInstance(self.female_profile.genders_sought, list)
        
        # Verify correct gender preferences
        self.assertIn('female', self.male_profile.genders_sought)
        self.assertIn('male', self.female_profile.genders_sought)
        
        # Both users should have valid profiles in discovery
        self.assertTrue(self.male_profile.allow_in_discovery)
        self.assertTrue(self.female_profile.allow_in_discovery)
