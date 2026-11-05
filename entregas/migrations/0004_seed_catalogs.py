from django.db import migrations


MATERIALS = [
    ('LAV-8',     'Arena Lavanda',             'Bolsa 8kg',  '#f0e040'),
    ('LAV-20',    'Arena Lavanda',             'Bolsa 20kg', '#f0e040'),
    ('LAV-CA-8',  'Arena Lavanda + Carbón',    'Bolsa 8kg',  '#40c8f0'),
    ('LAV-CA-20', 'Arena Lavanda + Carbón',    'Bolsa 20kg', '#40c8f0'),
    ('CA-TB-20',  'Arena Carbón + Talco Bebé', 'Bolsa 20kg', '#f04090'),
    ('CAF-20',    'Bentonita Aroma Café',      'Bolsa 20kg', '#a66a3f'),
]

COMMERCIAL_PRODUCTS = [
    '8 k ca lav',
    '16 k ca lav',
    '20 k ca lav',
    '24 k ca lav',
    '28 k ca lav',
    '32 k ca lav',
    '40 k ca lav',
    '20 k ca tal',
    '40 k ca tal',
    '20 k ca café',
    '40 k ca café',
    '8 k lav',
    '16 k lav',
    '20 k lav',
    '24 k lav',
    '28 k lav',
    '32 k lav',
    '40 k lav',
]


def seed_catalogs(apps, schema_editor):
    Material = apps.get_model('entregas', 'Material')
    CommercialProduct = apps.get_model('entregas', 'CommercialProduct')
    Delivery = apps.get_model('entregas', 'Delivery')
    DailyStock = apps.get_model('entregas', 'DailyStock')

    for order, (sku, name, unit, color) in enumerate(MATERIALS):
        Material.objects.update_or_create(
            sku=sku,
            defaults={
                'name': name,
                'unit': unit,
                'color': color,
                'active': True,
                'sort_order': order,
            },
        )

    for order, label in enumerate(COMMERCIAL_PRODUCTS):
        CommercialProduct.objects.update_or_create(
            label=label,
            defaults={'active': True, 'sort_order': order},
        )

    historical_skus = set()
    for delivery in Delivery.objects.all().only('stock_items'):
        historical_skus.update((delivery.stock_items or {}).keys())
    for entry in DailyStock.objects.all().only('initial'):
        historical_skus.update((entry.initial or {}).keys())

    next_order = len(MATERIALS)
    for sku in sorted(s for s in historical_skus if s):
        if Material.objects.filter(sku=sku).exists():
            continue
        Material.objects.create(
            sku=sku,
            name=sku,
            unit='',
            color='#999999',
            active=False,
            sort_order=next_order,
        )
        next_order += 1

    historical_labels = set()
    for label in Delivery.objects.exclude(product='').values_list('product', flat=True):
        label = (label or '').strip()
        if label:
            historical_labels.add(label)

    next_order = len(COMMERCIAL_PRODUCTS)
    for label in sorted(historical_labels):
        if CommercialProduct.objects.filter(label=label).exists():
            continue
        CommercialProduct.objects.create(
            label=label,
            active=False,
            sort_order=next_order,
        )
        next_order += 1


def reverse_seed_catalogs(apps, schema_editor):
    Material = apps.get_model('entregas', 'Material')
    CommercialProduct = apps.get_model('entregas', 'CommercialProduct')

    CommercialProduct.objects.filter(label__in=COMMERCIAL_PRODUCTS).delete()
    Material.objects.filter(sku__in=[m[0] for m in MATERIALS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('entregas', '0003_commercialproduct_material_alter_delivery_arrived_at_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_catalogs, reverse_seed_catalogs),
    ]
