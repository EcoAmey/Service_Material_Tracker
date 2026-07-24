from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from .forms import (
    DispatchForm,
    ElectronicsAssignmentForm,
    ElectronicsProceedForm,
    ForwardDispatchForm,
    MotorDispositionForm,
    ReceiveMaterialForm,
    WarehouseRemarksForm,
)
from .models import DeliveryPartner, Dispatch, DispatchItem, DispatchLocation
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
        if request.user.role == 'regwarehouse':
            return redirect('tracker:warehouse_home')
        if request.user.role == 'warehouse':
            return redirect('tracker:main_warehouse_home')
        if request.user.role == 'servicedesk':
            return redirect('tracker:service_desk_home')
        if request.user.role == 'electronics':
            return redirect('tracker:electronics_home')
        return redirect('tracker:engineer_home')


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
        return context


class WarehouseActionView(LoginRequiredMixin, View):
    """Handles a regional warehouse acting on one or more incoming items:
    Tested OK / Repaired / Dispatched to OEM (status + remarks only), or
    Dispatch (forward onward, a full second shipment)."""

    login_url = 'tracker:login'

    SIMPLE_ACTIONS = {'tested_ok', 'repaired', 'dispatched_to_oem'}
    CARD_ACTIONS = {'dispatch_forward', 'tested_ok'}
    MOTOR_ACTIONS = {'dispatch_forward', 'repaired', 'dispatched_to_oem'}

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

        for item in items:
            allowed = self.MOTOR_ACTIONS if item.is_motor_or_pump else self.CARD_ACTIONS
            if action not in allowed:
                messages.error(request, 'That action is not valid for one or more selected materials.')
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
            if post_data.get('delivery_partner') == 'other':
                post_data['delivery_partner'] = ''
            form = ForwardDispatchForm(post_data)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the forward dispatch form.')
                return redirect('tracker:warehouse_home')

            delivery_partner = form.cleaned_data['delivery_partner']
            custom_partner_name = form.cleaned_data['custom_delivery_partner'].strip()
            if not delivery_partner and custom_partner_name:
                delivery_partner, _ = DeliveryPartner.objects.get_or_create(name=custom_partner_name)

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
        return context


class MainWarehouseActionView(LoginRequiredMixin, View):
    """Handles a warehouse user acting on one or more items:

    - Receive: the initial check-in for Power Card / Control Card / RMU
      material -- records the receive date and whether the physical serial
      matches the ticket on file, then hands off to Service Desk.
    - Dispatch to OEM: motors/pumps go straight to the OEM for repair
      instead of through Service Desk / Electronics.
    - Add to Stock: closes the loop once Electronics has repaired an item
      and sent it back -- marks it added to the service stock.
    """

    login_url = 'tracker:login'

    ACTIONS = {'receive', 'dispatch_to_oem', 'scrap', 'add_to_stock'}

    def _eligible_items(self, action, selected_pks):
        candidates = _get_main_warehouse_items().filter(pk__in=selected_pks)
        if action == 'receive':
            return [
                item for item in candidates
                if item.is_pending_for_main_warehouse and not item.is_motor_or_pump
            ]
        if action in ('dispatch_to_oem', 'scrap'):
            return [
                item for item in candidates
                if item.is_pending_for_main_warehouse and item.is_motor_or_pump
            ]
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
            form = ReceiveMaterialForm(request.POST)
            if not form.is_valid():
                messages.error(request, 'Please correct the errors in the receive form.')
                return redirect('tracker:main_warehouse_home')
            remarks = form.cleaned_data['remarks']
            DispatchItem.objects.filter(pk__in=item_pks).update(
                status='with_service_desk',
                received_date=form.cleaned_data['received_date'],
                received_serial_matches=form.cleaned_data['serial_matches'] == 'yes',
                received_serial_no=form.cleaned_data['received_serial_no'],
                warehouse_reservation_no=form.cleaned_data['reservation_no'],
                status_remarks=remarks,
                status_updated_by=request.user,
                status_updated_at=timezone.now(),
            )
            for item in items:
                record_status_event(item, 'with_service_desk', remarks, request.user)
            messages.success(request, f'Received {len(items)} item(s) and assigned to Service Desk.')
            return redirect('tracker:main_warehouse_home')

        if action in ('dispatch_to_oem', 'scrap'):
            form = MotorDispositionForm(request.POST)
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

        # add_to_stock is a simple status + remarks update.
        form = WarehouseRemarksForm({'remarks': request.POST.get('simple_remarks', '')})
        if not form.is_valid():
            messages.error(request, 'Please correct the errors in the form.')
            return redirect('tracker:main_warehouse_home')

        remarks = form.cleaned_data['remarks']
        DispatchItem.objects.filter(pk__in=item_pks).update(
            status='added_to_stock',
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
            inspection_reservation_no=data['reservation_no'],
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
    """Handles Electronics proceeding on one or more items: fills in the
    diagnostic checklist and decides Tested OK (sent back to the warehouse
    for stock) or Scrapped (terminal)."""

    login_url = 'tracker:login'

    def post(self, request, *args, **kwargs):
        selected_pks = request.POST.getlist('selected_items')

        items = [
            item for item in get_electronics_items().filter(pk__in=selected_pks)
            if item.is_pending_for_electronics
        ]
        if not items:
            messages.error(request, 'Select at least one item awaiting a decision.')
            return redirect('tracker:electronics_home')

        form = ElectronicsProceedForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Please complete the checklist.')
            return redirect('tracker:electronics_home')

        data = form.cleaned_data
        new_status = 'repaired_by_electronics' if data['outcome'] == 'tested_ok' else 'scrapped'
        item_pks = [item.pk for item in items]
        DispatchItem.objects.filter(pk__in=item_pks).update(
            status=new_status,
            status_remarks=data['remarks'],
            status_updated_by=request.user,
            status_updated_at=timezone.now(),
            electronics_initial_observation=data['initial_observation'],
            electronics_pcb_type=data['pcb_type'],
            electronics_pcb_issue=data['pcb_issue'],
            electronics_failure_category=data['failure_category'],
            electronics_sub_category=data['sub_category'],
            electronics_igbt_pin_status=data['igbt_pin_status'],
            electronics_component_change=data['component_change'],
            electronics_test_machine_info=data['test_machine_info'],
            electronics_tested_date=data['tested_date'],
        )
        for item in items:
            record_status_event(item, new_status, data['remarks'], request.user)
        verb = 'Tested OK' if new_status == 'repaired_by_electronics' else 'Scrapped'
        messages.success(request, f'{verb}: {len(items)} item(s).')
        return redirect('tracker:electronics_home')


class DispatchSubmitView(LoginRequiredMixin, View):
    """Handles the dispatch form submission from the engineer's main page."""

    login_url = 'tracker:login'

    def post(self, request, *args, **kwargs):
        selected_keys = request.POST.getlist('selected_items')

        post_data = request.POST.copy()
        if post_data.get('delivery_partner') == 'other':
            post_data['delivery_partner'] = ''
        form = DispatchForm(post_data)

        if not selected_keys:
            messages.error(request, 'Select at least one material to dispatch.')
            return redirect('tracker:engineer_home')

        if not form.is_valid():
            messages.error(request, 'Please correct the errors in the dispatch form.')
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

        delivery_partner = form.cleaned_data['delivery_partner']
        custom_partner_name = form.cleaned_data['custom_delivery_partner'].strip()
        if not delivery_partner and custom_partner_name:
            delivery_partner, _ = DeliveryPartner.objects.get_or_create(name=custom_partner_name)

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
