from django import forms

from .models import DeliveryPartner, DispatchLocation


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


class DispatchForm(DeliveryPartnerFieldsMixin, forms.Form):
    """Engineer's initial dispatch to a regional warehouse or RSC."""

    pickup_number = forms.CharField(max_length=100)
    lr_number = forms.CharField(max_length=100)
    delivery_challan_number = forms.CharField(max_length=100)
    destination = forms.ModelChoiceField(queryset=DispatchLocation.objects.filter(is_active=True))
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class ForwardDispatchForm(DeliveryPartnerFieldsMixin, forms.Form):
    """A regional warehouse forwarding a material onward -- only
    Warehouse-type locations are valid further destinations."""

    pickup_number = forms.CharField(max_length=100)
    lr_number = forms.CharField(max_length=100)
    delivery_challan_number = forms.CharField(max_length=100)
    destination = forms.ModelChoiceField(
        queryset=DispatchLocation.objects.filter(is_active=True, location_type=DispatchLocation.WAREHOUSE)
    )
    remarks = forms.CharField(widget=forms.Textarea, required=False)


class WarehouseRemarksForm(forms.Form):
    """Simple status-only actions: Tested OK, Repaired, Dispatched to OEM."""

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
    reservation_no = forms.CharField(max_length=255)
    remarks = forms.CharField(widget=forms.Textarea)


def _choices(text):
    return [(line.strip(), line.strip()) for line in text.strip().splitlines() if line.strip()]


INITIAL_OBSERVATION_CHOICES = _choices("""
Battery holder missing
C1 & C2 found damaged
C29 missing
Display Hang
Fly back track damaged
Display blank
Extra Cap removed
Power off
PCB burn
IGBT short
MTR phase loss
Track damaged
PCB BROKEN
TRACK DAMAGED
NA
Communication Problem
Short circuit on display
Current missmatched
IGBT temp.
Connector broken
faulty Display
Components Missing
Network Problem
Flyback components damaged
Dry solder
Over voltage
MTR unbalanced
Serial no. sticker
TMS IC SHORT
COMPONENTS DAMAGED/SHORT/BUST
EC200 short
control board off
PCB GREEN MASKING EXPOSED
OVER CURRENT
UVW VOLTAGE MISMATCH
CURRENT SECTION BUST
WATER DAMAGED PCB
UNDER VOLTAGE SHOWN ON DISPLAY
MOV BUST
Burg strip damage
Blinking PCB
DEACTIATED PCB
OUT DATED ECN OLD PCB
TRACK BURN
MUD FOUND ON PCB
DC BUS VOLTAGE MISMATCH
FAN CONTROLLER BROKEN
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
Both Ctrl+Power
Only Ctrl
Only Power
RMU
PCB issue reported
""")

FAILURE_CATEGORY_CHOICES = _choices("""
Hardware
Software
Prod process
QC oversight
Hardware(Control) & Software (Power)
Hardware(power) & Software (control)
Hardware & Software
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
""")


class ElectronicsProceedForm(forms.Form):
    """Electronics' detailed diagnostic checklist -- captured once when
    proceeding to a Tested OK / Scrapped decision."""

    BLANK = [('', '— Select —')]
    OUTCOME_CHOICES = [('tested_ok', 'Tested OK'), ('scrapped', 'Scrapped')]

    initial_observation = forms.ChoiceField(choices=BLANK + INITIAL_OBSERVATION_CHOICES)
    pcb_type = forms.ChoiceField(choices=BLANK + PCB_TYPE_CHOICES)
    pcb_issue = forms.ChoiceField(choices=BLANK + PCB_ISSUE_CHOICES)
    failure_category = forms.ChoiceField(choices=BLANK + FAILURE_CATEGORY_CHOICES)
    sub_category = forms.ChoiceField(choices=BLANK + SUB_CATEGORY_CHOICES)
    igbt_pin_status = forms.ChoiceField(choices=BLANK + IGBT_PIN_STATUS_CHOICES)
    component_change = forms.CharField(max_length=255)
    test_machine_info = forms.CharField(max_length=255)
    tested_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    outcome = forms.ChoiceField(choices=BLANK + OUTCOME_CHOICES)
    remarks = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        # This form's fields live inside a <dialog> outside the actual
        # <form id="action-form">, same as every other dialog in this app --
        # each widget needs form="action-form" to submit with it.
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['form'] = 'action-form'
