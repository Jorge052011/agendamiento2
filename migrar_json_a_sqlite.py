#!/usr/bin/env python3
"""
Migra los datos de los archivos JSON a la base de datos SQLite.
Ejecutar UNA SOLA VEZ después de aplicar los cambios y correr las migraciones.

Uso:
    python manage.py shell < migrar_json_a_sqlite.py
    
O directamente:
    python migrar_json_a_sqlite.py
"""
import os, sys, json, django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'repartotrack.settings')
django.setup()

from entregas.models import Client, Delivery, DailyStock, OptRoute, Config

def load_json(path):
    p = Path(path)
    if not p.exists():
        print(f"⚠️  No existe: {path}")
        return []
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON corrupto en {path}: {e}")
        return []

def migrar():
    print("=== Migrando JSON → SQLite ===\n")

    # ── Clientes ──────────────────────────────────────────────────────────────
    clients_data = load_json(BASE_DIR / 'clients.json')
    c_ok = c_skip = 0
    for c in clients_data:
        phone = c.get('phone', '').strip()
        if not phone:
            c_skip += 1
            continue
        Client.objects.update_or_create(
            phone=phone,
            defaults={
                'phone_raw':         c.get('phone_raw', phone),
                'name':              c.get('name', ''),
                'address_input':     c.get('address_input', ''),
                'address':           c.get('address', ''),
                'formatted_address': c.get('formatted_address', ''),
                'place_id':          c.get('place_id', ''),
                'reference':         c.get('reference', ''),
                'lat':               c.get('lat'),
                'lng':               c.get('lng'),
                'verified':          c.get('verified', False),
                'geocode_source':    c.get('geocode_source', 'manual'),
            }
        )
        c_ok += 1
    print(f"✅ Clientes: {c_ok} importados, {c_skip} omitidos")

    # ── Entregas ──────────────────────────────────────────────────────────────
    deliveries_data = load_json(BASE_DIR / 'deliveries.json')
    d_ok = d_skip = 0
    for d in deliveries_data:
        did = str(d.get('id', '')).strip()
        if not did:
            d_skip += 1
            continue
        try:
            Delivery.objects.update_or_create(
                id=did,
                defaults={
                    'delivery_date':     d.get('delivery_date', ''),
                    'client_phone':      d.get('client_phone', ''),
                    'name':              d.get('name', ''),
                    'address':           d.get('address', ''),
                    'formatted_address': d.get('formatted_address', ''),
                    'place_id':          d.get('place_id', ''),
                    'reference':         d.get('reference', ''),
                    'product':           d.get('product', ''),
                    'amount':            str(d.get('amount', '')),
                    'payment':           d.get('payment', ''),
                    'driver':            d.get('driver', ''),
                    'time_start':        d.get('time_start', ''),
                    'time_end':          d.get('time_end', ''),
                    'notes':             d.get('notes', ''),
                    'lat':               d.get('lat'),
                    'lng':               d.get('lng'),
                    'stock_items':       d.get('stock_items') or {},
                    'completed':         d.get('completed', False),
                    'arrived_at':        d.get('arrived_at'),
                    'departed_at':       d.get('departed_at'),
                }
            )
            d_ok += 1
        except Exception as e:
            print(f"  ⚠️  Entrega {did} omitida: {e}")
            d_skip += 1
    print(f"✅ Entregas: {d_ok} importadas, {d_skip} omitidas")

    # ── Stock ─────────────────────────────────────────────────────────────────
    stock_data = load_json(BASE_DIR / 'stock.json')
    s_ok = 0
    for s in stock_data:
        day    = s.get('date', '')
        driver = s.get('driver', '')
        if not day or not driver:
            continue
        DailyStock.objects.update_or_create(
            date=day, driver=driver,
            defaults={'initial': s.get('initial', {})}
        )
        s_ok += 1
    print(f"✅ Stock: {s_ok} importados")

    # ── Rutas optimizadas ─────────────────────────────────────────────────────
    routes_data = load_json(BASE_DIR / 'opt_routes.json')
    r_ok = 0
    for r in routes_data:
        day    = r.get('date', '')
        driver = r.get('driver', '')
        result = r.get('result')
        if not day or not result:
            continue
        OptRoute.objects.update_or_create(
            date=day, driver=driver,
            defaults={'result': result}
        )
        r_ok += 1
    print(f"✅ Rutas optimizadas: {r_ok} importadas")

    # ── Config ────────────────────────────────────────────────────────────────
    config_data = load_json(BASE_DIR / 'config.json')
    if isinstance(config_data, dict):
        for key, value in config_data.items():
            Config.objects.update_or_create(key=key, defaults={'value': value})
        print(f"✅ Config: {len(config_data)} claves importadas")

    print("\n🎉 Migración completada.")

if __name__ == '__main__':
    migrar()
