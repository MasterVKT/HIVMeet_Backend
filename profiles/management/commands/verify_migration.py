from django.core.management.base import BaseCommand
from profiles.models import Profile


class Command(BaseCommand):
    help = 'Verify genders_sought migration'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n✅ Vérification post-migration:"))
        
        # Vérifier les NULL values
        missing = Profile.objects.filter(genders_sought__isnull=True)
        count_missing = missing.count()
        
        self.stdout.write(f"Profils avec genders_sought=NULL: {count_missing}")
        
        if count_missing > 0:
            for profile in missing:
                self.stdout.write(f"  - {profile.user.email} (gender={profile.gender})")
        
        # Vérifier le total
        all_profiles = Profile.objects.all()
        self.stdout.write(f"\nTotal des profils: {all_profiles.count()}")
        
        # Distribution par genre
        males = Profile.objects.filter(gender='male', genders_sought__isnull=False)
        self.stdout.write(f"\nMâles avec genders_sought valide: {males.count()}")
        
        females = Profile.objects.filter(gender='female', genders_sought__isnull=False)
        self.stdout.write(f"Femelles avec genders_sought valide: {females.count()}")
        
        others = Profile.objects.filter(genders_sought__isnull=False).exclude(gender__in=['male', 'female'])
        self.stdout.write(f"Autres avec genders_sought valide: {others.count()}")
        
        if count_missing == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Migration réussie! Le champ genders_sought est désormais robuste."))
        else:
            self.stdout.write(self.style.ERROR(f"\n❌ {count_missing} profils ont toujours genders_sought=NULL"))
