from collections import namedtuple
from dataclasses import dataclass
from datetime import date, datetime

from .models import (
    ArchivedMaterialLine, ClappiaData, DispatchItem, DispatchItemStatusEvent, User,
)

# ez_service holds records going back to 2019 (lakhs of rows) -- only
# tickets registered on or after this date are considered. Rows with no
# complaint_reg_date at all are legacy data from before this field existed
# and are excluded too.
DATA_CUTOFF_DATE = date(2026, 7, 19)

# (part_type key, faulty-serial column, display label, name source, problem source)
# name source is None for Power Card / Control Card, which have no
# ticket-provided name of their own -- the label is used as-is. Both share
# one fault reason field (controller_display_fault) rather than having a
# problem field each. Generic "material" slots (up to 3 per visit) each have
# their own component and problem field.
PART_TYPES = [
    ('power_card', 'faulty_power_card_no', 'Power Card', None, 'controller_display_fault'),
    ('control_card', 'faulty_control_card_no', 'Control Card', None, 'controller_display_fault'),
    ('material', 'faulty_part_no_1', 'Material', 'component_1', 'problem_1'),
    ('material', 'faulty_part_no_2', 'Material', 'component_2', 'problem_2'),
    ('material', 'faulty_part_no_3', 'Material', 'component_3', 'problem_3'),
]

# Generic "material" entries whose name suggests a motor or pump follow a
# different repair workflow (repair/OEM) than cards/RMU (tested OK/dispatch).
MOTOR_PUMP_KEYWORDS = ('motor', 'pump')

# The source data uses '-1' (as well as blank/None) as a sentinel for
# "not applicable" in these free-text fields -- e.g. an unused replacement
# slot's component/faulty-part columns.
BLANK_SENTINELS = {'', '-1'}

DispatchMeta = namedtuple(
    'DispatchMeta',
    'dispatched_at partner_name destination_name pickup_number lr_number delivery_challan_number '
    'status received_date final_remark is_archived dest_received_date',
)


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


def engineer_status_label(status, received_date, destination_name):
    """All a service engineer gets to know about a dispatched material:
    whether it has reached the place it was sent to. Anything past the
    destination's receive step (service desk, electronics, scrap, ...) is
    not theirs to see. A forwarded item was necessarily received first."""
    if status != 'dispatched' or received_date is not None:
        return f'Received at {destination_name}'
    return 'Dispatched'


def type_key(part_type, material_name):
    """Filter/segregation key: power_card, control_card, motor,
    submersible_pump, surface_pump, or material (anything else)."""
    if is_motor_or_pump(part_type, material_name):
        return motor_pump_type(material_name)
    return part_type


def type_label(part_type, material_name):
    key = type_key(part_type, material_name)
    if key == 'motor':
        return 'Submersible Motor' if 'submersible' in (material_name or '').lower() else 'Motor'
    return {
        'power_card': 'Power Card', 'control_card': 'Control Card',
        'submersible_pump': 'Submersible Pump', 'surface_pump': 'Surface Pump',
    }.get(key, 'Material')


def motor_pump_type(material_name):
    """'motor', 'submersible_pump' or 'surface_pump' -- decides which OEM
    name list applies, and whether Head/Inch size are asked for at all
    (not for a bare motor). Only meaningful when is_motor_or_pump is True."""
    name = (material_name or '').lower()
    if 'motor' in name:
        return 'motor'
    if 'submersible' in name:
        return 'submersible_pump'
    return 'surface_pump'


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
    slot: str
    problem: str
    dispatch_date: datetime
    delivery_partner_name: str
    destination_name: str
    pickup_number: str
    lr_number: str
    delivery_challan_number: str
    is_archived: bool = False
    status_label: str = ''
    received_date: object = None  # when the destination received it (engineer-facing)

    @property
    def filter_type(self):
        return type_key(self.part_type, self.material_name)

    @property
    def type_label(self):
        return type_label(self.part_type, self.material_name)

    @property
    def key(self):
        # slot (the source column, e.g. faulty_part_no_2) rather than
        # part_type disambiguates two generic "material" slots on the same
        # visit that happen to share a faulty_serial (e.g. a motor and a
        # pump both logged with the same placeholder serial) -- without it
        # they'd collide and one would silently vanish from selection.
        return f'{self.service_id}|{self.slot}|{self.faulty_serial}'


def get_material_lines_for_engineer(email=None, include_archived=False):
    """Every material replaced, one row per replaced part -- for one
    engineer, or every engineer if email is omitted (used by the admin
    dashboard to show items still pending dispatch).

    A single completed visit can have a Power card, a Control card, and up
    to 3 generic materials all replaced at once -- each becomes its own
    line. Only completed visits registered on/after DATA_CUTOFF_DATE are
    considered; the source table also holds in-progress ones, and years of
    older data before the cutoff.
    """
    tickets = ClappiaData.objects.filter(status__iexact='completed', complaint_reg_date__gte=DATA_CUTOFF_DATE)
    if email:
        tickets = tickets.filter(engineer_email__iexact=email)
        registered_emails = None
    else:
        # Admin "all engineers" view -- only show tickets from engineers who
        # actually have a login, not every free-text name in clappia_data.
        registered_emails = {
            e.lower() for e in User.objects.filter(role='engineer', status='active').values_list('email', flat=True)
        }
    dispatch_info = {
        (service_id, part_type, faulty_serial): DispatchMeta(*rest)
        for service_id, part_type, faulty_serial, *rest in DispatchItem.all_objects.values_list(
            'service_id', 'part_type', 'faulty_serial',
            'dispatch__dispatched_at', 'dispatch__delivery_partner__name', 'dispatch__destination__name',
            'dispatch__pickup_number', 'dispatch__lr_number', 'dispatch__delivery_challan_number',
            'status', 'received_date', 'electronics_final_remark', 'is_archived',
            'destination_received_date',
        )
    }

    # clappia_data can contain duplicate rows for the same service_id;
    # keep only the most recent row per (service_id, part_type, faulty_serial)
    # -- keyed on the serial too, since the same part_type "slot" can hold
    # two genuinely different materials (e.g. a motor and a pump).
    lines_by_key = {}
    for ticket in tickets:
        if registered_emails is not None and (ticket.engineer_email or '').lower() not in registered_emails:
            continue
        replacement_date = datetime.combine(ticket.complaint_reg_date, datetime.min.time())
        for part_type, faulty_field, label, name_field, problem_field in PART_TYPES:
            faulty_serial = _clean(getattr(ticket, faulty_field))
            if not faulty_serial:
                continue
            # Keyed on slot (faulty_field), not just part_type: two generic
            # "material" slots on the same visit (e.g. motor + pump) can
            # share a faulty_serial -- see MaterialLine.key.
            key = (ticket.service_id, faulty_field, faulty_serial)
            existing = lines_by_key.get(key)
            if existing is not None and existing.replacement_date >= replacement_date:
                continue
            material_name = label if name_field is None else (_clean(getattr(ticket, name_field)) or label)
            problem = None if problem_field is None else _clean(getattr(ticket, problem_field))
            dispatch_meta = dispatch_info.get((ticket.service_id, part_type, faulty_serial))
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
                is_dispatched=dispatch_meta is not None,
                received_date=dispatch_meta.dest_received_date if dispatch_meta else None,
                status_label=(
                    engineer_status_label(dispatch_meta.status, dispatch_meta.received_date, dispatch_meta.destination_name)
                    if dispatch_meta else ''
                ),
                slot=faulty_field,
                problem=problem,
                dispatch_date=dispatch_meta.dispatched_at if dispatch_meta else None,
                delivery_partner_name=dispatch_meta.partner_name if dispatch_meta else None,
                destination_name=dispatch_meta.destination_name if dispatch_meta else None,
                pickup_number=dispatch_meta.pickup_number if dispatch_meta else None,
                lr_number=dispatch_meta.lr_number if dispatch_meta else None,
                delivery_challan_number=dispatch_meta.delivery_challan_number if dispatch_meta else None,
            )

    archived_keys = set(ArchivedMaterialLine.objects.values_list('service_id', 'slot', 'faulty_serial'))
    lines = []
    for key, line in lines_by_key.items():
        # Archived either as a not-yet-dispatched line, or because its
        # dispatched item was archived -- both stay admin-only.
        meta_archived = bool(line.is_dispatched and dispatch_info[(line.service_id, line.part_type, line.faulty_serial)].is_archived)
        line.is_archived = key in archived_keys or meta_archived
        if include_archived or not line.is_archived:
            lines.append(line)
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
        .prefetch_related('status_events')
        .order_by('-created_at')
    )


def get_service_desk_items():
    return _items_ever_at_stage('with_service_desk')


def get_electronics_items():
    return _items_ever_at_stage('with_electronics')
