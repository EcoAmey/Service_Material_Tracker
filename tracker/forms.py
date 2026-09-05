from django import forms

from .models import DeliveryPartner, DispatchLocation, User


class DeliveryPartnerFieldsMixin(forms.Form):
    """Shared 'pick from list or type a new one' delivery partner fields."""

    delivery_partner = forms.ModelChoiceField(
        queryset=DeliveryPartner.objects.filter(is_active=True), required=False
    )
    custom_delivery_partner = forms.CharField(
        max_length=255, required=False, label='Other delivery partner (if not listed)'
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('delivery_partner') and not cleaned.get('custom_delivery_partner', '').strip():
            raise forms.ValidationError('Select a delivery partner or enter one manually.')
        return cleaned


def resolve_delivery_partner(cleaned_data):
    """DeliveryPartnerFieldsMixin's result is either a real DeliveryPartner
    or a free-typed name. A typed name still needs a real row (the FK it
    fills isn't nullable), but as inactive -- so a one-off name typed here
    is usable for this dispatch without joining the reusable dropdown list."""
    delivery_partner = cleaned_data['delivery_partner']
    custom_name = cleaned_data['custom_delivery_partner'].strip()
    if not delivery_partner and custom_name:
        delivery_partner, _ = DeliveryPartner.objects.get_or_create(
            name=custom_name, defaults={'is_active': False}
        )
    return delivery_partner


class DispatchForm(DeliveryPartnerFieldsMixin, forms.Form):
    """Engineer's initial dispatch to a regional warehouse or RSC.

    pickup/LR/challan numbers are optional here (not required=True) because
    a "By Hand" dispatch (handed to the warehouse directly, no courier) has
    none of these -- DispatchSubmitView enforces them as required for every
    other delivery partner.
    """

    pickup_number = forms.CharField(max_length=100, required=False)
    lr_number = forms.CharField(max_length=100, required=False)
    delivery_challan_number = forms.CharField(max_length=100, required=False)
    destination = forms.ModelChoiceField(queryset=DispatchLocation.objects.filter(is_active=True))
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class ForwardDispatchForm(DeliveryPartnerFieldsMixin, forms.Form):
    """A regional warehouse forwarding a material onward -- only
    Warehouse-type locations are valid further destinations.

    pickup/LR/challan numbers are optional here (not required=True) because
    a "By Hand" dispatch (handed to the destination warehouse directly, no
    courier) has none of these -- WarehouseActionView enforces them as
    required for every other delivery partner (mirrors DispatchForm /
    DispatchSubmitView on the engineer's own dispatch).
    """

    pickup_number = forms.CharField(max_length=100, required=False)
    lr_number = forms.CharField(max_length=100, required=False)
    delivery_challan_number = forms.CharField(max_length=100, required=False)
    destination = forms.ModelChoiceField(
        queryset=DispatchLocation.objects.filter(is_active=True, location_type=DispatchLocation.WAREHOUSE)
    )
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class WarehouseRemarksForm(forms.Form):
    """Simple status-only actions: Tested OK, Repaired, Dispatched to OEM."""

    remarks = forms.CharField(widget=forms.Textarea, required=False)


class AddToStockForm(forms.Form):
    """Main warehouse's 'Add to Stock' action -- closes the loop on a
    repaired item, capturing the outward reservation number it's issued
    against."""

    outward_reservation_no = forms.CharField(max_length=255, label='Outward reservation number')
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class ReceiveMaterialForm(forms.Form):
    """The main warehouse receiving a Power Card / Control Card / RMU item:
    records when it physically arrived and whether its serial number
    matches the ticket on file."""

    SERIAL_CHOICES = [('yes', 'Matches'), ('no', 'Does not match')]

    received_date = forms.DateField()
    serial_matches = forms.ChoiceField(choices=SERIAL_CHOICES)
    received_serial_no = forms.CharField(max_length=255, required=False, label='Received serial number')
    reservation_no = forms.CharField(max_length=255, label='Reservation number')
    remarks = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('serial_matches') == 'no':
            if not cleaned.get('remarks', '').strip():
                raise forms.ValidationError('Please note the serial mismatch in the remarks.')
            if not cleaned.get('received_serial_no', '').strip():
                raise forms.ValidationError('Please enter the received serial number.')
        return cleaned


class MotorDispositionForm(forms.Form):
    """Warehouse deciding a motor/pump's fate -- OEM repair or scrap --
    both requiring an inward and outward reservation number."""

    inward_reservation_no = forms.CharField(max_length=255, label='Inward reservation number')
    outward_reservation_no = forms.CharField(max_length=255, label='Outward reservation number')
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class CardOemDispatchForm(forms.Form):
    """Warehouse dispatching a P-serial Power/Control Card (see
    DispatchItem.is_p_serial_card) straight to OEM after receiving it --
    ships out directly, so it's tracked by its own LR/challan number rather
    than the motor/pump inward-reservation concept."""

    lr_no = forms.CharField(max_length=255, label='LR number')
    challan_no = forms.CharField(max_length=255, label='DC number')
    outward_reservation_no = forms.CharField(max_length=255, label='Outward reservation number')


class CardScrapForm(forms.Form):
    """Warehouse scrapping a P-serial Power/Control Card after receiving
    it."""

    CONDITION_CHOICES = [
        ('damaged', 'Damaged'),
        ('burn', 'Burn'),
        ('non_repairable', 'Non-repairable'),
    ]

    condition = forms.ChoiceField(choices=CONDITION_CHOICES)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    outward_reservation_no = forms.CharField(max_length=255, label='Outward reservation number')


class ElectronicsAssignmentForm(forms.Form):
    """Service Desk's mandatory inspection checklist before assigning an
    item onward to Electronics -- every field here is required."""

    YES_NO = [('yes', 'Yes'), ('no', 'No')]
    PASS_FAIL = [('passed', 'Passed'), ('failed', 'Failed')]
    WIRING_CHOICES = [('repaired', 'Repaired'), ('ok', 'Was OK')]

    problem = forms.CharField(max_length=255)
    visual_inspection_done = forms.ChoiceField(choices=YES_NO)
    mtr_test = forms.ChoiceField(choices=PASS_FAIL)
    cold_test = forms.ChoiceField(choices=PASS_FAIL)
    wiring = forms.ChoiceField(choices=WIRING_CHOICES)
    remarks = forms.CharField(widget=forms.Textarea)


def _choices(text):
    return [(line.strip(), line.strip()) for line in text.strip().splitlines() if line.strip()]


MOTOR_CAPACITY_CHOICES = _choices("""
1 HP
2 HP
3 HP
5 HP
7.5 HP
10 HP
""")

MOTOR_HEAD_SIZE_CHOICES = _choices("""
10 Meters
20 Meters
30 Meters
40 Meters
50 Meters
60 Meters
70 Meters
80 Meters
85 Meters
90 Meters
100 Meters
35 Meters
150 Meters
180 Meters
120 Meters
130 Meters
""")

MOTOR_INCH_SIZE_CHOICES = _choices("""
2 inch
4 inch
6 inch
8 inch
""")

# OEM name list depends on the pump type -- Motor/Surface Pump share one
# list, Submersible Pump uses another (see DispatchItem.motor_pump_type).
MOTOR_SURFACE_OEM_CHOICES = _choices("""
Techno_OEM-1
Borana_OEM-3
Varuna_OEM-4
Oswal_OEM-5
Matel_OEM-2
Amrut
CRI
Shakti
Sleka
Bronex
Silver
ViraSubmersible_OEM-7
Oswal Pumps
Latteys_OEM-8
Ravi Water Flow_OEM-9
Felie_OEM-13
Advik
Fountain Pumps_OEM-11
Hiwaki Pumps_OEM-12
Japhet_OEM-13_Import
Yongxin_OEM-14_Import
Inox
Pluga
Ganesh Pumps
""")

SUBMERSIBLE_PUMP_OEM_CHOICES = _choices("""
Techno_OEM-1
Borana_OEM-3
Varuna_OEM-4
Oswal_OEM-5
Matel_OEM-2
Amrut
CRI
Shakti
Sleka
Bronex
Silver Pumps
Latteys Pumps
Oswal Pumps
CNP_OEM-8
Ravi Water Flow_OEM-9
Vallabh Pumps
Parth_OEM-10
Fountain Pumps_OEM-11
RCP Engineering_OEM-12
Japhet_OEM-13_Import
MEC
Ganesh Pumps
Inox
Pluga
""")

# Union of both lists -- the form only checks the submitted name is valid
# for *some* pump type; the dialog's JS is what shows the right list for
# the selected item.
MOTOR_OEM_CHOICES = MOTOR_SURFACE_OEM_CHOICES + [
    choice for choice in SUBMERSIBLE_PUMP_OEM_CHOICES if choice not in MOTOR_SURFACE_OEM_CHOICES
]


class MotorReceiveForm(forms.Form):
    """Motor/Pump receive checklist -- captured once (at either the regional
    or main warehouse) before an OEM/Scrap/Repaired/Service Center decision
    can be made. See DispatchItem.is_pending_motor_receive."""

    received_date = forms.DateField()
    capacity = forms.ChoiceField(choices=MOTOR_CAPACITY_CHOICES)
    oem_name = forms.ChoiceField(choices=MOTOR_OEM_CHOICES)
    # Head/inch size only apply to Surface/Submersible Pump, not a bare
    # Motor -- not required here since the dialog hides them for a motor
    # (see DispatchItem.motor_pump_type).
    head_size = forms.ChoiceField(choices=MOTOR_HEAD_SIZE_CHOICES, required=False)
    inch_size = forms.ChoiceField(choices=MOTOR_INCH_SIZE_CHOICES, required=False)
    remarks = forms.CharField(widget=forms.Textarea, required=False)


# The old single "Initial Observation" dropdown is now 4 categorized
# checklists (each a multi-select, mirroring SUB_CATEGORY_CHOICES below) --
# see ElectronicsProceedForm.
PHYSICAL_VISUAL_DAMAGE_CHOICES = _choices("""
PCB Broken / Cracked
Track Burned / Damaged
Flyback Track Damaged
PCB Green Masking Exposed
PCB Burned
Water / Moisture Damaged
Mud / Foreign Material Found on PCB
Corrosion / Oxidation Present
NA
""")

COMPONENT_STATUS_CHOICES = _choices("""
Components Damaged / Shorted / Burst
TMS IC Short
EC200 Short
IGBT Short
MOV Burst
Capacitor Swollen / Damaged (e.g., C1, C2)
Component Missing (e.g., C29, Battery Holder)
Burg Strip / Connector Damage
Dry Solder / Solder Bridge
NA
""")

POWER_ELECTRICAL_FAULT_CHOICES = _choices("""
Over Current Fault
Current Section Burst
Current Mismatched
UVW Voltage Mismatch
DC Bus Voltage Mismatch
Under Voltage Displayed
MTR Phase Loss
NA
""")

SYSTEM_DISPLAY_BEHAVIOR_CHOICES = _choices("""
Control Board Off / Power Off
Display Blank
Display Frozen / Hung
Short Circuit on Display
Communication Error / Problem
Blinking PCB Status LED
Fan Controller Broken
Outdated ECN / Old Revision PCB
Deactivated PCB
NA
""")

PCB_TYPE_CHOICES = _choices("""
RMU V4
RMU V3
RMU V3.1
RMU V5.1
RMU 5.2
RMU 5.3.1
5HP ecore Power (0.2)
5HP ecore control (0.2)
5HP ecore control (1.1)
5HP ecore Power (0.2) & 5HP ecore control (0.2)
5HP ecore power (0.2) & 5HP ecore control (1.1)
5HP ecore Power (0.2) & 5HP ecore control (1.1)
5HP ecore power (2.0.0) & 5HP ecore control (1.1)
5HP v0.2 Power Board
5HP ecore Power (2.0.0)
5HP v3.0.1 Power Board
5HP ecore power (2.0.0) & 5HP ecore control (0.2)
5HP ecore power (3.0.1) & 5HP ecore control (1.1)
5HP ecore power (3.0.1) & 5HP ecore control (V0.2)
3HP V1.2 Power Board
3HP ecore control (1.2)
3HP ecore control (1.4)
3HP ecore Power (1.2)
3HP ecore Power (1.4)
3HP V1.4 Power Board
3HP ecore Power (1.5) & 3HP ecore control (1.4)
3HP ecore Power (1.2) & 3HP ecore control (1.2)
3HP ecore Power (1.4) & 3HP ecore control (1.4)
3HP ecore Power (1.6) & 3HP ecore control (1.4)
3HP ecore Power (1.6) & 3HP ecore control (1.5)
3HP ecore Power (1.6) & 3HP ecore control (4g 6.2.0 sim com)
10HP ecore power (v1.2.4) & RMU (V5.2 WITH LINK SOLDER)
10HP ecore power (v1.2.4) & RMU (V5.3.1)
10HP ecore power (v1.2.4)
10HP ecore power (v1.1.0)
""")

PCB_ISSUE_CHOICES = _choices("""
Both Control+Power
Only Control
Only Power
RMU
PCB issue reported
""")

FAILURE_CATEGORY_CHOICES = _choices("""
Hardware
Software
Prod Process
None
""")

SUB_CATEGORY_CHOICES = _choices("""
IGBT
Mosfet
Diode
Connector
IC's
BURG STRIP
IGBT+Snabar
Capacitor
Resistor
Resistor+Capacitor
Flyback
Missing Component
Drysolder
NA
U20 burn
Replaced NEW PCB
Resistor+Capacitor+IC
Ic's+Coin Cell
Mosfet+IC+Resistor+Capacitor
Ic's+ Resistor
Diode & Resistor & SIM tray
Diode & resistor
IGBT & Diode
Antenna
M66 quectel IC
Display
coin cell
IGBT + IC
IC+Diode
SIM Tray
IGBT-Fuji
IGBT-ST
Flyback+ Mosfet
Flyback+ Mosfet+IC
IC+Snabar
Ic's+ Resistor+Capacitor
IGBT + IC+ Resistor
Flyback+Display
Optocoupler
EC200 short
IGBT-ST+IC+Diode
corrosion
Flyback+ Mosfet +Snubber
IGBT+Snubber
IGBT ST+IC
PCB BURN
TRANSFORMER
GREEN MASKING EXPOSED
MOV BUST
TRACK BURN
""")

IGBT_PIN_STATUS_CHOICES = _choices("""
U short w.r.t. -Ve
V short w.r.t. -Ve
W short w.r.t. -Ve
U short w.r.t. +Ve
V short w.r.t. +Ve
W short w.r.t. +Ve
VALUE OK  BUT INTERNAL FUNCTIONING OFF
UVW SHORT WITH +VE
UVW SHORT WITH -VE
IGBT BROKEN
OK Condition
""")


class ElectronicsProceedForm(forms.Form):
    """Electronics' detailed diagnostic checklist -- captured once when
    proceeding to a diagnosed (Completed) state. This only records the
    diagnosis; the actual Send Back to Warehouse / Scrap disposition is a
    separate, later action (see ElectronicsDispositionForm)."""

    NA_CHOICE = [('NA', 'NA')]
    BLANK = [('', '— Select —')]
    FINAL_REMARK_CHOICES = [
        ('repaired_ok', 'Repaired OK'),
        ('tested_ok', 'Tested OK'),
        ('scrapped', 'Scrapped'),
    ]

    electronics_engineer_name = forms.CharField(max_length=255, label='Electronics Engineer name')
    physical_visual_damage = forms.MultipleChoiceField(choices=PHYSICAL_VISUAL_DAMAGE_CHOICES, widget=forms.SelectMultiple)
    component_status = forms.MultipleChoiceField(choices=COMPONENT_STATUS_CHOICES, widget=forms.SelectMultiple)
    power_electrical_faults = forms.MultipleChoiceField(choices=POWER_ELECTRICAL_FAULT_CHOICES, widget=forms.SelectMultiple)
    system_display_behavior = forms.MultipleChoiceField(choices=SYSTEM_DISPLAY_BEHAVIOR_CHOICES, widget=forms.SelectMultiple)
    pcb_type = forms.ChoiceField(choices=BLANK + NA_CHOICE + PCB_TYPE_CHOICES)
    pcb_issue = forms.ChoiceField(choices=BLANK + NA_CHOICE + PCB_ISSUE_CHOICES)
    failure_category = forms.ChoiceField(choices=BLANK + FAILURE_CATEGORY_CHOICES)
    sub_category = forms.MultipleChoiceField(choices=SUB_CATEGORY_CHOICES, widget=forms.SelectMultiple)
    igbt_pin_status = forms.ChoiceField(choices=BLANK + NA_CHOICE + IGBT_PIN_STATUS_CHOICES)
    component_change = forms.CharField(max_length=255)
    test_machine_info = forms.CharField(max_length=255)
    tested_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    final_remark = forms.ChoiceField(choices=BLANK + FINAL_REMARK_CHOICES)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        # This form's fields live inside a <dialog> outside the actual
        # <form id="action-form">, same as every other dialog in this app --
        # each widget needs form="action-form" to submit with it.
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['form'] = 'action-form'


class ElectronicsDispositionForm(forms.Form):
    """Electronics' final disposition of an already-diagnosed item --
    Send Back to Warehouse or Scrap -- captured separately from the
    diagnostic checklist above."""

    outward_reservation_no = forms.CharField(max_length=255, label='Outward reservation number')


class CreateUserForm(forms.Form):
    """Admin creating a new login -- this app stores passwords in plaintext
    (see User.check_password), so no hashing step is needed here."""

    name = forms.CharField(max_length=255)
    email = forms.CharField(max_length=255)
    password = forms.CharField(max_length=255)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)


class BulkCreateUsersForm(forms.Form):
    """Admin creating many logins at once -- one 'name,email,password,role'
    line per user, pasted into a single textarea. Each line is validated
    independently so one bad row doesn't block the rest (see
    AdminUserActionView's 'bulk_create' handling)."""

    rows = forms.CharField(widget=forms.Textarea)

    def parse_rows(self):
        """Splits the pasted text into (line_no, name, email, password, role)
        tuples, or records a parse error for lines that don't have exactly
        4 comma-separated fields. Role/email validity is checked later by
        the caller, against live DB state (existing emails)."""
        parsed, errors = [], []
        for line_no, raw_line in enumerate(self.cleaned_data['rows'].splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) != 4:
                errors.append(f'Line {line_no}: expected "name,email,password,role", got {len(fields)} field(s).')
                continue
            name, email, password, role = fields
            if not all([name, email, password, role]):
                errors.append(f'Line {line_no}: all four fields are required.')
                continue
            valid_roles = dict(User.ROLE_CHOICES)
            if role not in valid_roles:
                errors.append(f'Line {line_no}: unknown role "{role}".')
                continue
            parsed.append((line_no, name, email, password, role))
        return parsed, errors


class ChangePasswordForm(forms.Form):
    new_password = forms.CharField(max_length=255, label='New password')


class ChangeRoleForm(forms.Form):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
