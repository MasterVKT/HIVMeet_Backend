"""
Management command to populate sample resources.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from resources.models import Category, Resource
import json


class Command(BaseCommand):
    help = 'Populate database with sample resources'

    def handle(self, *args, **options):
        # Create categories
        categories = [
            {
                'name': 'Information générale',
                'name_en': 'General Information',
                'name_fr': 'Information générale',
                'description_en': 'General information about HIV/AIDS',
                'description_fr': 'Informations générales sur le VIH/SIDA',
            },
            {
                'name': 'Santé et bien-être',
                'name_en': 'Health & Wellness',
                'name_fr': 'Santé et bien-être',
                'description_en': 'Health and wellness resources',
                'description_fr': 'Ressources de santé et bien-être',
            },
            {
                'name': 'Support et communauté',
                'name_en': 'Support & Community',
                'name_fr': 'Support et communauté',
                'description_en': 'Support groups and community resources',
                'description_fr': 'Groupes de soutien et ressources communautaires',
            },
            {
                'name': 'Droits et législation',
                'name_en': 'Rights & Legislation',
                'name_fr': 'Droits et législation',
                'description_en': 'Legal rights and legislation',
                'description_fr': 'Droits légaux et législation',
            },
        ]

        created_categories = {}
        for cat_data in categories:
            cat, created = Category.objects.get_or_create(
                slug=slugify(cat_data['name_en']),
                defaults=cat_data
            )
            created_categories[cat_data['name_en']] = cat
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {cat.name}'))

        # Create sample resources
        resources = [
            {
                'title': 'Comprendre le VIH/SIDA',
                'title_en': 'Understanding HIV/AIDS',
                'title_fr': 'Comprendre le VIH/SIDA',
                'resource_type': Resource.ARTICLE,
                'category': created_categories['General Information'],
                'summary_en': 'Basic information about HIV/AIDS',
                'summary_fr': 'Informations de base sur le VIH/SIDA',
                'content_en': 'HIV (Human Immunodeficiency Virus) is a virus that attacks the immune system...',
                'content_fr': 'Le VIH (Virus de l\'Immunodéficience Humaine) est un virus qui attaque le système immunitaire...',
                'is_published': True,
                'is_verified_expert': True,
                'tags': ['HIV', 'AIDS', 'basics', 'information'],
            },
            {
                'title': 'Vivre positivement avec le VIH',
                'title_en': 'Living Positively with HIV',
                'title_fr': 'Vivre positivement avec le VIH',
                'resource_type': Resource.ARTICLE,
                'category': created_categories['Health & Wellness'],
                'summary_en': 'Tips for maintaining health and wellness while living with HIV',
                'summary_fr': 'Conseils pour maintenir sa santé et son bien-être en vivant avec le VIH',
                'is_published': True,
                'tags': ['wellness', 'health', 'lifestyle'],
            },
            {
                'title': 'Groupes de support locaux',
                'title_en': 'Local Support Groups',
                'title_fr': 'Groupes de support locaux',
                'resource_type': Resource.CONTACT,
                'category': created_categories['Support & Community'],
                'summary_en': 'Find local HIV support groups in your area',
                'summary_fr': 'Trouvez des groupes de soutien VIH dans votre région',
                'is_published': True,
                'contact_info': {
                    'phone': '+1-800-HIV-INFO',
                    'email': 'support@hivinfo.org',
                    'website': 'https://www.hivinfo.org'
                },
                'tags': ['support', 'community', 'groups'],
            },
        ]

        for res_data in resources:
            res, created = Resource.objects.get_or_create(
                slug=slugify(res_data['title_en']),
                defaults=res_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created resource: {res.title}'))

        self.stdout.write(self.style.SUCCESS('Successfully populated resources'))