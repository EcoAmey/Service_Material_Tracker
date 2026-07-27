from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)


class User(AbstractBaseUser):
    """Maps to the existing `users` table in the fault_tracker database.

    managed=False: Django never creates/alters/drops this table, it only
    reads and writes rows in the columns already defined below.
    """

    # One RoleBackend per role in AUTHENTICATION_BACKENDS (tracker/backends.py)
    # -- this is the exhaustive set of roles this app actually authenticates.
    ROLE_CHOICES = [
        ('engineer', 'Engineer'),
        ('regwarehouse', 'Regional Warehouse'),
        ('warehouse', 'Warehouse'),
        ('servicedesk', 'Service Desk'),
        ('electronics', 'Electronics'),
        ('admin', 'Admin'),
    ]

    # Explicit to match the real column type (int), overriding the
    # project-wide BigAutoField default which would mismatch on FKs.
    id = models.AutoField(primary_key=True)
    # AbstractBaseUser's last_login field has no matching column in the
    # real users table; removing it avoids Django querying for it.
    last_login = None
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    # AbstractBaseUser already defines a `password` field; we redeclare it
    # here only to point at the real column name, password_hash.
    password = models.CharField(max_length=255, db_column='password_hash')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return self.status == 'active'

    def check_password(self, raw_password):
        # The users table stores the actual password, not a hash.
        return self.password == raw_password


class ClappiaData(models.Model):
    """Maps to the `ez_service` table on the shared RDS server -- service
    tickets/visits, owned by another team's process. Read via the
    'clappia' database connection (see tracker.db_router.ClappiaRouter),
    which is fetch-only: this app never writes to it, and never touches
    the many other unrelated tables that live on that same server.

    managed=False: Django never creates/alters/drops this table.
    submission_id is the primary key -- unlike service_id, which can repeat
    across multiple submissions for the same ticket, submission_id
    uniquely identifies one form submission/visit.

    Only columns this app actually reads are mapped -- the real table has
    many more (pump_type, oem, dc_*, cmc_*, etc.) that aren't used yet.
    """

    submission_id = models.CharField(max_length=255, primary_key=True)
    # A real date column (unlike submission_date, which is free text and
    # mostly blank) -- used as this app's notion of "when" a visit happened.
    complaint_reg_date = models.DateField(blank=True, null=True)
    service_id = models.CharField(max_length=255)
    machine_no = models.CharField(max_length=255)
    farmer_name = models.CharField(max_length=255)
    village = models.CharField(max_length=255, blank=True, null=True)
    taluka = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    si_name = models.CharField(max_length=255)
    engineer_name = models.CharField(max_length=255)
    engineer_email = models.CharField(max_length=255, db_column='engineer_mail')
    status = models.CharField(max_length=50)

    # Power Card / Control Card have no ticket-provided name of their own --
    # callers use a fixed label ("Power Card"/"Control Card") instead.
    faulty_power_card_no = models.CharField(max_length=255, blank=True, null=True)
    faulty_control_card_no = models.CharField(max_length=255, blank=True, null=True)

    # Up to 3 generic replaced parts per visit, each with its own name.
    component_1 = models.CharField(max_length=255, blank=True, null=True)
    component_2 = models.CharField(max_length=255, blank=True, null=True)
    component_3 = models.CharField(max_length=255, blank=True, null=True)
    faulty_part_no_1 = models.CharField(max_length=255, blank=True, null=True)
    faulty_part_no_2 = models.CharField(max_length=255, blank=True, null=True)
    faulty_part_no_3 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ez_service'

    def __str__(self):
        return self.submission_id

    @property
    def location(self):
        """village/taluka/district/state as one display string, standing
        in for the single 'location' field the app used to be given."""
        parts = [self.village, self.taluka, self.district, self.state]
        return ', '.join(part for part in parts if part)


class DeliveryPartner(models.Model):
    """Admin-managed lookup list of couriers/transporters for dispatch."""

    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DispatchLocation(models.Model):
    """Admin-managed lookup list of destinations for dispatch."""

    RSC = 'rsc'
    WAREHOUSE = 'warehouse'
    LOCATION_TYPE_CHOICES = [
        (RSC, 'Regional Service Center'),
        (WAREHOUSE, 'Warehouse'),
    ]

    name = models.CharField(max_length=255, unique=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_location_type_display()})'


class Dispatch(models.Model):
    """One dispatch action: a batch of materials sent together."""

    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='dispatches'
    )
    pickup_number = models.CharField(max_length=100)
    lr_number = models.CharField(max_length=100)
    delivery_challan_number = models.CharField(max_length=100)
    delivery_partner = models.ForeignKey(DeliveryPartner, on_delete=models.PROTECT)
    destination = models.ForeignKey(DispatchLocation, on_delete=models.PROTECT)
    remarks = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispatched_at']

    def __str__(self):
        return f'Dispatch #{self.pk} by {self.dispatched_by}'


class DispatchItem(models.Model):
    """One material actually dispatched, as part of a Dispatch batch.

    Stores a snapshot of the material's details at dispatch time, so the
    audit trail stays accurate even if the source clappia_data row changes
    later. unique_together enforces "cannot dispatch the same material
    twice" at the database level -- keyed on faulty_serial too, since a
    single service_id/part_type combo can legitimately hold two different
    physical materials (e.g. a motor and a pump both under the generic
    "material" bucket).
    """

    PART_TYPE_CHOICES = [
        ('power_card', 'Power Card'),
        ('control_card', 'Control Card'),
        ('material', 'Material'),
    ]

    STATUS_CHOICES = [
        ('dispatched', 'Dispatched'),
        ('tested_ok', 'Tested OK'),
        ('repaired', 'Repaired'),
        ('pending_oem_scrap', 'Pending OEM/Scrap Decision'),
        ('dispatched_to_oem', 'Dispatched to OEM'),
        ('dispatched_to_warehouse', 'Dispatched to Warehouse'),
        ('with_service_desk', 'With Service Desk'),
        ('with_electronics', 'With Electronics'),
        ('electronics_completed', 'Completed (Electronics)'),
        ('repaired_by_electronics', 'Repaired (Electronics)'),
        ('scrapped', 'Scrapped'),
        ('added_to_stock', 'Added to Service Stock'),
    ]

    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, related_name='items')
    service_id = models.CharField(max_length=255)
    part_type = models.CharField(max_length=20, choices=PART_TYPE_CHOICES)
    faulty_serial = models.CharField(max_length=255)
    material_name = models.CharField(max_length=255)
    controller_serial = models.CharField(max_length=255)
    si_details = models.CharField(max_length=255)
    farmer_name = models.CharField(max_length=255, default='')
    location = models.CharField(max_length=255, default='')
    service_person_name = models.CharField(max_length=255)
    replacement_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='dispatched')
    status_remarks = models.TextField(blank=True)
    status_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)
    # Second-hop shipment when a regional warehouse forwards this material
    # onward (status='dispatched_to_warehouse'). Only one further hop is
    # modeled -- if items ever need to move a 3rd time, this should become
    # its own MovementEvent table instead of a single extra FK.
    forward_dispatch = models.ForeignKey(
        Dispatch, null=True, blank=True, on_delete=models.SET_NULL, related_name='forwarded_items'
    )
    # Set once, by the main warehouse's "Receive" action.
    received_date = models.DateField(null=True, blank=True)
    received_serial_matches = models.BooleanField(null=True, blank=True)
    received_serial_no = models.CharField(max_length=255, blank=True, null=True)
    warehouse_reservation_no = models.CharField(max_length=255, blank=True, null=True)

    # Set once, by the main warehouse's "Dispatch to OEM" / "Scrap" action
    # on a motor/pump.
    oem_inward_reservation_no = models.CharField(max_length=255, blank=True, null=True)
    oem_outward_reservation_no = models.CharField(max_length=255, blank=True, null=True)

    # Set once, by the main warehouse's "Dispatch to OEM" action on a
    # P-serial Power/Control Card (see is_p_serial_card) -- this path ships
    # the card out directly, so it tracks its own LR/challan number instead
    # of reusing the motor/pump inward reservation concept above.
    # oem_outward_reservation_no is shared with the motor/pump path above.
    oem_dispatch_lr_no = models.CharField(max_length=255, blank=True, null=True)
    oem_dispatch_challan_no = models.CharField(max_length=255, blank=True, null=True)

    # Set once, by the main warehouse's "Scrap" action on a P-serial
    # Power/Control Card.
    SCRAP_CONDITION_CHOICES = [
        ('damaged', 'Damaged'),
        ('burn', 'Burn'),
        ('non_repairable', 'Non-repairable'),
    ]
    scrap_condition = models.CharField(max_length=20, blank=True, null=True, choices=SCRAP_CONDITION_CHOICES)

    # Set once, by the main warehouse's "Add to Stock" action.
    stock_outward_reservation_no = models.CharField(max_length=255, blank=True, null=True)

    # Service Desk's mandatory inspection checklist, set once when assigning
    # onward to Electronics.
    inspection_problem = models.CharField(max_length=255, blank=True, null=True)
    inspection_visual_done = models.BooleanField(null=True, blank=True)
    inspection_mtr_test_passed = models.BooleanField(null=True, blank=True)
    inspection_cold_test_passed = models.BooleanField(null=True, blank=True)
    inspection_wiring_repaired = models.BooleanField(null=True, blank=True)
    inspection_reservation_no = models.CharField(max_length=255, blank=True, null=True)

    # Electronics' detailed diagnostic checklist, set once when proceeding
    # to a Tested OK / Scrapped decision.
    electronics_initial_observation = models.CharField(max_length=255, blank=True, null=True)
    electronics_pcb_type = models.CharField(max_length=255, blank=True, null=True)
    electronics_pcb_issue = models.CharField(max_length=255, blank=True, null=True)
    electronics_failure_category = models.CharField(max_length=255, blank=True, null=True)
    # Widened from 255: now stores a comma-joined multi-select.
    electronics_sub_category = models.CharField(max_length=1000, blank=True, null=True)
    electronics_igbt_pin_status = models.CharField(max_length=255, blank=True, null=True)
    electronics_component_change = models.CharField(max_length=255, blank=True, null=True)
    electronics_test_machine_info = models.CharField(max_length=255, blank=True, null=True)
    electronics_tested_date = models.DateField(null=True, blank=True)
    electronics_engineer_name = models.CharField(max_length=255, blank=True, null=True)

    # Set once, when Electronics disposes of a completed item onward (see
    # is_electronics_completed / electronics_action_group below): the
    # diagnostic remark from the checklist above, and the reservation number
    # captured at that later disposition step.
    electronics_final_remark = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        choices=[
            ('repaired_ok', 'Repaired OK'),
            ('tested_ok', 'Tested OK'),
            ('scrapped', 'Scrapped'),
        ],
    )
    electronics_outward_reservation_no = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = [('service_id', 'part_type', 'faulty_serial')]

    def __str__(self):
        return f'{self.service_id} - {self.get_part_type_display()}'

    @property
    def is_motor_or_pump(self):
        # Local import avoids a circular import (services.py imports models.py).
        from .services import is_motor_or_pump
        return is_motor_or_pump(self.part_type, self.material_name)

    @property
    def is_p_serial_card(self):
        """A Power/Control Card whose faulty serial starts with 'P' -- these
        skip Service Desk/Electronics entirely and go straight from Receive
        to an OEM/Scrap decision instead."""
        if self.part_type not in ('power_card', 'control_card'):
            return False
        return self.faulty_serial.strip().upper().startswith('P')

    @property
    def effective_dispatch(self):
        """The dispatch that most recently brought this item to its current
        location: the forwarding dispatch if a regional warehouse forwarded
        it on, otherwise the original dispatch."""
        return self.forward_dispatch if self.forward_dispatch_id else self.dispatch

    @property
    def effective_arrival_date(self):
        return self.effective_dispatch.dispatched_at

    @property
    def assigned_to_service_desk_at(self):
        """When this item first reached Service Desk (Main Warehouse's
        Receive action) -- shown on both the Service Desk and Electronics
        pages, since both display items sourced from that same handoff."""
        event = self.status_events.filter(status='with_service_desk').first()
        return event.changed_at if event else None

    @property
    def is_pending_for_main_warehouse(self):
        """True if this item is awaiting the warehouse's initial Receive /
        Dispatch to OEM action, whether sent there directly by an engineer
        or forwarded on by a regional warehouse."""
        if self.status == 'dispatched_to_warehouse':
            return True
        if self.status == 'dispatched':
            return self.dispatch.destination.location_type == DispatchLocation.WAREHOUSE
        return False

    @property
    def is_pending_oem_scrap_decision(self):
        """True once a P-serial Power/Control Card has been received and is
        awaiting the warehouse's Dispatch to OEM / Scrap decision."""
        return self.status == 'pending_oem_scrap'

    @property
    def is_pending_for_service_desk(self):
        return self.status == 'with_service_desk'

    @property
    def is_pending_for_electronics(self):
        return self.status == 'with_electronics'

    @property
    def is_electronics_completed(self):
        return self.status == 'electronics_completed'

    @property
    def electronics_action_group(self):
        """'scrap' or 'send_to_warehouse', based on the diagnostic remark --
        used both to render each row's data-action-group and to re-check
        server-side that the right button was used."""
        return 'scrap' if self.electronics_final_remark == 'scrapped' else 'send_to_warehouse'

    @property
    def is_pending_stock_entry(self):
        """True once electronics has repaired this item and it is waiting
        for the warehouse to add it back to the service stock."""
        return self.status == 'repaired_by_electronics'


class DispatchItemStatusEvent(models.Model):
    """Append-only log of every status a DispatchItem has ever passed
    through. DispatchItem.status only holds the current value, so this is
    the source of truth for full material history (needed for reporting),
    and for finding "everything that ever reached stage X" regardless of
    where it is now.
    """

    item = models.ForeignKey(DispatchItem, on_delete=models.CASCADE, related_name='status_events')
    status = models.CharField(max_length=30, choices=DispatchItem.STATUS_CHOICES)
    remarks = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    # default=timezone.now (not auto_now_add) deliberately: auto_now_add would
    # silently overwrite the historical timestamp the backfill migration sets.
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['changed_at']

    def __str__(self):
        return f'{self.item_id}: {self.status} @ {self.changed_at:%Y-%m-%d %H:%M}'
