from django.db import migrations


def backfill_status_events(apps, schema_editor):
    """Seed the new status-history log for items dispatched before this
    log existed, so reporting isn't missing their earliest known state.
    Best-effort: uses the original dispatch time for the initial
    'dispatched' entry, and status_updated_at/by for the current status
    if it has moved on since.
    """
    DispatchItem = apps.get_model('tracker', 'DispatchItem')
    DispatchItemStatusEvent = apps.get_model('tracker', 'DispatchItemStatusEvent')

    for item in DispatchItem.objects.select_related('dispatch').all():
        DispatchItemStatusEvent.objects.create(
            item=item,
            status='dispatched',
            remarks='',
            changed_by=item.dispatch.dispatched_by if item.dispatch_id else None,
            changed_at=item.dispatch.dispatched_at if item.dispatch_id else item.created_at,
        )
        if item.status != 'dispatched':
            DispatchItemStatusEvent.objects.create(
                item=item,
                status=item.status,
                remarks=item.status_remarks,
                changed_by=item.status_updated_by,
                changed_at=item.status_updated_at or item.created_at,
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_dispatchitem_received_date_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_status_events, noop_reverse),
    ]
