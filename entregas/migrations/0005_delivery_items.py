from django.db import migrations, models


def populate_delivery_items(apps, schema_editor):
    Delivery = apps.get_model('entregas', 'Delivery')
    updated = []
    for delivery in Delivery.objects.all().iterator():
        if not (delivery.product or delivery.amount):
            continue
        delivery.items = [{
            'product':        delivery.product or '',
            'amount':         delivery.amount or '',
            'product_ref_id': delivery.product_ref_id,
            'stock_items':    delivery.stock_items or {},
        }]
        updated.append(delivery)

    if updated:
        Delivery.objects.bulk_update(updated, ['items'])


class Migration(migrations.Migration):

    dependencies = [
        ('entregas', '0004_seed_catalogs'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='items',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(populate_delivery_items, migrations.RunPython.noop),
    ]
