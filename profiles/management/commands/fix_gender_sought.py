"""
Django management command to fix missing gender_sought values in profiles.
This is a production-safe, idempotent operation.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from profiles.models import Profile


class Command(BaseCommand):
    help = 'Fix missing or empty gender_sought values in profiles'

    def add_arguments(self, parser):
        """Add optional arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.WARNING('\n' + '=' * 80))
        self.stdout.write(self.style.WARNING('🔧 Fixing gender_sought Values'))
        self.stdout.write(self.style.WARNING('=' * 80))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n⚠️  DRY RUN MODE - No changes will be made\n'))
        
        try:
            # Find profiles with missing or empty gender_sought
            # Note: genders_sought is an ArrayField, NULL or empty list
            missing_query = Q(genders_sought__isnull=True) | Q(genders_sought=[])
            
            # Count by gender
            males = Profile.objects.filter(Q(gender='male') & missing_query)
            females = Profile.objects.filter(Q(gender='female') & missing_query)
            non_binary = Profile.objects.filter(Q(gender='non_binary') & missing_query)
            trans_male = Profile.objects.filter(Q(gender='trans_male') & missing_query)
            trans_female = Profile.objects.filter(Q(gender='trans_female') & missing_query)
            others = Profile.objects.filter(
                Q(gender__in=['other', 'prefer_not_to_say']) & missing_query
            )
            
            male_count = males.count()
            female_count = females.count()
            non_binary_count = non_binary.count()
            trans_male_count = trans_male.count()
            trans_female_count = trans_female.count()
            others_count = others.count()
            
            total_missing = (male_count + female_count + non_binary_count + 
                            trans_male_count + trans_female_count + others_count)
            
            self.stdout.write(f'\n📊 Profiles with missing genders_sought:')
            self.stdout.write(f'   Male:              {male_count}')
            self.stdout.write(f'   Female:            {female_count}')
            self.stdout.write(f'   Non-binary:        {non_binary_count}')
            self.stdout.write(f'   Trans-male:        {trans_male_count}')
            self.stdout.write(f'   Trans-female:      {trans_female_count}')
            self.stdout.write(f'   Other/Prefer:      {others_count}')
            self.stdout.write(f'   ─────────────────────────────')
            self.stdout.write(f'   TOTAL:             {total_missing}')
            
            if total_missing == 0:
                self.stdout.write(self.style.SUCCESS('\n✅ All profiles already have genders_sought defined!\n'))
                return
            
            if not dry_run:
                # Confirm before making changes
                response = input('\n⚠️  This will update the profiles above. Continue? (y/N): ')
                if response.lower() != 'y':
                    self.stdout.write(self.style.WARNING('❌ Operation cancelled\n'))
                    return
            
            self.stdout.write('\n🔄 Applying fixes...\n')
            
            # Fix by gender
            fixes = {
                'male': {
                    'queryset': males,
                    'value': ['female'],
                    'reason': 'Males seek females for mutual compatibility'
                },
                'female': {
                    'queryset': females,
                    'value': ['male'],
                    'reason': 'Females seek males for mutual compatibility'
                },
                'non_binary': {
                    'queryset': non_binary,
                    'value': ['male', 'female', 'non_binary'],
                    'reason': 'Non-binary accept all genders'
                },
                'trans_male': {
                    'queryset': trans_male,
                    'value': ['female'],
                    'reason': 'Trans males typically seek females'
                },
                'trans_female': {
                    'queryset': trans_female,
                    'value': ['male'],
                    'reason': 'Trans females typically seek males'
                },
                'other': {
                    'queryset': others,
                    'value': ['male', 'female', 'non_binary'],
                    'reason': 'Accept all genders'
                },
            }
            
            total_updated = 0
            
            for gender_label, fix_info in fixes.items():
                queryset = fix_info['queryset']
                count = queryset.count()
                
                if count == 0:
                    continue
                
                value = fix_info['value']
                reason = fix_info['reason']
                
                self.stdout.write(
                    f'   {gender_label:15} → {str(value):40} '
                    f'({reason})'
                )
                
                if not dry_run:
                    updated = queryset.update(genders_sought=value)
                    total_updated += updated
                    self.stdout.write(self.style.SUCCESS(f'      ✅ Updated {updated} profiles'))
                else:
                    total_updated += count
                    self.stdout.write(f'      [DRY-RUN] Would update {count} profiles')
            
            # Summary
            self.stdout.write(f'\n' + '=' * 80)
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'[DRY-RUN] Would update {total_updated} profiles total\n'
                ))
                self.stdout.write(self.style.NOTICE(
                    'Run without --dry-run to apply changes\n'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Successfully updated {total_updated} profiles!\n'
                ))
            
            # Verification
            remaining = Profile.objects.filter(missing_query).count()
            if remaining == 0:
                self.stdout.write(self.style.SUCCESS(
                    '✅ All profiles now have genders_sought defined!\n'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  {remaining} profiles still have missing genders_sought\n'
                ))
            
        except Exception as e:
            raise CommandError(f'❌ Error: {str(e)}')
