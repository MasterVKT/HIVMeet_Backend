from django.db import migrations

# Littéraux volontaires: une migration ne doit pas dépendre de l'évolution du code.
OWNED_GROUPS = ('backoffice_admin', 'backoffice_moderator', 'backoffice_support')


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in OWNED_GROUPS:
        Group.objects.get_or_create(name=name)


def keep_groups(apps, schema_editor):
    # Le retour arrière ne supprime pas les groupes: ils peuvent avoir reçu des
    # membres ou des permissions. Le déprovisionnement relève du runbook.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('backoffice', '0001_initial'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_groups, keep_groups),
    ]
