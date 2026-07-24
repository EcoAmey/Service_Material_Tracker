from dataclasses import dataclass
from datetime import date, datetime

from .models import ClappiaData, DispatchItem, DispatchItemStatusEvent

# ez_service holds records going back to 2019 (lakhs of rows) -- only
# tickets registered on or after this date are considered. Rows with no
# complaint_reg_date at all are legacy data from before this field existed
# and are excluded too.
DATA_CUTOFF_DATE = date(2026, 7, 19)

# (part_type key, faulty-serial column, display label, name source)
# name source is None for Power Card / Control Card, which have no
# ticket-provided name of their own -- the label is used as-is. Generic
# "material" slots (up to 3 per visit) each have their own component field.
PART_TYPES = [
    ('power_card', 'faulty_power_card_no', 'Power Card', None),
    ('control_card', 'faulty_control_card_no', 'Control Card', None),
    ('material', 'faulty_part_no_1', 'Material', 'component_1'),
    ('material', 'faulty_part_no_2', 'Material', 'component_2'),
    ('material', 'faulty_part_no_3', 'Material', 'component_3'),
]

# Generic "material" entries whose name suggests a motor or pump follow a
# different repair workflow (repair/OEM) than cards/RMU (tested OK/dispatch).
MOTOR_PUMP_KEYWORDS = ('motor', 'pump')

# The source data uses '-1' (as well as blank/None) as a sentinel for
# "not applicable" in these free-text fields -- e.g. an unused replacement
# slot's component/faulty-part columns.
BLANK_SENTINELS = {'', '-1'}


def _clean(value):
    if value is None:
        return None
    value = value.strip()
    return value if value not in BLANK_SENTINELS else None


def is_motor_or_pump(part_type, material_name):
    if part_type != 'material':
        return False
    name = (material_name or '').lower()
    return any(keyword in name for keyword in MOTOR_PUMP_KEYWORDS)


@dataclass
class MaterialLine:
    """One dispatchable material, unpivoted from a clappia_data row."""

    service_id: str
    part_type: str
    part_type_label: str
    material_name: str
    faulty_serial: str
    controller_serial: str
    si_details: str
    farmer_name: str
    location: str
    service_person_name: str
    replacement_date: datetime
    is_dispatched: bool

    @property
    def key(self):
        return f'{self.service_id}|{self.part_type}|{self.faulty_serial}'


def get_material_lines_for_engineer(email):
    """Every material an engineer has replaced, one row per replaced part.

    A single completed visit can have a Power card, a Control card, and up
    to 3 generic materials all replaced at once -- each becomes its own
    line. Only completed visits registered on/after DATA_CUTOFF_DATE are
    considered; the source table also holds in-progress ones, and years of
    older data before the cutoff.
    """
    tickets = ClappiaData.objects.filter(
        engineer_email__iexact=email, status__iexact='completed', complaint_reg_date__gte=DATA_CUTOFF_DATE
    )
    dispatched_keys = set(
        DispatchItem.objects.values_list('service_id', 'part_type', 'faulty_serial')
    )

    # clappia_data can contain duplicate rows for the same service_id;
    # keep only the most recent row per (service_id, part_type, faulty_serial)
    # -- keyed on the serial too, since the same part_type "slot" can hold
    # two genuinely different materials (e.g. a motor and a pump).
    lines_by_key = {}
    for ticket in tickets:
        replacement_date = datetime.combine(ticket.complaint_reg_date, datetime.min.time())
        for part_type, faulty_field, label, name_field in PART_TYPES:
            faulty_serial = _clean(getattr(ticket, faulty_field))
            if not faulty_serial:
                continue
            key = (ticket.service_id, part_type, faulty_serial)
            existing = lines_by_key.get(key)
            if existing is not None and existing.replacement_date >= replacement_date:
                continue
            material_name = label if name_field is None else (_clean(getattr(ticket, name_field)) or label)
            lines_by_key[key] = MaterialLine(
                service_id=ticket.service_id,
                part_type=part_type,
                part_type_label=label,
                material_name=material_name,
                faulty_serial=faulty_serial,
                controller_serial=ticket.machine_no,
                si_details=ticket.si_name,
                farmer_name=ticket.farmer_name,
                location=ticket.location,
                service_person_name=ticket.engineer_name,
                replacement_date=replacement_date,
                is_dispatched=key in dispatched_keys,
            )

    lines = list(lines_by_key.values())
    lines.sort(key=lambda line: line.replacement_date, reverse=True)
    return lines


def record_status_event(item, status, remarks, user):
    """Append an entry to the item's status history. DispatchItem.status
    only holds the current value; this is the source of truth for full
    material history, kept for future reporting."""
    DispatchItemStatusEvent.objects.create(item=item, status=status, remarks=remarks, changed_by=user)


def _items_ever_at_stage(status):
    """Every item that has ever reached the given status, regardless of
    where it is now -- lets a stage's page show its own full history
    (pending action, and whatever happened after) the same way the
    warehouse pages already do."""
    return (
        DispatchItem.objects.filter(status_events__status=status)
        .distinct()
        .select_related('dispatch', 'dispatch__destination', 'forward_dispatch__destination')
        .order_by('-created_at')
    )


def get_service_desk_items():
    return _items_ever_at_stage('with_service_desk')


def get_electronics_items():
    return _items_ever_at_stage('with_electronics')
