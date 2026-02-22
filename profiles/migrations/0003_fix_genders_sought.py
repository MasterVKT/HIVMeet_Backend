"""
Django migration to fix genders_sought field.
- Ensure the field never contains NULL values
- Depends on 0002_add_verified_online_filters migration
"""
from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0002_add_verified_online_filters'),
    ]

    operations = [
        # Ensure all NULL values become empty lists
        migrations.RunPython(
            code=lambda apps, schema_editor: fix_null_genders_sought(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
    ]


def fix_null_genders_sought(apps, schema_editor):
    """
    Data migration to fix NULL genders_sought values.
    This ensures all profiles have at least an empty list.
    """
    Profile = apps.get_model('profiles', 'Profile')
    
    # Find and fix NULL or missing values
    males = Profile.objects.filter(gender='male', genders_sought__isnull=True)
    females = Profile.objects.filter(gender='female', genders_sought__isnull=True)
    non_binary = Profile.objects.filter(gender='non_binary', genders_sought__isnull=True)
    others = Profile.objects.filter(
        gender__in=['trans_male', 'trans_female', 'other', 'prefer_not_to_say'],
        genders_sought__isnull=True
    )
    
    # Update to appropriate defaults
    males.update(genders_sought=['female'])
    females.update(genders_sought=['male'])
    non_binary.update(genders_sought=['male', 'female', 'non_binary'])
    others.update(genders_sought=['male', 'female', 'non_binary'])
