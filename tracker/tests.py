from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

from tracker.services import get_material_lines_for_engineer


def _ticket(**overrides):
    base = dict(
        service_id='E2680079',
        complaint_reg_date=date(2026, 9, 1),
        engineer_email='eng@example.com',
        engineer_name='Eng',
        machine_no='M1',
        si_name='SI',
        farmer_name='Farmer',
        status='Completed',
        faulty_power_card_no='CARD_SERIAL',
        faulty_control_card_no='CARD_SERIAL',
        controller_display_fault='Dry Run',
        faulty_part_no_1=None,
        faulty_part_no_2='SAME_SERIAL',
        faulty_part_no_3='SAME_SERIAL',
        component_1=None,
        component_2='Submersible Motor',
        component_3='Submersible Pump',
        problem_1=None,
        problem_2='Carbon Plate Damage',
        problem_3='Shaft Damage',
    )
    base.update(overrides)
    ticket = SimpleNamespace(**base)
    ticket.location = 'Loc'
    return ticket


class MaterialLineDedupTests(TestCase):
    def _lines(self):
        chained_queryset = mock.Mock()
        chained_queryset.filter.return_value = [_ticket()]
        with mock.patch('tracker.services.ClappiaData.objects.filter', return_value=chained_queryset):
            return get_material_lines_for_engineer('eng@example.com')

    def test_slots_sharing_a_faulty_serial_both_appear_with_their_own_problem_tag(self):
        """Motor (component_2) and pump (component_3) logged with the same
        (placeholder) faulty_serial must both show up, not collide into one,
        each with the fault reason from its own slot. Power/control card
        share one fault field (controller_display_fault) instead."""
        by_name = {line.material_name: line.problem for line in self._lines()}
        self.assertEqual(by_name, {
            'Power Card': 'Dry Run',
            'Control Card': 'Dry Run',
            'Submersible Motor': 'Carbon Plate Damage',
            'Submersible Pump': 'Shaft Damage',
        })
