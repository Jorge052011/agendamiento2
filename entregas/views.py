import json
import re
from datetime import datetime, date
from collections import defaultdict

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render

from .models import (
    Client, ClientAddress, Delivery, DailyStock, OptRoute, Config,
    Material, CommercialProduct,
)
from .utils import normalize_phone


def no_cache(response):
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma']        = 'no-cache'
    response['Expires']       = '0'
    return response


# ═══════════════════════════════════════════════════════════════════════════════
#  PÁGINA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def index(request):
    return render(request, 'index.html')


# ═══════════════════════════════════════════════════════════════════════════════
#  CLIENTES
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET", "POST"])
def clients(request):
    if request.method == "GET":
        phone = request.GET.get("phone", "").strip()
        if phone:
            norm = normalize_phone(phone)
            try:
                client = Client.objects.get(phone=norm)
                return no_cache(JsonResponse(client.to_dict()))
            except Client.DoesNotExist:
                return JsonResponse(None, safe=False, status=404)
        all_clients = list(Client.objects.all().values())
        # Convertir a formato compatible
        result = [Client.objects.get(pk=c['id']).to_dict() for c in all_clients]
        return no_cache(JsonResponse(result, safe=False))

    # POST — crear o actualizar
    data  = json.loads(request.body)
    phone = normalize_phone(data.get("phone", ""))
    if not phone:
        return JsonResponse({"error": "Teléfono requerido"}, status=400)

    client, created = Client.objects.get_or_create(phone=phone)

    fields = ["name", "address", "address_input", "formatted_address",
              "place_id", "lat", "lng", "reference", "verified", "geocode_source"]
    for k in fields:
        if k in data and data[k]:
            setattr(client, k, data[k])

    if created:
        client.phone_raw = data.get("phone", phone)

    client.save()

    # Al crear un cliente, guardar su primera dirección en la tabla histórica.
    formatted = (data.get("formatted_address") or data.get("address") or "").strip()
    if created and formatted:
        ClientAddress.objects.create(
            client=client,
            label=data.get("label", "Dirección principal").strip() or "Dirección principal",
            address_input=data.get("address_input", "").strip(),
            address=formatted,
            formatted_address=formatted,
            place_id=data.get("place_id", "").strip(),
            reference=data.get("reference", "").strip(),
            lat=data.get("lat"), lng=data.get("lng"),
            verified=bool(data.get("verified", False)),
            geocode_source=data.get("geocode_source", "manual"),
            is_default=True,
        )

    status = 201 if created else 200
    return JsonResponse(client.to_dict(), status=status)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def client_detail(request, phone):
    norm = normalize_phone(phone)
    try:
        client = Client.objects.get(phone=norm)
    except Client.DoesNotExist:
        return JsonResponse({"error": "Cliente no encontrado"}, status=404)

    if request.method == "DELETE":
        client.delete()
        return JsonResponse({"ok": True})

    # PATCH
    data = json.loads(request.body)
    for k, v in data.items():
        if hasattr(client, k):
            setattr(client, k, v)
    client.save()
    return JsonResponse(client.to_dict())


@csrf_exempt
@require_http_methods(["POST"])
def client_addresses(request, phone):
    norm = normalize_phone(phone)
    try:
        client = Client.objects.get(phone=norm)
    except Client.DoesNotExist:
        return JsonResponse({"error": "Cliente no encontrado"}, status=404)

    data = json.loads(request.body)
    formatted = (data.get("formatted_address") or data.get("address") or "").strip()
    if not formatted:
        return JsonResponse({"error": "Dirección requerida"}, status=400)

    if data.get("is_default"):
        client.addresses.update(is_default=False)

    address = ClientAddress.objects.create(
        client=client,
        label=data.get("label", "").strip(),
        address_input=data.get("address_input", "").strip(),
        address=formatted,
        formatted_address=formatted,
        place_id=data.get("place_id", "").strip(),
        reference=data.get("reference", "").strip(),
        lat=data.get("lat"), lng=data.get("lng"),
        verified=bool(data.get("verified", False)),
        geocode_source=data.get("geocode_source", "manual"),
        is_default=bool(data.get("is_default", not client.addresses.exists())),
    )
    return JsonResponse(address.to_dict(), status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def client_address_detail(request, phone, address_id):
    norm = normalize_phone(phone)
    try:
        client = Client.objects.get(phone=norm)
        address = client.addresses.get(id=address_id)
    except Client.DoesNotExist:
        return JsonResponse({"error": "Cliente no encontrado"}, status=404)
    except ClientAddress.DoesNotExist:
        return JsonResponse({"error": "Dirección no encontrada"}, status=404)

    was_default = address.is_default
    address.delete()

    # Si se borró la dirección principal, deja otra dirección como principal.
    if was_default:
        next_address = client.addresses.filter(active=True).first()
        if next_address:
            next_address.is_default = True
            next_address.save(update_fields=["is_default"])

    return JsonResponse({
        "ok": True,
        "client": client.to_dict(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  CATÁLOGO Y COMPOSICIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def _commercial_product_for(label):
    label = (label or '').strip()
    if not label:
        return None
    return CommercialProduct.objects.filter(label=label).first()


def _parse_quantity(value):
    """Extrae la cantidad numérica de campos históricos como '1' o '2 bolsas'."""
    if value is None:
        return 0
    match = re.search(r'\d+', str(value))
    return int(match.group()) if match else 0


def _required_materials_for(product_label, amount):
    """Calcula las bolsas requeridas desde la composición del producto."""
    product = _commercial_product_for(product_label)
    if not product or not product.components.exists():
        return None

    qty = _parse_quantity(amount) or 1
    required = {}
    for component in product.components.all():
        sku = component.material_id
        required[sku] = required.get(sku, 0) + (component.quantity * qty)
    return required


def _prepare_delivery_catalog(data, current_delivery=None):
    """Completa product_ref y stock_items sin destruir valores históricos."""
    product_label = data.get('product', current_delivery.product if current_delivery else '')
    amount = data.get('amount', current_delivery.amount if current_delivery else '')
    product = _commercial_product_for(product_label)

    product_changed = (
        current_delivery is None or
        (product_label or '') != (current_delivery.product or '')
    )
    amount_changed = (
        current_delivery is None or
        (amount or '') != (current_delivery.amount or '')
    )

    if product_changed:
        data['product_ref_id'] = product.id if product else None

    if product_changed or amount_changed:
        required = _required_materials_for(product_label, amount)
        if required is not None:
            data['stock_items'] = required
        elif product and product.active:
            raise ValueError(f'El producto "{product.label}" no tiene composición configurada')

    return data


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTREGAS
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET", "POST"])
def deliveries(request):
    if request.method == "GET":
        date_filter = request.GET.get("date")
        qs = Delivery.objects.all()
        if date_filter:
            qs = qs.filter(delivery_date=date_filter)

        clients_map = {c.phone: c for c in Client.objects.all()}
        result = [d.to_dict(client=clients_map.get(d.client_phone)) for d in qs]
        return no_cache(JsonResponse(result, safe=False))

    # POST
    data   = json.loads(request.body)
    try:
        _prepare_delivery_catalog(data)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    phone  = normalize_phone(data.get("phone", ""))
    client = None
    try:
        client = Client.objects.get(phone=phone)
    except Client.DoesNotExist:
        pass

    client_address = None
    address_id = data.get("client_address_id")
    if client and address_id:
        try:
            client_address = client.addresses.get(id=address_id, active=True)
        except ClientAddress.DoesNotExist:
            return JsonResponse({"error": "La dirección seleccionada no pertenece al cliente"}, status=400)

    address = (data.get("formatted_address") or data.get("address", "")).strip()
    if client_address:
        address = client_address.formatted_address or client_address.address
    elif not address and client:
        default_address = client.addresses.filter(active=True).first()
        if default_address:
            client_address = default_address
            address = default_address.formatted_address or default_address.address
        else:
            address = client.formatted_address or client.address or ""

    name = (data.get("name", "").strip() or (client.name if client else ""))
    driver = data.get("driver", "").lower().strip()

    if not name or not address or not driver:
        return JsonResponse(
            {"error": "Nombre, dirección y repartidor son requeridos"}, status=400)

    delivery = Delivery.objects.create(
        id               = str(int(datetime.now().timestamp() * 1000)),
        delivery_date    = data.get("delivery_date", date.today().isoformat()),
        client_phone     = phone,
        client_address   = client_address,
        name             = name,
        address          = address,
        formatted_address= (data.get("formatted_address", "").strip() or
                            (client_address.formatted_address if client_address else (client.formatted_address if client else ""))),
        place_id         = (data.get("place_id", "").strip() or
                            (client_address.place_id if client_address else (client.place_id if client else ""))),
        reference        = (data.get("reference", "").strip() or
                            (client_address.reference if client_address else (client.reference if client else ""))),
        product          = data.get("product", "").strip(),
        product_ref_id   = data.get("product_ref_id") or data.get("product_ref"),
        amount           = data.get("amount", "").strip(),
        payment          = data.get("payment", "").strip(),
        driver           = driver,
        time_start       = data.get("time_start", ""),
        time_end         = data.get("time_end", ""),
        notes            = data.get("notes", "").strip(),
        lat              = data.get("lat") or (client_address.lat if client_address else (client.lat if client else None)),
        lng              = data.get("lng") or (client_address.lng if client_address else (client.lng if client else None)),
        stock_items      = data.get("stock_items", {}),
        completed        = False,
    )
    return JsonResponse(delivery.to_dict(client=client), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def delivery_detail(request, delivery_id):
    try:
        delivery = Delivery.objects.get(id=delivery_id)
    except Delivery.DoesNotExist:
        return JsonResponse({"error": "No encontrado"}, status=404)

    if request.method == "DELETE":
        delivery.delete()
        return JsonResponse({"ok": True})

    # PATCH
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    try:
        _prepare_delivery_catalog(data, current_delivery=delivery)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    for k, v in data.items():
        if not hasattr(delivery, k):
            continue
        setattr(delivery, k, v)

    try:
        delivery.save()
    except Exception as e:
        return JsonResponse({"error": f"Error al guardar: {str(e)}"}, status=500)

    return JsonResponse(delivery.to_dict())


# ═══════════════════════════════════════════════════════════════════════════════
#  CALENDARIO
# ═══════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def calendar(request):
    year   = int(request.GET.get("year",  date.today().year))
    month  = int(request.GET.get("month", date.today().month))

    qs = Delivery.objects.filter(
        delivery_date__year=year,
        delivery_date__month=month
    )

    summary = defaultdict(lambda: {"total": 0, "completed": 0, "drivers": set()})
    for d in qs:
        key = d.delivery_date.isoformat()
        summary[key]["total"]     += 1
        summary[key]["completed"] += int(d.completed)
        summary[key]["drivers"].add(d.driver)

    result = {
        k: {"total": v["total"], "completed": v["completed"], "drivers": list(v["drivers"])}
        for k, v in summary.items()
    }
    return JsonResponse(result)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET", "POST"])
def config(request):
    if request.method == "GET":
        departure_points = []
        try:
            departure_points = Config.objects.get(key="departure_points").value
        except Config.DoesNotExist:
            pass
        key = settings.GOOGLE_MAPS_API_KEY or ""
        return no_cache(JsonResponse({
            "google_maps_key": key, "departure_points": departure_points,
        }))

    data = json.loads(request.body)
    if "departure_points" in data:
        Config.objects.update_or_create(
            key="departure_points",
            defaults={"value": data["departure_points"]}
        )
    return JsonResponse({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  RUTA OPTIMIZADA GUARDADA
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def opt_route(request):
    if request.method == "GET":
        day    = request.GET.get("date", date.today().isoformat())
        driver = request.GET.get("driver", "")
        try:
            entry = OptRoute.objects.get(date=day, driver=driver)
            return no_cache(JsonResponse(entry.result, safe=False))
        except OptRoute.DoesNotExist:
            return JsonResponse({"error": "No hay ruta guardada"}, status=404)

    if request.method == "DELETE":
        day    = request.GET.get("date", date.today().isoformat())
        driver = request.GET.get("driver", "")
        OptRoute.objects.filter(date=day, driver=driver).delete()
        return JsonResponse({"ok": True})

    # POST
    data   = json.loads(request.body)
    day    = data.get("date", date.today().isoformat())
    driver = data.get("driver", "")
    result = data.get("result")

    if not result:
        return JsonResponse({"error": "result requerido"}, status=400)

    OptRoute.objects.update_or_create(
        date=day, driver=driver,
        defaults={"result": result}
    )
    return JsonResponse({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  CATÁLOGO / MATERIALES
# ═══════════════════════════════════════════════════════════════════════════════

def _active_materials_payload():
    return [
        material.to_dict()
        for material in Material.objects.filter(active=True).order_by('sort_order', 'sku')
    ]


def _active_commercial_products_payload():
    products = (
        CommercialProduct.objects
        .filter(active=True)
        .prefetch_related('components__material')
        .order_by('sort_order', 'label')
    )
    result = []
    for product in products:
        item = product.to_dict()
        item['has_composition'] = bool(item['components'])
        result.append(item)
    return result


@require_http_methods(["GET"])
def products(request):
    """Catálogo de materiales activos (compatibilidad con Carga del Día)."""
    return JsonResponse(_active_materials_payload(), safe=False)


@require_http_methods(["GET"])
def catalog(request):
    return no_cache(JsonResponse({
        "materials": _active_materials_payload(),
        "commercial_products": _active_commercial_products_payload(),
    }))


def _stock_products_payload(deliveries_qs, loaded):
    """Materiales activos + SKUs históricos con movimiento en la fecha."""
    material_map = {material.sku: material for material in Material.objects.all()}
    skus = {
        material.sku for material in material_map.values() if material.active
    }
    for delivery in deliveries_qs:
        skus.update((delivery.stock_items or {}).keys())
    skus.update((loaded or {}).keys())

    def sort_key(sku):
        material = material_map.get(sku)
        return (material.sort_order if material else 9999, sku)

    result = []
    for sku in sorted(skus, key=sort_key):
        material = material_map.get(sku)
        if material:
            result.append(material.to_dict())
        else:
            result.append({
                'id': sku, 'sku': sku, 'name': sku, 'unit': '',
                'color': '#999999', 'active': False, 'sort_order': 9999,
            })
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  CARGA DEL DÍA
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["GET", "POST"])
def stock(request):
    if request.method == "GET":
        date_filter   = request.GET.get("date", date.today().isoformat())
        driver_filter = request.GET.get("driver", "").lower().strip()

        qs = Delivery.objects.filter(delivery_date=date_filter)
        if driver_filter:
            qs = qs.filter(driver=driver_filter)
        deliveries_list = list(qs)

        try:
            stock_entry = DailyStock.objects.get(date=date_filter, driver=driver_filter)
            loaded_saved = stock_entry.initial or {}
            has_saved_load = True
        except DailyStock.DoesNotExist:
            loaded_saved = {}
            has_saved_load = False

        stock_products = _stock_products_payload(deliveries_list, loaded_saved)
        skus = [product['id'] for product in stock_products]
        required  = {sku: 0 for sku in skus}
        delivered = {sku: 0 for sku in skus}

        for delivery in deliveries_list:
            for sku, qty in (delivery.stock_items or {}).items():
                qty = int(qty or 0)
                if sku not in required:
                    continue
                required[sku] += qty
                if delivery.completed:
                    delivered[sku] += qty

        loaded = {sku: int(loaded_saved.get(sku, 0) or 0) for sku in skus}
        pending = {sku: required[sku] - delivered[sku] for sku in skus}
        coverage = {sku: loaded[sku] - required[sku] for sku in skus}

        alerts = []
        if has_saved_load:
            for product in stock_products:
                sku = product['id']
                if loaded[sku] < required[sku]:
                    alerts.append({
                        'product_id':   sku,
                        'product_name': product['name'],
                        'unit':         product['unit'],
                        'loaded':       loaded[sku],
                        'required':     required[sku],
                        'shortage':     required[sku] - loaded[sku],
                    })

        return JsonResponse({
            "date": date_filter, "driver": driver_filter,
            "products": stock_products,
            "required": required, "demand": required,
            "loaded": loaded, "initial": loaded,
            "delivered": delivered, "pending": pending,
            "coverage": coverage, "has_saved_load": has_saved_load,
            "alerts": alerts,
            "deliveries_count": len(deliveries_list),
            "deliveries_detail": [
                {"id": d.id, "name": d.name, "completed": d.completed,
                 "driver": d.driver, "stock_items": d.stock_items or {}}
                for d in deliveries_list
            ],
        })

    # POST
    data    = json.loads(request.body)
    day     = data.get("date", date.today().isoformat())
    driver  = data.get("driver", "").lower().strip()
    loaded  = data.get("loaded", data.get("initial", {}))

    if not driver:
        return JsonResponse({"error": "driver requerido"}, status=400)

    DailyStock.objects.update_or_create(
        date=day, driver=driver,
        defaults={"initial": loaded}
    )
    return JsonResponse({
        "ok": True, "date": day, "driver": driver,
        "loaded": loaded, "initial": loaded,
    })


@require_http_methods(["GET"])
def stock_summary(request):
    date_filter = request.GET.get("date", date.today().isoformat())
    qs = Delivery.objects.filter(delivery_date=date_filter)
    stock_products = _stock_products_payload(list(qs), {})
    skus = [product['id'] for product in stock_products]

    summary = {}
    for driver in ["jorge", "diego", "otro"]:
        required = {sku: 0 for sku in skus}
        driver_qs = qs.filter(driver=driver)
        for delivery in driver_qs:
            for sku, qty in (delivery.stock_items or {}).items():
                if sku in required:
                    required[sku] += int(qty or 0)
        summary[driver] = {
            "total_deliveries": driver_qs.count(),
            "required": required,
            "demand": required,
        }

    return JsonResponse({
        "date": date_filter, "summary": summary,
        "products": stock_products,
    })