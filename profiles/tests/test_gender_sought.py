"""
Tests for profile gender_sought field validation and completeness.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import date
from profiles.models import Profile

User = get_user_model()


class ProfileGenderSoughtTest(TestCase):
    """Test that all profiles have genders_sought properly defined."""
    
    def setUp(self):
        """Create test users and profiles."""
        self.user = User.objects.create_user(
            email='test@test.com',
            password='testpass123',
            display_name='Test User',
            birth_date=date(1990, 1, 1)
        )
        self.profile = self.user.profile
    
    def test_profile_genders_sought_default_list(self):
        """Test that genders_sought defaults to empty list, not NULL."""
        new_user = User.objects.create_user(
            email='newuser@test.com',
            password='testpass123',
            display_name='New User',
            birth_date=date(1995, 1, 1)
        )
        self.assertIsNotNone(new_user.profile.genders_sought)
        self.assertEqual(new_user.profile.genders_sought, [])
    
    def test_profile_genders_sought_never_null(self):
        """Test that genders_sought is never NULL in the database."""
        from django.db.models import Q
        
        null_count = Profile.objects.filter(
            Q(genders_sought__isnull=True)
        ).count()
        self.assertEqual(null_count, 0, "No profiles should have NULL genders_sought")
    
    def test_profile_genders_sought_never_empty_string(self):
        """Test that genders_sought is never an empty string."""
        invalid_count = Profile.objects.filter(
            genders_sought=['']  # Check for empty string in list
        ).count()
        self.assertEqual(invalid_count, 0, "No profiles should have empty strings in genders_sought")
    
    def test_profile_clean_prevents_null_genders_sought(self):
        """Test that clean() prevents NULL genders_sought."""
        self.profile.genders_sought = None
        self.profile.clean()  # Should not raise, should set to []
        self.assertEqual(self.profile.genders_sought, [])
    
    def test_profile_save_calls_clean(self):
        """Test that save() calls clean() which enforces validation."""
        self.profile.genders_sought = None
        self.profile.save()  # Should not raise
        
        # Verify it was saved as empty list
        refreshed = Profile.objects.get(pk=self.profile.pk)
        self.assertEqual(refreshed.genders_sought, [])
    
    def test_profile_male_with_valid_genders_sought(self):
        """Test that male profiles with genders_sought=['female'] validate."""
        self.profile.gender = 'male'
        self.profile.genders_sought = ['female']
        self.profile.clean()  # Should not raise
        self.profile.save()  # Should not raise
        
        refreshed = Profile.objects.get(pk=self.profile.pk)
        self.assertEqual(refreshed.genders_sought, ['female'])
    
    def test_profile_invalid_gender_in_genders_sought_raises_error(self):
        """Test that invalid gender choices raise ValidationError."""
        self.profile.genders_sought = ['invalid_gender']
        with self.assertRaises(ValidationError):
            self.profile.clean()
    
    def test_profile_multiple_genders_sought_valid(self):
        """Test that profiles can seek multiple genders."""
        self.profile.genders_sought = ['male', 'female', 'non_binary']
        self.profile.clean()  # Should not raise
        self.profile.save()  # Should not raise
        
        refreshed = Profile.objects.get(pk=self.profile.pk)
        self.assertEqual(len(refreshed.genders_sought), 3)
    
    def test_no_profiles_missing_genders_sought(self):
        """Test that no existing profiles have missing genders_sought."""
        # This test verifies data integrity
        from django.db.models import Q
        
        missing = Profile.objects.filter(
            Q(genders_sought__isnull=True) | Q(genders_sought=[])
        )
        
        # Empty list is OK (means "all genders"), NULL is not
        null_only = Profile.objects.filter(genders_sought__isnull=True)
        self.assertEqual(null_only.count(), 0, 
            "No profiles should have NULL genders_sought. "
            "Run: python manage.py fix_gender_sought")
    
    def test_empty_genders_sought_is_valid(self):
        """Test that empty list for genders_sought is a valid, deliberate choice."""
        self.profile.genders_sought = []
        self.profile.clean()  # Should not raise
        self.profile.save()  # Should not raise
        
        refreshed = Profile.objects.get(pk=self.profile.pk)
        self.assertEqual(refreshed.genders_sought, [])
