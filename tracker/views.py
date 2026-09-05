from collections import Counter

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from .forms import (
    AddToStockForm,
    BulkCreateUsersForm,
    CardOemDispatchForm,
    CardScrapForm,
    ChangePasswordForm,
    ChangeRoleForm,
    CreateUserForm,
    DispatchForm,
    ElectronicsAssignmentForm,
    ElectronicsDispositionForm,
    ElectronicsProceedForm,
    ForwardDispatchForm,
    MOTOR_CAPACITY_CHOICES,
    MOTOR_HEAD_SIZE_CHOICES,
    MOTOR_INCH_SIZE_CHOICES,
    MOTOR_SURFACE_OEM_CHOICES,
    SUBMERSIBLE_PUMP_OEM_CHOICES,
    MotorDispositionForm,
    MotorReceiveForm,
    ReceiveMaterialForm,
    WarehouseRemarksForm,
    resolve_delivery_partner,
)
from .models import DeliveryPartner, Dispatch, DispatchItem, DispatchLocation, User
from .services import (
    get_electronics_items,
    get_material_lines_for_engineer,
    get_service_desk_items,
    record_status_event,
)


class HomeDispatchView(LoginRequiredMixin, View):
    """Routes a logged-in user to the home page for their role."""

    login_url = 'tracker:login'

    def get(self, request, *args, **kwargs):
        if request.user.role == 'admin':
            return redirect('tracker:admin_dashboard')
        if request.user.role == 'regwarehouse':
            return redirect('tracker:warehouse_home')
        if request.user.role == 'warehouse':
            return redirect('tracker:main_warehouse_home')
        if request.user.role == 'servicedesk':
            return redirect('tracker:service_desk_home')
        if request.user.role == 'electronics':
            return redirect('tracker:electronics_home')
        return redirect('tracker:engineer_home')


class AdminRequiredMixin(LoginRequiredMixin):
    """Restricts a view to the 'admin' role, redirecting anyone else to
    their own home page -- shared by every admin-dashboard view."""

    login_url = 'tracker:login'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != 'admin':
            messages.error(request, 'You do not have access to the admin dashboard.')
            return redirect('tracker:home')
        return super().dispatch(request, *args, **kwargs)


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Admin-only overview: every material in the system, at whatever
    stage it's currently at -- unlike every operational page, not scoped
    to one role/destination."""

    template_name = 'tracker/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_section'] = 'dashboard'
        context['items'] = DispatchItem.objects.select_related(
            'dispatch', 'dispatch__destination', 'forward_dispatch__destination'
        ).order_by('-created_at')
        pending_lines = [line for line in get_material_lines_for_engineer() if not line.is_dispatched]
        context['pending_lines'] = pending_lines
        engineer_names = set(
            DispatchItem.objects.exclude(service_person_name='').values_list('service_person_name', flat=True)
        )
        engineer_names.update(line.service_person_name for line in pending_lines if line.service_person_name)
        context['engineer_names'] = sorted(engineer_names)
        return context


class AdminUserManagementView(AdminRequiredMixin, TemplateView):
    """Admin-only: list every login, create new ones, and change an
    existing one's password/role/active status."""

    template_name = 'tracker/admin_users.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_section'] = 'users'
        context['users'] = User.objects.order_by('name')
        context['role_choices'] = User.ROLE_CHOICES
        return context


class AdminUserActionView(AdminRequiredMixin, View):
    """Handles the admin acting on one user account at a time -- creating
    a new one, or changing an existing one's password/role/active status."""

    ACTIONS = {'create', 'bulk_create', 'change_password', 'change_role', 'activate', 'deactivate'}

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action not in self.ACTIONS:
            messages.error(request, 'Unknown action.')
            return redirect('tracker:admin_users')

        if action == 'create':
            form = CreateUserForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the new user form.')
                return redirect('tracker:admin_users')
            data = form.cleaned_data
            if User.objects.filter(email__iexact=data['email']).exists():
                messages.error(request, f"A user with email {data['email']} already exists.")
                return redirect('tracker:admin_users')
            User.objects.create(
                name=data['name'], email=data['email'], password=data['password'],
                role=data['role'], status='active',
            )
            messages.success(request, f"Created user {data['email']}.")
            return redirect('tracker:admin_users')

        if action == 'bulk_create':
            form = BulkCreateUsersForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please paste at least one user row.')
                return redirect('tracker:admin_users')
            parsed_rows, errors = form.parse_rows()

            # Case-insensitive dupe check against both the DB and other rows
            # in this same paste, so two identical rows in one paste don't
            # both silently succeed.
            existing_emails = {e.lower() for e in User.objects.values_list('email', flat=True)}
            seen_in_paste = set()
            created = []
            for line_no, name, email, password, role in parsed_rows:
                email_key = email.lower()
                if email_key in existing_emails or email_key in seen_in_paste:
                    errors.append(f'Line {line_no}: a user with email {email} already exists.')
                    continue
                seen_in_paste.add(email_key)
                created.append(User(name=name, email=email, password=password, role=role, status='active'))

            if created:
                User.objects.bulk_create(created)
                messages.success(request, f'Created {len(created)} user(s).')
            if errors:
                messages.error(request, f'{len(errors)} row(s) skipped: ' + ' | '.join(errors))
            if not created and not errors:
                messages.error(request, 'No user rows found in the pasted text.')
            return redirect('tracker:admin_users')

        target_id = request.POST.get('target_user_id')
        target = User.objects.filter(pk=target_id).first()
        if not target:
            messages.error(request, 'Select a valid user for this action.')
            return redirect('tracker:admin_users')

        if action == 'change_password':
            form = ChangePasswordForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please enter a new password.')
                return redirect('tracker:admin_users')
            target.password = form.cleaned_data['new_password']
            target.save()
            messages.success(request, f'Password updated for {target.email}.')
            return redirect('tracker:admin_users')

        if action == 'change_role':
            form = ChangeRoleForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please select a role.')
                return redirect('tracker:admin_users')
            target.role = form.cleaned_data['role']
            target.save()
            messages.success(request, f'Role updated for {target.email}.')
            return redirect('tracker:admin_users')

        # activate / deactivate
        if action == 'deactivate' and target.pk == request.user.pk:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('tracker:admin_users')
        target.status = 'active' if action == 'activate' else 'inactive'
        target.save()
        messages.success(request, f"{target.email} {'activated' if action == 'activate' else 'deactivated'}.")
        return redirect('tracker:admin_users')


class AdminReportsView(AdminRequiredMixin, TemplateView):
    """Admin-only: status-distribution and component-failure charts,
    rendered as simple percentage-of-max bar lists (no charting library)."""

    template_name = 'tracker/admin_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_section'] = 'reports'

        status_counts = Counter(DispatchItem.objects.values_list('status', flat=True))
        status_labels = dict(DispatchItem.STATUS_CHOICES)
        max_status_count = max(status_counts.values(), default=1)
        context['status_bars'] = sorted(
            (
                {
                    'label': status_labels.get(status, status),
                    'count': count,
                    'percent': round(count / max_status_count * 100),
                }
                for status, count in status_counts.items()
            ),
            key=lambda bar: bar['count'],
            reverse=True,
        )

        sub_category_counts = Counter()
        for value in DispatchItem.objects.exclude(electronics_sub_category__isnull=True).exclude(
            electronics_sub_category=''
        ).values_list('electronics_sub_category', flat=True):
            for part in value.split(', '):
                part = part.strip()
                if part:
                    sub_category_counts[part] += 1
        max_sub_category_count = max(sub_category_counts.values(), default=1)
        context['component_bars'] = sorted(
            (
                {'label': label, 'count': count, 'percent': round(count / max_sub_category_count * 100)}
                for label, count in sub_category_counts.items()
            ),
            key=lambda bar: bar['count'],
            reverse=True,
        )
        return context


class AdminMaterialLookupView(AdminRequiredMixin, TemplateView):
    """Admin-only: search by service ID / machine no / faulty serial, and
    see a material's full status history from dispatch to final remark."""

    template_name = 'tracker/admin_lookup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_section'] = 'lookup'
        query = self.request.GET.get('q', '').strip()
        context['query'] = query
        if query:
            context['results'] = (
                DispatchItem.objects.filter(
                    Q(service_id__icontains=query)
                    | Q(controller_serial__icontains=query)
                    | Q(faulty_serial__icontains=query)
                )
                .select_related('dispatch', 'dispatch__destination', 'forward_dispatch__destination')
                .prefetch_related('status_events', 'status_events__changed_by')
                .order_by('-created_at')
            )
            # A material an engineer has logged but not yet dispatched has no
            # DispatchItem row at all -- only the query above matched -- so
            # it'd otherwise never show up in a lookup search.
            needle = query.lower()
            context['pending_results'] = [
                line for line in get_material_lines_for_engineer()
                if not line.is_dispatched and (
                    needle in line.service_id.lower()
                    or needle in (line.controller_serial or '').lower()
                    or needle in (line.faulty_serial or '').lower()
                )
            ]
        else:
            context['results'] = []
            context['pending_results'] = []
        return context


class EngineerHomeView(LoginRequiredMixin, TemplateView):
    """Main page: lists the logged-in engineer's replaced materials,
    labeled pending/dispatched, with a dispatch action for pending ones."""

    template_name = 'tracker/engineer_home.html'
    login_url = 'tracker:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['material_lines'] = get_material_lines_for_engineer(self.request.user.email)
        context['delivery_partners'] = DeliveryPartner.objects.filter(is_active=True)
        context['destinations'] = DispatchLocation.objects.filter(is_active=True)
        return context


class RegionalWarehouseHomeView(LoginRequiredMixin, TemplateView):
    """Read-only page: lists materials dispatched to this warehouse user's
    location. Matched by name against DispatchLocation (no explicit link
    exists yet between a regwarehouse user account and a location)."""

    template_name = 'tracker/warehouse_home.html'
    login_url = 'tracker:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location = DispatchLocation.objects.filter(name__iexact=self.request.user.name).first()
        if location:
            items = (
                DispatchItem.objects.filter(dispatch__destination=location)
                .select_related('dispatch', 'dispatch__delivery_partner', 'forward_dispatch__destination')
                .order_by('-dispatch__dispatched_at')
            )
        else:
            items = DispatchItem.objects.none()
        context['location'] = location
        context['incoming_items'] = items
        context['delivery_partners'] = DeliveryPartner.objects.filter(is_active=True)
        context['warehouse_destinations'] = DispatchLocation.objects.filter(
            is_active=True, location_type=DispatchLocation.WAREHOUSE
        )
        context['motor_capacity_choices'] = MOTOR_CAPACITY_CHOICES
        context['motor_surface_oem_choices'] = MOTOR_SURFACE_OEM_CHOICES
        context['submersible_oem_choices'] = SUBMERSIBLE_PUMP_OEM_CHOICES
        context['motor_head_size_choices'] = MOTOR_HEAD_SIZE_CHOICES
        context['motor_inch_size_choices'] = MOTOR_INCH_SIZE_CHOICES
        return context


def _missing_courier_fields(form):
    """Pickup/LR/challan are only actually required for a courier dispatch,
    not a By Hand one -- used by both DispatchSubmitView (engineer) and
    WarehouseActionView (regional warehouse forward) after their form's own
    validation, which leaves these optional so a By Hand submission passes."""
    return [
        label
        for field, label in (
            ('pickup_number', 'Pickup number'),
            ('lr_number', 'LR number'),
            ('delivery_challan_number', 'Delivery challan number'),
        )
        if not form.cleaned_data.get(field, '').strip()
    ]


def _motor_receive_form(post_data):
    """Builds a MotorReceiveForm from its dialog's uniquely-prefixed field
    names ('motor_capacity', etc) -- every dialog's fields live on one
    shared <form> via form="action-form", so names can't collide."""
    return MotorReceiveForm({
        'received_date': post_data.get('motor_received_date', ''),
        'capacity': post_data.get('motor_capacity', ''),
        'oem_name': post_data.get('motor_oem_name', ''),
        'head_size': post_data.get('motor_head_size', ''),
        'inch_size': post_data.get('motor_inch_size', ''),
        'remarks': post_data.get('motor_receive_remarks', ''),
    })


class WarehouseActionView(LoginRequiredMixin, View):
    """Handles a regional warehouse acting on one or more incoming items:
    Tested OK / Repaired / Dispatched to OEM / Scrapped (status + remarks
    only), Dispatch (forward onward, a full second shipment), or one of two
    receive checklists that must be completed before any other action
    applies -- Receive (date + serial match, for a card) or Receive
    Motor/Pump (capacity/OEM/head/inch/fault) -- see
    DispatchItem.is_pending_card_receive / is_pending_motor_receive."""

    login_url = 'tracker:login'

    SIMPLE_ACTIONS = {'tested_ok', 'repaired', 'dispatched_to_oem', 'scrapped'}
    CARD_ACTIONS = {'dispatch_forward', 'tested_ok'}
    MOTOR_ACTIONS = {'dispatch_forward', 'repaired', 'dispatched_to_oem', 'scrapped'}

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_pks = request.POST.getlist('selected_items')

        location = DispatchLocation.objects.filter(name__iexact=request.user.name).first()
        if not location:
            messages.error(request, 'No warehouse location is set up for your account.')
            return redirect('tracker:warehouse_home')

        # Only items destined to this user's own location and still awaiting
        # action can be touched -- prevents acting on someone else's items
        # or re-actioning something already processed.
        items = list(
            DispatchItem.objects.filter(
                pk__in=selected_pks, dispatch__destination=location, status='dispatched'
            )
        )
        if not items:
            messages.error(request, 'Select at least one incoming material to act on.')
            return redirect('tracker:warehouse_home')

        if action == 'receive':
            items = [item for item in items if item.is_pending_card_receive]
            if not items:
                messages.error(request, 'Select at least one incoming card to receive.')
                return redirect('tracker:warehouse_home')
            receive_data = request.POST.copy()
            receive_data['remarks'] = request.POST.get('receive_remarks', '')
            form = ReceiveMaterialForm(receive_data)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the receive form.')
                return redirect('tracker:warehouse_home')
            DispatchItem.objects.filter(pk__in=[item.pk for item in items]).update(
                received_date=form.cleaned_data['received_date'],
                received_serial_matches=form.cleaned_data['serial_matches'] == 'yes',
                received_serial_no=form.cleaned_data['received_serial_no'],
                warehouse_reservation_no=form.cleaned_data['reservation_no'],
                status_remarks=form.cleaned_data['remarks'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            messages.success(request, f'Received {len(items)} item(s).')
            return redirect('tracker:warehouse_home')

        if action == 'receive_motor':
            items = [item for item in items if item.is_pending_motor_receive]
            if not items:
                messages.error(request, 'Select at least one incoming motor/pump to receive.')
                return redirect('tracker:warehouse_home')
            form = _motor_receive_form(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the receive form.')
                return redirect('tracker:warehouse_home')
            DispatchItem.objects.filter(pk__in=[item.pk for item in items]).update(
                received_date=form.cleaned_data['received_date'],
                motor_capacity=form.cleaned_data['capacity'],
                motor_oem_name=form.cleaned_data['oem_name'],
                motor_head_size=form.cleaned_data['head_size'],
                motor_inch_size=form.cleaned_data['inch_size'],
                status_remarks=form.cleaned_data['remarks'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            messages.success(request, f'Received {len(items)} item(s).')
            return redirect('tracker:warehouse_home')

        for item in items:
            allowed = self.MOTOR_ACTIONS if item.is_motor_or_pump else self.CARD_ACTIONS
            if action not in allowed:
                messages.error(request, 'That action is not valid for one or more selected materials.')
                return redirect('tracker:warehouse_home')
            if item.is_motor_or_pump and item.is_pending_motor_receive:
                messages.error(request, 'Receive this motor/pump before choosing an action.')
                return redirect('tracker:warehouse_home')
            if item.is_pending_card_receive:
                messages.error(request, 'Receive this card before choosing an action.')
                return redirect('tracker:warehouse_home')

        item_pks = [item.pk for item in items]

        if action in self.SIMPLE_ACTIONS:
            # Named differently from the forward-dialog's own `remarks` field
            # since both dialogs' inputs are attached to the same <form>.
            form = WarehouseRemarksForm({'remarks': request.POST.get('simple_remarks', '')})
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the form.')
                return redirect('tracker:warehouse_home')
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status=action,
                status_remarks=form.cleaned_data['remarks'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            for item in items:
                record_status_event(item, action, form.cleaned_data['remarks'], request.user)
            messages.success(request, f'Updated {len(items)} item(s).')
            return redirect('tracker:warehouse_home')

        if action == 'dispatch_forward':
            post_data = request.POST.copy()
            is_by_hand = post_data.get('delivery_partner') == 'by_hand'
            if is_by_hand:
                post_data['delivery_partner'] = ''
                post_data['custom_delivery_partner'] = 'By Hand'
            elif post_data.get('delivery_partner') == 'other':
                post_data['delivery_partner'] = ''
            form = ForwardDispatchForm(post_data)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the forward dispatch form.')
                return redirect('tracker:warehouse_home')

            # Pickup/LR/challan numbers only matter when a courier is
            # actually involved -- a By Hand dispatch skips straight to the
            # destination warehouse (mirrors DispatchSubmitView).
            if not is_by_hand:
                missing = _missing_courier_fields(form)
                if missing:
                    messages.error(request, f'{", ".join(missing)} required unless dispatching by hand.')
                    return redirect('tracker:warehouse_home')

            delivery_partner = resolve_delivery_partner(form.cleaned_data)

            with transaction.atomic():
                new_dispatch = Dispatch.objects.create(
                    dispatched_by=request.user,
                    pickup_number=form.cleaned_data['pickup_number'],
                    lr_number=form.cleaned_data['lr_number'],
                    delivery_challan_number=form.cleaned_data['delivery_challan_number'],
                    delivery_partner=delivery_partner,
                    destination=form.cleaned_data['destination'],
                    remarks=form.cleaned_data['remarks'],
                )
                DispatchItem.objects.filter(pk__in=item_pks).update(
                    status='dispatched_to_warehouse',
                    forward_dispatch=new_dispatch,
                    status_updated_by=request.user,
                    status_updated_at=timezone.now(),
                )
                for item in items:
                    record_status_event(
                        item, 'dispatched_to_warehouse', form.cleaned_data['remarks'], request.user
                    )
            messages.success(request, f'Forwarded {len(items)} item(s) to {new_dispatch.destination.name}.')
            return redirect('tracker:warehouse_home')

        messages.error(request, 'Unknown action.')
        return redirect('tracker:warehouse_home')


def _get_main_warehouse_items():
    """Every item currently or previously addressed to a Warehouse-type
    location -- shared across all 'warehouse' role users (there is no
    per-user location like regional warehouse has)."""
    return (
        DispatchItem.objects.filter(
            Q(dispatch__destination__location_type=DispatchLocation.WAREHOUSE)
            | Q(forward_dispatch__destination__location_type=DispatchLocation.WAREHOUSE)
        )
        .select_related('dispatch', 'dispatch__delivery_partner', 'dispatch__destination', 'forward_dispatch__destination')
        .order_by('-dispatch__dispatched_at')
    )


class MainWarehouseHomeView(LoginRequiredMixin, TemplateView):
    """Read-only page: lists every material addressed to a Warehouse-type
    location (direct from an engineer, or forwarded by a regional
    warehouse). Shared across all 'warehouse' role users."""

    template_name = 'tracker/main_warehouse_home.html'
    login_url = 'tracker:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['incoming_items'] = _get_main_warehouse_items()
        context['motor_capacity_choices'] = MOTOR_CAPACITY_CHOICES
        context['motor_surface_oem_choices'] = MOTOR_SURFACE_OEM_CHOICES
        context['submersible_oem_choices'] = SUBMERSIBLE_PUMP_OEM_CHOICES
        context['motor_head_size_choices'] = MOTOR_HEAD_SIZE_CHOICES
        context['motor_inch_size_choices'] = MOTOR_INCH_SIZE_CHOICES
        return context


class MainWarehouseActionView(LoginRequiredMixin, View):
    """Handles a warehouse user acting on one or more items:

    - Receive: the initial check-in for Power Card / Control Card / RMU
      material -- records the receive date and whether the physical serial
      matches the ticket on file, then hands off to Service Desk.
    - Dispatch to OEM: motors/pumps go straight to the OEM for repair
      instead of through Service Desk / Electronics. A P-serial Power/
      Control Card (see DispatchItem.is_p_serial_card) takes the same
      shortcut, but only after being received -- see card_dispatch_to_oem/
      card_scrap below.
    - Add to Stock: closes the loop once Electronics has repaired an item
      and sent it back -- marks it added to the service stock.
    - Receive Motor/Pump: the motor/pump equivalent of Receive -- a
      capacity/OEM/head/inch/fault checklist instead of a serial-match
      check. Doesn't change status; it only unlocks the OEM/Scrap/Repaired
      decision below (see DispatchItem.is_pending_motor_receive).
    """

    login_url = 'tracker:login'

    ACTIONS = {
        'receive', 'receive_motor', 'dispatch_to_oem', 'scrap', 'repaired',
        'card_dispatch_to_oem', 'card_scrap', 'add_to_stock',
    }

    def _eligible_items(self, action, selected_pks):
        candidates = _get_main_warehouse_items().filter(pk__in=selected_pks)
        if action == 'receive':
            return [
                item for item in candidates
                if item.is_pending_for_main_warehouse and not item.is_motor_or_pump
            ]
        if action == 'receive_motor':
            return [
                item for item in candidates
                if item.is_pending_for_main_warehouse and item.is_pending_motor_receive
            ]
        if action in ('dispatch_to_oem', 'scrap', 'repaired'):
            return [
                item for item in candidates
                if item.is_pending_for_main_warehouse and item.is_motor_or_pump and item.received_date
            ]
        if action in ('card_dispatch_to_oem', 'card_scrap'):
            return [item for item in candidates if item.is_pending_oem_scrap_decision]
        if action == 'add_to_stock':
            return [item for item in candidates if item.is_pending_stock_entry]
        return []

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_pks = request.POST.getlist('selected_items')

        if action not in self.ACTIONS:
            messages.error(request, 'Unknown action.')
            return redirect('tracker:main_warehouse_home')

        # Recomputed server-side from the same base queryset the home page
        # uses, so a tampered request can't act on an item never addressed
        # to a warehouse, one not eligible for this particular action, or
        # one someone else has already moved on.
        items = self._eligible_items(action, selected_pks)
        if not items:
            messages.error(request, 'Select at least one eligible material for this action.')
            return redirect('tracker:main_warehouse_home')

        item_pks = [item.pk for item in items]

        if action == 'receive':
            receive_data = request.POST.copy()
            receive_data['remarks'] = request.POST.get('receive_remarks', '')
            form = ReceiveMaterialForm(receive_data)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the receive form.')
                return redirect('tracker:main_warehouse_home')
            remarks = form.cleaned_data['remarks']
            common_fields = dict(
                received_date=form.cleaned_data['received_date'],
                received_serial_matches=form.cleaned_data['serial_matches'] == 'yes',
                received_serial_no=form.cleaned_data['received_serial_no'],
                warehouse_reservation_no=form.cleaned_data['reservation_no'],
                status_remarks=remarks,
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )

            # P-serial Power/Control Cards skip Service Desk/Electronics
            # entirely -- straight to an OEM/Scrap decision instead.
            card_items = [item for item in items if item.is_p_serial_card]
            other_items = [item for item in items if not item.is_p_serial_card]

            if card_items:
                DispatchItem.objects.filter(pk__in=[item.pk for item in card_items]).update(
                    status='pending_oem_scrap', **common_fields
                )
                for item in card_items:
                    record_status_event(item, 'pending_oem_scrap', remarks, request.user)
            if other_items:
                DispatchItem.objects.filter(pk__in=[item.pk for item in other_items]).update(
                    status='with_service_desk', **common_fields
                )
                for item in other_items:
                    record_status_event(item, 'with_service_desk', remarks, request.user)

            if card_items and other_items:
                messages.success(
                    request,
                    f'Received {len(items)} item(s): {len(other_items)} assigned to Service Desk, '
                    f'{len(card_items)} flagged for an OEM/Scrap decision.',
                )
            elif card_items:
                messages.success(request, f'Received {len(items)} item(s), flagged for an OEM/Scrap decision.')
            else:
                messages.success(request, f'Received {len(items)} item(s) and assigned to Service Desk.')
            return redirect('tracker:main_warehouse_home')

        if action == 'receive_motor':
            form = _motor_receive_form(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the receive form.')
                return redirect('tracker:main_warehouse_home')
            DispatchItem.objects.filter(pk__in=item_pks).update(
                received_date=form.cleaned_data['received_date'],
                motor_capacity=form.cleaned_data['capacity'],
                motor_oem_name=form.cleaned_data['oem_name'],
                motor_head_size=form.cleaned_data['head_size'],
                motor_inch_size=form.cleaned_data['inch_size'],
                status_remarks=form.cleaned_data['remarks'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            messages.success(request, f'Received {len(items)} item(s).')
            return redirect('tracker:main_warehouse_home')

        if action == 'repaired':
            form = WarehouseRemarksForm({'remarks': request.POST.get('simple_remarks', '')})
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the form.')
                return redirect('tracker:main_warehouse_home')
            remarks = form.cleaned_data['remarks']
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status='repaired',
                status_remarks=remarks,
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            for item in items:
                record_status_event(item, 'repaired', remarks, request.user)
            messages.success(request, f'Marked {len(items)} item(s) repaired.')
            return redirect('tracker:main_warehouse_home')

        if action in ('dispatch_to_oem', 'scrap'):
            motor_data = request.POST.copy()
            motor_data['remarks'] = request.POST.get('motor_remarks', '')
            form = MotorDispositionForm(motor_data)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the form.')
                return redirect('tracker:main_warehouse_home')

            new_status = 'dispatched_to_oem' if action == 'dispatch_to_oem' else 'scrapped'
            remarks = form.cleaned_data['remarks']
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status=new_status,
                status_remarks=remarks,
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
                oem_inward_reservation_no=form.cleaned_data['inward_reservation_no'],
                oem_outward_reservation_no=form.cleaned_data['outward_reservation_no'],
            )
            for item in items:
                record_status_event(item, new_status, remarks, request.user)
            messages.success(request, f'Updated {len(items)} item(s).')
            return redirect('tracker:main_warehouse_home')

        if action == 'card_dispatch_to_oem':
            form = CardOemDispatchForm({
                'lr_no': request.POST.get('card_oem_lr_no', ''),
                'challan_no': request.POST.get('card_oem_challan_no', ''),
                'outward_reservation_no': request.POST.get('card_oem_outward_reservation_no', ''),
            })
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the form.')
                return redirect('tracker:main_warehouse_home')

            DispatchItem.objects.filter(pk__in=item_pks).update(
                status='dispatched_to_oem',
                oem_dispatch_lr_no=form.cleaned_data['lr_no'],
                oem_dispatch_challan_no=form.cleaned_data['challan_no'],
                oem_outward_reservation_no=form.cleaned_data['outward_reservation_no'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            for item in items:
                record_status_event(item, 'dispatched_to_oem', '', request.user)
            messages.success(request, f'Dispatched {len(items)} item(s) to OEM.')
            return redirect('tracker:main_warehouse_home')

        if action == 'card_scrap':
            form = CardScrapForm({
                'condition': request.POST.get('card_scrap_condition', ''),
                'remarks': request.POST.get('card_scrap_remarks', ''),
                'outward_reservation_no': request.POST.get('card_scrap_outward_reservation_no', ''),
            })
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the form.')
                return redirect('tracker:main_warehouse_home')

            remarks = form.cleaned_data['remarks']
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status='scrapped',
                scrap_condition=form.cleaned_data['condition'],
                oem_outward_reservation_no=form.cleaned_data['outward_reservation_no'],
                status_remarks=remarks,
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            for item in items:
                record_status_event(item, 'scrapped', remarks, request.user)
            messages.success(request, f'Scrapped {len(items)} item(s).')
            return redirect('tracker:main_warehouse_home')

        # add_to_stock also captures the outward reservation number it's
        # issued against, so uses its own form rather than WarehouseRemarksForm
        # (shared with the regional warehouse's plain status-only actions).
        form = AddToStockForm({
            'outward_reservation_no': request.POST.get('stock_outward_reservation_no', ''),
            'remarks': request.POST.get('simple_remarks', ''),
        })
        if not form.is_valid():
            messages.error(request, 'Please correct the errors in the form.')
            return redirect('tracker:main_warehouse_home')

        remarks = form.cleaned_data['remarks']
        DispatchItem.objects.filter(pk__in=item_pks).update(
            status='added_to_stock',
            stock_outward_reservation_no=form.cleaned_data['outward_reservation_no'],
            status_remarks=remarks,
            status_updated_by=request.user,
            status_updated_at=timezone.now(),
        )
        for item in items:
            record_status_event(item, 'added_to_stock', remarks, request.user)
        messages.success(request, f'Updated {len(items)} item(s).')
        return redirect('tracker:main_warehouse_home')


class ServiceDeskHomeView(LoginRequiredMixin, TemplateView):
    """Read-only page: every item that has ever reached Service Desk,
    shared across all 'servicedesk' role users."""

    template_name = 'tracker/service_desk_home.html'
    login_url = 'tracker:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['incoming_items'] = get_service_desk_items()
        return context


class ServiceDeskActionView(LoginRequiredMixin, View):
    """Handles Service Desk inspecting one or more items and assigning
    them onward to Electronics."""

    login_url = 'tracker:login'

    def post(self, request, *args, **kwargs):
        selected_pks = request.POST.getlist('selected_items')

        items = [
            item for item in get_service_desk_items().filter(pk__in=selected_pks)
            if item.is_pending_for_service_desk
        ]
        if not items:
            messages.error(request, 'Select at least one item awaiting inspection.')
            return redirect('tracker:service_desk_home')

        form = ElectronicsAssignmentForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Please complete the inspection checklist.')
            return redirect('tracker:service_desk_home')

        data = form.cleaned_data
        item_pks = [item.pk for item in items]
        DispatchItem.objects.filter(pk__in=item_pks).update(
            status='with_electronics',
            status_remarks=data['remarks'],
            status_updated_by=request.user,
            status_updated_at=timezone.now(),
            inspection_problem=data['problem'],
            inspection_visual_done=data['visual_inspection_done'] == 'yes',
            inspection_mtr_test_passed=data['mtr_test'] == 'passed',
            inspection_cold_test_passed=data['cold_test'] == 'passed',
            inspection_wiring_repaired=data['wiring'] == 'repaired',
        )
        for item in items:
            record_status_event(item, 'with_electronics', data['remarks'], request.user)
        messages.success(request, f'Assigned {len(items)} item(s) to Electronics.')
        return redirect('tracker:service_desk_home')


class ElectronicsHomeView(LoginRequiredMixin, TemplateView):
    """Read-only page: every item that has ever reached Electronics,
    shared across all 'electronics' role users."""

    template_name = 'tracker/electronics_home.html'
    login_url = 'tracker:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['incoming_items'] = get_electronics_items()
        context['proceed_form'] = ElectronicsProceedForm()
        return context


class ElectronicsActionView(LoginRequiredMixin, View):
    """Handles Electronics acting on one or more items:

    - Proceed: fills in the diagnostic checklist and records a diagnosis
      (Repaired OK / Tested OK / Scrapped), moving the item to Completed.
    - Send Back to Warehouse / Scrap: a later, separate action on an
      already-diagnosed (Completed) item -- captures the outward
      reservation number and performs the actual disposition. Which of the
      two applies is determined by the diagnosis (see
      DispatchItem.electronics_action_group), and re-checked here against
      a tampered request the same way the warehouse views do.
    """

    login_url = 'tracker:login'

    ACTIONS = {'proceed', 'send_to_warehouse', 'scrap'}

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        selected_pks = request.POST.getlist('selected_items')

        if action not in self.ACTIONS:
            messages.error(request, 'Unknown action.')
            return redirect('tracker:electronics_home')

        candidates = get_electronics_items().filter(pk__in=selected_pks)
        if action == 'proceed':
            items = [item for item in candidates if item.is_pending_for_electronics]
        else:
            items = [item for item in candidates if item.is_electronics_completed]
        if not items:
            messages.error(request, 'Select at least one eligible material for this action.')
            return redirect('tracker:electronics_home')

        item_pks = [item.pk for item in items]

        if action == 'proceed':
            form = ElectronicsProceedForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please complete the checklist.')
                return redirect('tracker:electronics_home')

            data = form.cleaned_data
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status='electronics_completed',
                status_remarks=data['remarks'],
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
                electronics_engineer_name=data['electronics_engineer_name'],
                electronics_physical_visual_damage=', '.join(data['physical_visual_damage']),
                electronics_component_status=', '.join(data['component_status']),
                electronics_power_electrical_faults=', '.join(data['power_electrical_faults']),
                electronics_system_display_behavior=', '.join(data['system_display_behavior']),
                electronics_pcb_type=data['pcb_type'],
                electronics_pcb_issue=data['pcb_issue'],
                electronics_failure_category=data['failure_category'],
                electronics_sub_category=', '.join(data['sub_category']),
                electronics_igbt_pin_status=data['igbt_pin_status'],
                electronics_component_change=data['component_change'],
                electronics_test_machine_info=data['test_machine_info'],
                electronics_tested_date=data['tested_date'],
                electronics_final_remark=data['final_remark'],
            )
            for item in items:
                record_status_event(item, 'electronics_completed', data['remarks'], request.user)
            messages.success(request, f'Completed diagnosis for {len(items)} item(s).')
            return redirect('tracker:electronics_home')

        # send_to_warehouse / scrap -- only valid for items whose diagnosis
        # matches the button clicked.
        expected_group = 'scrap' if action == 'scrap' else 'send_to_warehouse'
        if any(item.electronics_action_group != expected_group for item in items):
            messages.error(request, 'One or more selected items are not eligible for that action.')
            return redirect('tracker:electronics_home')

        form = ElectronicsDispositionForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Please enter the outward reservation number.')
            return redirect('tracker:electronics_home')

        new_status = 'scrapped' if action == 'scrap' else 'repaired_by_electronics'
        DispatchItem.objects.filter(pk__in=item_pks).update(
            status=new_status,
            electronics_outward_reservation_no=form.cleaned_data['outward_reservation_no'],
            status_updated_by=request.user,
            status_updated_at=timezone.now(),
        )
        for item in items:
            record_status_event(item, new_status, '', request.user)
        messages.success(request, f'Updated {len(items)} item(s).')
        return redirect('tracker:electronics_home')


class DispatchSubmitView(LoginRequiredMixin, View):
    """Handles the dispatch form submission from the engineer's main page."""

    login_url = 'tracker:login'

    def post(self, request, *args, **kwargs):
        selected_keys = request.POST.getlist('selected_items')

        post_data = request.POST.copy()
        is_by_hand = post_data.get('delivery_partner') == 'by_hand'
        if is_by_hand:
            post_data['delivery_partner'] = ''
            post_data['custom_delivery_partner'] = 'By Hand'
        elif post_data.get('delivery_partner') == 'other':
            post_data['delivery_partner'] = ''
        form = DispatchForm(post_data)

        if not selected_keys:
            messages.error(request, 'Select at least one material to dispatch.')
            return redirect('tracker:engineer_home')

        if not form.is_valid():
            messages.error(request, 'Please correct the errors in the dispatch form.')
            return redirect('tracker:engineer_home')

        # Pickup/LR/challan numbers only matter when a courier is actually
        # involved -- a By Hand dispatch skips straight to the warehouse.
        if not is_by_hand:
            missing = _missing_courier_fields(form)
            if missing:
                messages.error(request, f'{", ".join(missing)} required unless dispatching by hand.')
                return redirect('tracker:engineer_home')

        # Recompute the engineer's own pending lines server-side so a
        # tampered request can never dispatch someone else's material or
        # re-dispatch an already-dispatched one.
        lines_by_key = {
            line.key: line
            for line in get_material_lines_for_engineer(request.user.email)
            if not line.is_dispatched
        }
        items_to_create = [
            lines_by_key[key] for key in selected_keys if key in lines_by_key
        ]

        if not items_to_create:
            messages.error(request, 'Selected materials are no longer available to dispatch.')
            return redirect('tracker:engineer_home')

        delivery_partner = resolve_delivery_partner(form.cleaned_data)

        try:
            with transaction.atomic():
                dispatch = Dispatch.objects.create(
                    dispatched_by=request.user,
                    pickup_number=form.cleaned_data['pickup_number'],
                    lr_number=form.cleaned_data['lr_number'],
                    delivery_challan_number=form.cleaned_data['delivery_challan_number'],
                    delivery_partner=delivery_partner,
                    destination=form.cleaned_data['destination'],
                    remarks=form.cleaned_data['remarks'],
                )
                # Created one by one (not bulk_create) so each instance gets
                # its real pk back -- MySQL doesn't return generated ids for
                # a multi-row bulk insert, and record_status_event below
                # needs a valid item pk to log against.
                created_items = [
                    DispatchItem.objects.create(
                        dispatch=dispatch,
                        service_id=line.service_id,
                        part_type=line.part_type,
                        faulty_serial=line.faulty_serial,
                        material_name=line.material_name,
                        problem=line.problem or '',
                        controller_serial=line.controller_serial,
                        si_details=line.si_details,
                        farmer_name=line.farmer_name,
                        location=line.location,
                        service_person_name=line.service_person_name,
                        replacement_date=line.replacement_date,
                    )
                    for line in items_to_create
                ]
                for item in created_items:
                    record_status_event(item, 'dispatched', '', request.user)
        except IntegrityError:
            messages.error(request, 'One or more selected materials were already dispatched. Please refresh and try again.')
            return redirect('tracker:engineer_home')

        messages.success(request, f'Dispatched {len(items_to_create)} item(s) successfully.')
        return redirect('tracker:engineer_home')
