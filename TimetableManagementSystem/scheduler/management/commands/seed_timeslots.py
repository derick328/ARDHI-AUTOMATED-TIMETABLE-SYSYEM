"""
Management command: seed_timeslots
Creates the official ARDHI University timeslots.

Slots (2 hours each, 10-minute break between):
  07:00–09:00 | 09:10–11:10 | 11:20–13:20 | 13:30–15:30 | 15:40–17:40 | 17:50–19:50

Friday rule:
  The 11:20–13:20 slot is reserved (Jumu'ah / free period) — NOT created for Friday.

Usage:
    python manage.py seed_timeslots           # add missing only
    python manage.py seed_timeslots --reset   # delete all existing first, then create
"""
from datetime import time
from django.core.management.base import BaseCommand
from scheduler.models import Timeslot

SLOT_TIMES = [
    (time(7,  0), time(9,  0)),
    (time(9, 10), time(11, 10)),
    (time(11, 20), time(13, 20)),   # Friday: skipped
    (time(13, 30), time(15, 30)),
    (time(15, 40), time(17, 40)),
    (time(17, 50), time(19, 50)),
]

FRIDAY_BLOCKED = {(time(11, 20), time(13, 20))}   # free period

DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']


def build_timeslots():
    slots = []
    for day in DAYS:
        for start, end in SLOT_TIMES:
            if day == 'FRI' and (start, end) in FRIDAY_BLOCKED:
                continue   # Friday 11:20-13:20 is free — never schedule here
            slots.append((day, start, end))
    return slots


class Command(BaseCommand):
    help = 'Seed official ARDHI University timeslots (6 slots/day, Friday noon free)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Delete ALL existing timeslots first, then recreate'
        )

    def handle(self, *args, **options):
        if options['reset']:
            deleted, _ = Timeslot.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing timeslots.'))

        slots = build_timeslots()
        created = skipped = 0
        for day, start, end in slots:
            _, was_created = Timeslot.objects.get_or_create(
                day=day, start_time=start, end_time=end
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created} timeslots created, {skipped} already existed.\n'
            f'Total slots per week: {len(slots)} '
            f'(Mon–Thu: 6 each, Fri: 5 — noon slot free)'
        ))
