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
        }


class Delivery(models.Model):
    id              = models.CharField(max_length=20, primary_key=True)
    delivery_date   = models.DateField()
    client_phone    = models.CharField(max_length=20, blank=True)
    name            = models.CharField(max_length=200, blank=True)
    address         = models.TextField(blank=True)
    formatted_address = models.TextField(blank=True)
    place_id        = models.CharField(max_length=200, blank=True)
    reference       = models.TextField(blank=True)
    product         = models.CharField(max_length=200, blank=True)
    amount          = models.CharField(max_length=100, blank=True)
    payment         = models.CharField(max_length=100, blank=True)
    driver          = models.CharField(max_length=100, blank=True)
    time_start      = models.CharField(max_length=10, blank=True)
    time_end        = models.CharField(max_length=10, blank=True)
    notes           = models.TextField(blank=True)
    lat             = models.FloatField(null=True, blank=True)
    lng             = models.FloatField(null=True, blank=True)
    stock_items     = models.JSONField(default=dict, blank=True)
    completed       = models.BooleanField(default=False)
    arrived_at      = models.DateTimeField(null=True, blank=True)
    departed_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'deliveries'

    def to_dict(self, client=None):
        d = {
            'id':                self.id,
            'delivery_date':     self.delivery_date.isoformat(),
            'client_phone':      self.client_phone,
            'name':              self.name,
            'address':           self.address,
            'formatted_address': self.formatted_address,
            'place_id':          self.place_id,
            'reference':         self.reference,
            'product':           self.product,
            'amount':            self.amount,
            'payment':           self.payment,
            'driver':            self.driver,
            'time_start':        self.time_start,
            'time_end':          self.time_end,
            'notes':             self.notes,
            'lat':               self.lat,
            'lng':               self.lng,
            'stock_items':       self.stock_items,
            'completed':         self.completed,
            'arrived_at':        self.arrived_at.isoformat() if self.arrived_at else None,
            'departed_at':       self.departed_at.isoformat() if self.departed_at else None,
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
