from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0005_accountdeletionrequest_dataexportrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='preferred_currency',
            field=models.CharField(
                choices=[
                    ('AUTO', 'Automatic'),
                    ('XAF', 'Central African CFA franc'),
                    ('EUR', 'Euro'),
                ],
                default='AUTO',
                max_length=4,
                verbose_name='Preferred payment currency',
            ),
        ),
    ]
