"""
Management command: seed_timeslots
Creates default university timeslots for ARDHI University.

Mon–Thu: 08:00–10:00, 10:00–12:00, 13:00–15:00, 15:00–17:00
Fri:     08:00–10:00, 10:00–12:00 (Friday afternoon restricted)

Usage:
    python manage.py seed_timeslots
"""
from datetime import time
from django.core.management.base import BaseCommand
from scheduler.models import Timeslot


TIMESLOTS = [
    # Monday
    ('MON', time(8, 0), time(10, 0)),
    ('MON', time(10, 0), time(12, 0)),
    ('MON', time(13, 0), time(15, 0)),
    ('MON', time(15, 0), time(17, 0)),
    # Tuesday
    ('TUE', time(8, 0), time(10, 0)),
    ('TUE', time(10, 0), time(12, 0)),
    ('TUE', time(13, 0), time(15, 0)),
    ('TUE', time(15, 0), time(17, 0)),
    # Wednesday
    ('WED', time(8, 0), time(10, 0)),
    ('WED', time(10, 0), time(12, 0)),
    ('WED', time(13, 0), time(15, 0)),
    ('WED', time(15, 0), time(17, 0)),
    # Thursday
    ('THU', time(8, 0), time(10, 0)),
    ('THU', time(10, 0), time(12, 0)),
    ('THU', time(13, 0), time(15, 0)),
    ('THU', time(15, 0), time(17, 0)),
    # Friday (afternoon restricted — only morning slots)
    ('FRI', time(8, 0), time(10, 0)),
    ('FRI', time(10, 0), time(12, 0)),
]


class Command(BaseCommand):
    help = 'Seed default timeslots for ARDHI University'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for day, start, end in TIMESLOTS:
            _, was_created = Timeslot.objects.get_or_create(
                day=day, start_time=start, end_time=end
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {created} timeslots created, {skipped} already existed.'
            )
        )
