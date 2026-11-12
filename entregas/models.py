from django.db import models


class Client(models.Model):
    phone           = models.CharField(max_length=20, unique=True)
    phone_raw       = models.CharField(max_length=20, blank=True)
    name            = models.CharField(max_length=200, blank=True)
    address_input   = models.TextField(blank=True)
    address         = models.TextField(blank=True)
    formatted_address = models.TextField(blank=True)
    place_id        = models.CharField(max_length=200, blank=True)
    reference       = models.TextField(blank=True)
    lat             = models.FloatField(null=True, blank=True)
    lng             = models.FloatField(null=True, blank=True)
    verified        = models.BooleanField(default=False)
    geocode_source  = models.CharField(max_length=50, default='manual')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clients'

    def to_dict(self):
        return {
            'phone':             self.phone,
            'phone_raw':         self.phone_raw,
            'name':              self.name,
            'address_input':     self.address_input,
            'address':           self.address,
            'formatted_address': self.formatted_address,
            'place_id':          self.place_id,
            'reference':         self.reference,
            'lat':               self.lat,
            'lng':               self.lng,
            'verified':          self.verified,
            'geocode_source':    self.geocode_source,
            'created_at':        self.created_at.isoformat() if self.created_at else None,
            'addresses':         [a.to_dict() for a in self.addresses.filter(active=True)],
        }


class ClientAddress(models.Model):
    client            = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='addresses')
    label             = models.CharField(max_length=100, blank=True)
    address_input     = models.TextField(blank=True)
    address           = models.TextField(blank=True)
    formatted_address = models.TextField(blank=True)
    place_id          = models.CharField(max_length=200, blank=True)
    reference         = models.TextField(blank=True)
    lat               = models.FloatField(null=True, blank=True)
    lng               = models.FloatField(null=True, blank=True)
    verified          = models.BooleanField(default=False)
    geocode_source    = models.CharField(max_length=50, default='manual')
    is_default        = models.BooleanField(default=False)
    active            = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client_addresses'
        ordering = ['-is_default', 'id']

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'address_input': self.address_input,
            'address': self.address,
            'formatted_address': self.formatted_address,
            'place_id': self.place_id,
            'reference': self.reference,
            'lat': self.lat,
            'lng': self.lng,
            'verified': self.verified,
            'geocode_source': self.geocode_source,
            'is_default': self.is_default,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Material(models.Model):
    sku        = models.CharField(max_length=20, primary_key=True)
    name       = models.CharField(max_length=200)
    unit       = models.CharField(max_length=50, blank=True)
    color      = models.CharField(max_length=20, default='#999999')
    active     = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'materials'
        ordering = ['sort_order', 'sku']

    def to_dict(self):
        return {
            'id':         self.sku,
            'sku':        self.sku,
            'name':       self.name,
            'unit':       self.unit,
            'color':      self.color,
            'active':     self.active,
            'sort_order': self.sort_order,
        }


class CommercialProduct(models.Model):
    label      = models.CharField(max_length=100, unique=True)
    active     = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'commercial_products'
        ordering = ['sort_order', 'label']

    def to_dict(self):
        return {
            'id':         self.id,
            'label':      self.label,
            'name':       self.label,
            'active':     self.active,
            'sort_order': self.sort_order,
            'components': [
                {
                    'sku':      c.material_id,
                    'quantity': c.quantity,
                }
                for c in self.components.select_related('material').all()
            ],
        }


class ProductComponent(models.Model):
    product  = models.ForeignKey(CommercialProduct, on_delete=models.CASCADE, related_name='components')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='components')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'product_components'
        unique_together = ('product', 'material')
        ordering = ['material__sort_order', 'material_id']

    def __str__(self):
        return f'{self.product.label} → {self.material_id} x {self.quantity}'


class Delivery(models.Model):
    id              = models.CharField(max_length=20, primary_key=True)
    delivery_date   = models.DateField()
    client_phone    = models.CharField(max_length=20, blank=True)
    client_address   = models.ForeignKey('ClientAddress', null=True, blank=True, on_delete=models.SET_NULL, related_name='deliveries')
    name            = models.CharField(max_length=200, blank=True)
    address         = models.TextField(blank=True)
    formatted_address = models.TextField(blank=True)
    place_id        = models.CharField(max_length=200, blank=True)
    reference       = models.TextField(blank=True)
    product         = models.CharField(max_length=200, blank=True)
    product_ref     = models.ForeignKey(CommercialProduct, null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='deliveries')
    amount          = models.CharField(max_length=100, blank=True)
    items           = models.JSONField(default=list, blank=True)
    payment         = models.CharField(max_length=100, blank=True)
    driver          = models.CharField(max_length=100, blank=True)
    route_order     = models.PositiveIntegerField(null=True, blank=True)
    time_start      = models.CharField(max_length=10, blank=True)
    time_end        = models.CharField(max_length=10, blank=True)
    notes           = models.TextField(blank=True)
    lat             = models.FloatField(null=True, blank=True)
    lng             = models.FloatField(null=True, blank=True)
    stock_items     = models.JSONField(default=dict, blank=True)
    completed       = models.BooleanField(default=False)
    arrived_at      = models.CharField(max_length=10, blank=True, null=True)
    departed_at     = models.CharField(max_length=10, blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'deliveries'

    def items_payload(self):
        if self.items:
            return self.items
        if self.product or self.amount or self.stock_items:
            return [{
                'product':       self.product,
                'amount':        self.amount,
                'product_ref_id': self.product_ref_id,
                'stock_items':   self.stock_items or {},
            }]
        return []

    def to_dict(self, client=None):
        items = self.items_payload()
        first_item = items[0] if items else {}
        d = {
            'id':                self.id,
            'delivery_date':     self.delivery_date.isoformat() if hasattr(self.delivery_date, 'isoformat') else self.delivery_date,
            'client_phone':      self.client_phone,
            'client_address_id': self.client_address_id,
            'name':              self.name,
            'address':           self.address,
            'formatted_address': self.formatted_address,
            'place_id':          self.place_id,
            'reference':         self.reference,
            'product':           self.product or first_item.get('product', ''),
            'product_ref_id':    self.product_ref_id or first_item.get('product_ref_id'),
            'amount':            self.amount or first_item.get('amount', ''),
            'items':             items,
            'payment':           self.payment,
            'driver':            self.driver,
            'route_order':       self.route_order,
            'time_start':        self.time_start,
            'time_end':          self.time_end,
            'notes':             self.notes,
            'lat':               self.lat,
            'lng':               self.lng,
            'stock_items':       self.stock_items,
            'completed':         self.completed,
            'arrived_at':        self.arrived_at or None,
            'departed_at':       self.departed_at or None,
            'created_at':        self.created_at.isoformat() if self.created_at else None,
        }
        if client:
            d['_client'] = client.to_dict() if hasattr(client, 'to_dict') else client
            if not d['lat'] and client.lat:
                d['lat'] = client.lat
                d['lng'] = client.lng
            if not d['name']:
                d['name'] = client.name
            if not d['address']:
                d['address'] = client.formatted_address or client.address
        return d


class DailyStock(models.Model):
    date       = models.DateField()
    driver     = models.CharField(max_length=100)
    initial    = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_stock'
        unique_together = ('date', 'driver')


class OptRoute(models.Model):
    date       = models.DateField()
    driver     = models.CharField(max_length=100, blank=True)
    result     = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opt_routes'
        unique_together = ('date', 'driver')


class Config(models.Model):
    key   = models.CharField(max_length=100, unique=True)
    value = models.JSONField()

    class Meta:
        db_table = 'config'