import json
from datetime import date

from django.test import TestCase

from .models import CommercialProduct, Delivery, Material, ProductComponent


class CatalogAndLoadTests(TestCase):
    def setUp(self):
        self.material = Material.objects.get(sku='LAV-8')
        self.product = CommercialProduct.objects.get(label='8 k lav')
        ProductComponent.objects.create(
            product=self.product, material=self.material, quantity=2)
        self.other_product = CommercialProduct.objects.get(label='16 k lav')

    def post_json(self, path, payload, method='post'):
        return getattr(self.client, method)(
            path, data=json.dumps(payload), content_type='application/json')

    def create_delivery(self, **overrides):
        payload = {
            'delivery_date': '2026-11-05',
            'name': 'Cliente',
            'address': 'Calle 1',
            'driver': 'jorge',
            'product': self.product.label,
            'amount': '3',
        }
        payload.update(overrides)
        return self.post_json('/api/deliveries', payload)

    def add_other_composition(self):
        ProductComponent.objects.get_or_create(
            product=self.other_product, material=self.material,
            defaults={'quantity': 1})

    def test_create_delivery_with_multiple_items(self):
        self.add_other_composition()
        response = self.create_delivery(items=[
            {'product': self.product.label, 'amount': '2'},
            {'product': self.other_product.label, 'amount': '3'},
        ])
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data['items']), 2)

        delivery = Delivery.objects.get(id=data['id'])
        self.assertEqual(delivery.items[1]['product'], self.other_product.label)
        self.assertEqual(delivery.stock_items, {'LAV-8': 7})
        self.assertEqual(delivery.product, self.product.label)
        self.assertEqual(delivery.amount, '2')

    def test_stock_required_aggregates_multiple_items(self):
        self.add_other_composition()
        self.create_delivery(items=[
            {'product': self.product.label, 'amount': '2'},
            {'product': self.other_product.label, 'amount': '3'},
        ])
        response = self.client.get('/api/stock?date=2026-11-05&driver=jorge')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['required']['LAV-8'], 7)

    def test_edit_items_recalculates_and_supports_add_remove(self):
        self.add_other_composition()
        created = self.create_delivery(amount='1').json()

        response = self.post_json(
            f"/api/deliveries/{created['id']}",
            {'items': [
                {'product': self.product.label, 'amount': '2'},
                {'product': self.other_product.label, 'amount': '3'},
            ]},
            method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stock_items'], {'LAV-8': 7})

        response = self.post_json(
            f"/api/deliveries/{created['id']}",
            {'items': [{'product': self.other_product.label, 'amount': '4'}]},
            method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stock_items'], {'LAV-8': 4})
        self.assertEqual(response.json()['product'], self.other_product.label)
        self.assertEqual(response.json()['amount'], '4')

    def test_edit_notes_keeps_items_snapshot(self):
        created = self.create_delivery(amount='2').json()
        ProductComponent.objects.filter(
            product=self.product, material=self.material).update(quantity=5)

        response = self.post_json(
            f"/api/deliveries/{created['id']}", {'notes': 'nota'}, method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['stock_items'], {'LAV-8': 4})
        self.assertEqual(response.json()['stock_items'], {'LAV-8': 4})

    def test_legacy_delivery_returns_items_fallback(self):
        Delivery.objects.create(
            id='legacy-items-1', delivery_date=date(2026, 11, 5), name='Viejo',
            address='Calle', driver='jorge', product='20 k aroma café',
            amount='1', stock_items={'LAV-20': 1})
        response = self.client.get('/api/deliveries?date=2026-11-05')
        self.assertEqual(response.status_code, 200)
        data = next(d for d in response.json() if d['id'] == 'legacy-items-1')
        self.assertEqual(data['items'][0]['product'], '20 k aroma café')
        self.assertEqual(data['items'][0]['amount'], '1')

    def test_catalog_includes_components(self):
        response = self.client.get('/api/catalog')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        product = next(p for p in data['commercial_products']
                       if p['label'] == self.product.label)
        self.assertEqual(product['components'], [{'sku': 'LAV-8', 'quantity': 2}])

    def test_create_delivery_snapshots_composition(self):
        response = self.create_delivery()
        self.assertEqual(response.status_code, 201)
        delivery = Delivery.objects.get(id=response.json()['id'])
        self.assertEqual(delivery.stock_items, {'LAV-8': 6})
        self.assertEqual(delivery.product_ref, self.product)

    def test_create_delivery_without_composition_fails(self):
        response = self.create_delivery(product=self.other_product.label)
        self.assertEqual(response.status_code, 400)

    def test_edit_amount_recalculates_composition(self):
        created = self.create_delivery(amount='1').json()
        response = self.post_json(
            f"/api/deliveries/{created['id']}", {'amount': '4'}, method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stock_items'], {'LAV-8': 8})

    def test_edit_without_composition_change_keeps_snapshot(self):
        created = self.create_delivery(amount='3').json()
        ProductComponent.objects.filter(
            product=self.product, material=self.material).update(quantity=5)

        response = self.post_json(
            f"/api/deliveries/{created['id']}",
            {'product': self.product.label, 'amount': '3', 'notes': 'nota'},
            method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stock_items'], {'LAV-8': 6})

    def test_edit_legacy_product_keeps_snapshot(self):
        delivery = Delivery.objects.create(
            id='legacy-1', delivery_date=date(2026, 11, 5), name='Viejo',
            address='Calle', driver='jorge', product='20 k aroma café',
            amount='1', stock_items={'LAV-20': 1})
        response = self.post_json(
            '/api/deliveries/legacy-1', {'notes': 'nota'}, method='patch')
        self.assertEqual(response.status_code, 200)
        delivery.refresh_from_db()
        self.assertEqual(delivery.stock_items, {'LAV-20': 1})

    def test_stock_required_loaded_delivered_and_alerts(self):
        created = self.create_delivery(amount='2').json()
        self.post_json(
            f"/api/deliveries/{created['id']}", {'completed': True}, method='patch')

        response = self.client.get('/api/stock?date=2026-11-05&driver=jorge')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['required']['LAV-8'], 4)
        self.assertEqual(data['delivered']['LAV-8'], 4)
        self.assertFalse(data['has_saved_load'])
        self.assertEqual(data['alerts'], [])

        saved = self.post_json('/api/stock', {
            'date': '2026-11-05', 'driver': 'jorge', 'loaded': {'LAV-8': 2},
        })
        self.assertEqual(saved.status_code, 200)

        response = self.client.get('/api/stock?date=2026-11-05&driver=jorge')
        data = response.json()
        self.assertTrue(data['has_saved_load'])
        self.assertEqual(data['loaded']['LAV-8'], 2)
        self.assertEqual(data['coverage']['LAV-8'], -2)
        self.assertEqual(data['alerts'][0]['shortage'], 2)

    def test_stock_summary_uses_required(self):
        self.create_delivery(amount='2')
        response = self.client.get('/api/stock/summary?date=2026-11-05')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['summary']['jorge']['required']['LAV-8'], 4)

    def test_create_delivery_accepts_route_order(self):
        response = self.create_delivery(route_order=3)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['route_order'], 3)

    def test_patch_route_order_persists_and_orders_deliveries(self):
        first = self.create_delivery(name='Primero', amount='1').json()
        second = self.create_delivery(name='Segundo', amount='1').json()

        response = self.post_json(
            f"/api/deliveries/{second['id']}", {'route_order': 1}, method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['route_order'], 1)

        response = self.post_json(
            f"/api/deliveries/{first['id']}", {'route_order': 2}, method='patch')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['route_order'], 2)

        first_delivery = Delivery.objects.get(id=first['id'])
        second_delivery = Delivery.objects.get(id=second['id'])
        self.assertEqual(second_delivery.route_order, 1)
        self.assertEqual(first_delivery.route_order, 2)

        response = self.client.get('/api/deliveries?date=2026-11-05')
        self.assertEqual(response.status_code, 200)
        ids = [d['id'] for d in response.json()]
        self.assertEqual(ids, [second['id'], first['id']])

    def test_deliveries_without_route_order_go_last(self):
        unordered = self.create_delivery(name='Sin orden', amount='1').json()
        ordered = self.create_delivery(name='Con orden', amount='1').json()
        self.post_json(
            f"/api/deliveries/{ordered['id']}", {'route_order': 1}, method='patch')

        response = self.client.get('/api/deliveries?date=2026-11-05')
        ids = [d['id'] for d in response.json()]
        self.assertEqual(ids, [ordered['id'], unordered['id']])
