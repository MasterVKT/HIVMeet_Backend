from django.db import migrations


def normalize_single_choice_sought_gender(apps, schema_editor):
    Profile = apps.get_model('profiles', 'Profile')
    valid = {'male', 'female'}
    for profile in Profile.objects.all().iterator():
        selected = []
        for value in profile.genders_sought or []:
            if value in valid and value not in selected:
                selected.append(value)
        # The old two-value representation means "everyone" in the new
        # single-choice catalogue, preserving broad discovery intent.
        normalized = selected if len(selected) == 1 else []
        if normalized != (profile.genders_sought or []):
            profile.genders_sought = normalized
            profile.save(update_fields=['genders_sought'])


class Migration(migrations.Migration):
    dependencies = [('profiles', '0008_phase4_registration_gender_catalog')]

    operations = [
        migrations.RunPython(normalize_single_choice_sought_gender, migrations.RunPython.noop),
    ]
