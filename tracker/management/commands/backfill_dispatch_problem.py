from django.core.management.base import BaseCommand

from tracker.models import DispatchItem
from tracker.services import get_material_lines_for_engineer


class Command(BaseCommand):
    help = (
        'One-off backfill of DispatchItem.problem for items dispatched before '
        'that field existed. Reuses get_material_lines_for_engineer so the '
        'slot-matching rules live in exactly one place. Safe to re-run -- '
        'only touches rows where problem is still blank.'
    )

    def handle(self, *args, **options):
        problem_by_key = {
            (line.service_id, line.part_type, line.faulty_serial): line.problem
            for line in get_material_lines_for_engineer()
            if line.problem
        }

        updated = 0
        for item in DispatchItem.objects.filter(problem=''):
            problem = problem_by_key.get((item.service_id, item.part_type, item.faulty_serial))
            if problem:
                item.problem = problem
                item.save(update_fields=['problem'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Backfilled problem on {updated} dispatch item(s).'))
