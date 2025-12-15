"""
Django management command to load event categories
Run with: python manage.py load_categories
"""

from django.core.management.base import BaseCommand
from tickets.models import EventCategory


class Command(BaseCommand):
    help = 'Load event categories into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing categories before loading',
        )

    def handle(self, *args, **options):
        # Define categories
        categories = [
            {
                "name": "Music",
                "slug": "music",
                "description": "Musical events and concerts",
                "icon": "FaMusic"
            },
            {
                "name": "Sports",
                "slug": "sports",
                "description": "Sports matches and tournaments",
                "icon": "FaFootballBall"
            },
            {
                "name": "Arts & Culture",
                "slug": "arts-culture",
                "description": "Art exhibitions, galleries, and cultural events",
                "icon": "FaPaintBrush"
            },
            {
                "name": "Business & Networking",
                "slug": "business-networking",
                "description": "Professional networking events and conferences",
                "icon": "FaBriefcase"
            },
            {
                "name": "Food & Drink",
                "slug": "food-drink",
                "description": "Food festivals, wine tastings, and culinary events",
                "icon": "FaUtensils"
            },
            {
                "name": "Comedy",
                "slug": "comedy",
                "description": "Stand-up comedy shows and comedy nights",
                "icon": "FaLaugh"
            },
            {
                "name": "Education & Training",
                "slug": "education-training",
                "description": "Workshops, seminars, and training sessions",
                "icon": "FaGraduationCap"
            },
            {
                "name": "Other",
                "slug": "other",
                "description": "Other events and activities",
                "icon": "FaCalendarAlt"
            }
        ]

        # Clear existing categories if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing categories...'))
            EventCategory.objects.all().delete()

        # Create categories
        self.stdout.write(self.style.SUCCESS('Creating categories...'))
        created_count = 0
        updated_count = 0

        for cat_data in categories:
            category, created = EventCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {category.name}'))
            else:
                # Update existing category
                for key, value in cat_data.items():
                    setattr(category, key, value)
                category.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'- Updated: {category.name}'))

        total = EventCategory.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\n✅ Done!'))
        self.stdout.write(f'   Created: {created_count}')
        self.stdout.write(f'   Updated: {updated_count}')
        self.stdout.write(f'   Total categories: {total}')