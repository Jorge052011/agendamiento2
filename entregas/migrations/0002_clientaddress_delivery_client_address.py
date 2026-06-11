from django.db import migrations, models
import django.db.models.deletion


def copy_existing_addresses(apps, schema_editor):
    Client = apps.get_model('entregas', 'Client')
    ClientAddress = apps.get_model('entregas', 'ClientAddress')
    for client in Client.objects.all():
        formatted = client.formatted_address or client.address
        if not formatted:
            continue
        ClientAddress.objects.create(
            client_id=client.id,
            label='Dirección principal',
            address_input=client.address_input,
            address=client.address or formatted,
            formatted_address=formatted,
            place_id=client.place_id,
            reference=client.reference,
            lat=client.lat,
            lng=client.lng,
            verified=client.verified,
            geocode_source=client.geocode_source,
            is_default=True,
            active=True,
        )


class Migration(migrations.Migration):
    dependencies = [('entregas', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='ClientAddress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(blank=True, max_length=100)),
                ('address_input', models.TextField(blank=True)),
                ('address', models.TextField(blank=True)),
                ('formatted_address', models.TextField(blank=True)),
                ('place_id', models.CharField(blank=True, max_length=200)),
                ('reference', models.TextField(blank=True)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lng', models.FloatField(blank=True, null=True)),
                ('verified', models.BooleanField(default=False)),
                ('geocode_source', models.CharField(default='manual', max_length=50)),
                ('is_default', models.BooleanField(default=False)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='entregas.client')),
            ],
            options={'db_table': 'client_addresses', 'ordering': ['-is_default', 'id']},
        ),
        migrations.AddField(
            model_name='delivery',
            name='client_address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deliveries', to='entregas.clientaddress'),
        ),
        migrations.RunPython(copy_existing_addresses, migrations.RunPython.noop),
    ]
