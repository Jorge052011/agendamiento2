import json
from datetime import datetime, date
from collections import defaultdict

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render

from .models import Client, Delivery, DailyStock, OptRoute, Config
from .utils import normalize_phone, haversine, nearest_neighbor_route


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
    phone  = normalize_phone(data.get("phone", ""))
    client = None
    try:
        client = Client.objects.get(phone=phone)
    except Client.DoesNotExist:
        pass

    address = (data.get("formatted_address") or data.get("address", "")).strip()
    if not address and client:
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
        name             = name,
        address          = address,
        formatted_address= (data.get("formatted_address", "").strip() or
                            (client.formatted_address if client else "")),
        place_id         = (data.get("place_id", "").strip() or
                            (client.place_id if client else "")),
        reference        = (data.get("reference", "").strip() or
                            (client.reference if client else "")),
        product          = data.get("product", "").strip(),
        amount           = data.get("amount", "").strip(),
        payment          = data.get("payment", "").strip(),
        driver           = driver,
        time_start       = data.get("time_start", ""),
        time_end         = data.get("time_end", ""),
        notes            = data.get("notes", "").strip(),
        lat              = data.get("lat") or (client.lat if client else None),
        lng              = data.get("lng") or (client.lng if client else None),
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
#  OPTIMIZADOR
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def optimize(request):
    data          = json.loads(request.body)
    origin        = data.get("origin")
    driver        = data.get("driver", "")
    day           = data.get("date", date.today().isoformat())
    driver_filter = data.get("driver_filter", True)

    if not origin:
        return JsonResponse({"error": "Punto de partida requerido"}, status=400)

    origin_ref = (origin.get("place_id") or origin.get("formatted_address") or origin.get("address"))
    if not origin_ref:
        return JsonResponse({"error": "Punto de partida requerido"}, status=400)

    qs = Delivery.objects.filter(delivery_date=day, completed=False)
    if driver_filter and driver:
        qs = qs.filter(driver=driver)

    clients_map = {c.phone: c for c in Client.objects.all()}

    stops = []
    for d in qs:
        client = clients_map.get(d.client_phone)
        lat = d.lat or (client.lat if client else None)
        lng = d.lng or (client.lng if client else None)
        stop_ref = (d.place_id or d.formatted_address or d.address or
                    (client.place_id if client else None) or
                    (client.formatted_address if client else None) or
                    (client.address if client else None))
        if not stop_ref:
            continue

        stop = d.to_dict(client=client)
        stop["route_ref"] = stop_ref
        stop["lat"]       = lat
        stop["lng"]       = lng
        if not stop.get("name") and client:
            stop["name"] = client.name
        if not stop.get("reference") and client:
            stop["reference"] = client.reference
        stops.append(stop)

    if not stops:
        return JsonResponse(
            {"error": "No hay entregas pendientes con dirección válida para este día"},
            status=404)

    stops_with_coords = [s for s in stops if s.get("lat") and s.get("lng")]
    stops_without     = [s for s in stops if not (s.get("lat") and s.get("lng"))]

    if stops_with_coords and origin.get("lat") and origin.get("lng"):
        ordered = nearest_neighbor_route(origin, stops_with_coords) + stops_without
    else:
        ordered = stops

    total_km = 0.0
    if origin.get("lat") and ordered:
        prev = origin
        for s in ordered:
            if s.get("lat") and s.get("lng"):
                total_km += haversine(float(prev["lat"]), float(prev["lng"]),
                                      float(s["lat"]),    float(s["lng"]))
                prev = s
    total_km = round(total_km, 2)

    def location_for_url(item):
        lat = item.get("lat")
        lng = item.get("lng")
        if lat and lng:
            return f"{lat},{lng}"
        return item.get("formatted_address") or item.get("address") or ""

    import urllib.parse
    origin_str = location_for_url(origin)
    if len(ordered) == 1:
        dest_str      = location_for_url(ordered[0])
        waypoints_str = ""
    else:
        dest_str      = location_for_url(ordered[-1])
        waypoints_str = "|".join(location_for_url(s) for s in ordered[:-1])

    maps_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={urllib.parse.quote(str(origin_str))}"
        f"&destination={urllib.parse.quote(str(dest_str))}"
        f"&travelmode=driving"
    )
    if waypoints_str:
        maps_url += f"&waypoints={urllib.parse.quote(waypoints_str)}"

    return no_cache(JsonResponse({
        "origin":   origin,
        "ordered":  ordered,
        "stops":    len(ordered),
        "total_km": total_km,
        "maps_url": maps_url,
    }))


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
        return JsonResponse({"google_maps_key": key, "departure_points": departure_points})

    data = json.loads(request.body)
    if "departure_points" in data:
        Config.objects.update_or_create(
            key="departure_points",
            defaults={"value": data["departure_points"]}
        )
    return JsonResponse({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  GPS TRACKING (en memoria — sin cambios)
# ═══════════════════════════════════════════════════════════════════════════════

_gps_store = {}

@csrf_exempt
@require_http_methods(["POST"])
def gps_update(request):
    data   = json.loads(request.body)
    driver = data.get("driver", "").lower().strip()
    lat    = data.get("lat")
    lng    = data.get("lng")

    if not driver or lat is None or lng is None:
        return JsonResponse({"error": "driver, lat y lng requeridos"}, status=400)

    prev  = _gps_store.get(driver, {})
    trail = prev.get("trail", [])
    trail = (trail + [[lat, lng]])[-200:]

    _gps_store[driver] = {
        "driver": driver, "lat": lat, "lng": lng,
        "trail": trail, "ts": datetime.now().isoformat(),
    }
    return JsonResponse({"ok": True})


@require_http_methods(["GET"])
def gps_status(request):
    return JsonResponse(list(_gps_store.values()), safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def gps_clear(request):
    data   = json.loads(request.body)
    driver = data.get("driver", "").lower().strip()
    if driver in _gps_store:
        del _gps_store[driver]
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
#  PRODUCTOS
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCTS = [
    {"id": "LAV-8",     "name": "Arena Lavanda",             "unit": "Bolsa 8kg",  "color": "#f0e040"},
    {"id": "LAV-20",    "name": "Arena Lavanda",             "unit": "Bolsa 20kg", "color": "#f0e040"},
    {"id": "LAV-CA-8",  "name": "Arena Lavanda + Carbón",    "unit": "Bolsa 8kg",  "color": "#40c8f0"},
    {"id": "LAV-CA-20", "name": "Arena Lavanda + Carbón",    "unit": "Bolsa 20kg", "color": "#40c8f0"},
    {"id": "CA-TB-20",  "name": "Arena Carbón + Talco Bebé", "unit": "Bolsa 20kg", "color": "#f04090"},
]

@require_http_methods(["GET"])
def products(request):
    return JsonResponse(PRODUCTS, safe=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  STOCK DIARIO
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

        demand    = {p["id"]: 0 for p in PRODUCTS}
        delivered = {p["id"]: 0 for p in PRODUCTS}

        for d in qs:
            items    = d.stock_items or {}
            has_items = any(int(v or 0) > 0 for v in items.values())
            if has_items:
                for pid, qty in items.items():
                    if pid in demand:
                        demand[pid] += int(qty or 0)
                if d.completed:
                    for pid, qty in items.items():
                        if pid in delivered:
                            delivered[pid] += int(qty or 0)

        pending = {pid: demand[pid] - delivered[pid] for pid in demand}

        try:
            stock_entry = DailyStock.objects.get(date=date_filter, driver=driver_filter)
            initial = stock_entry.initial
        except DailyStock.DoesNotExist:
            initial = {}

        balance = {}
        alerts  = []
        for p in PRODUCTS:
            pid = p["id"]
            ini = int(initial.get(pid, 0))
            bal = ini - delivered.get(pid, 0)
            balance[pid] = bal
            if bal < pending.get(pid, 0):
                alerts.append({
                    "product_id":   pid,
                    "product_name": p["name"],
                    "unit":         p["unit"],
                    "balance":      bal,
                    "pending":      pending[pid],
                    "shortage":     pending[pid] - bal,
                })

        return JsonResponse({
            "date": date_filter, "driver": driver_filter,
            "products": PRODUCTS, "demand": demand,
            "delivered": delivered, "pending": pending,
            "initial": initial, "balance": balance, "alerts": alerts,
            "deliveries_count": qs.count(),
            "deliveries_detail": [
                {"id": d.id, "name": d.name, "completed": d.completed,
                 "stock_items": d.stock_items or {}}
                for d in qs
            ],
        })

    # POST
    data   = json.loads(request.body)
    day    = data.get("date", date.today().isoformat())
    driver = data.get("driver", "").lower().strip()
    initial = data.get("initial", {})

    if not driver:
        return JsonResponse({"error": "driver requerido"}, status=400)

    DailyStock.objects.update_or_create(
        date=day, driver=driver,
        defaults={"initial": initial}
    )
    return JsonResponse({"ok": True, "date": day, "driver": driver, "initial": initial})


@require_http_methods(["GET"])
def stock_summary(request):
    date_filter = request.GET.get("date", date.today().isoformat())
    qs = Delivery.objects.filter(delivery_date=date_filter)

    summary = {}
    for driver in ["jorge", "diego", "otro"]:
        demand = {p["id"]: 0 for p in PRODUCTS}
        driver_qs = qs.filter(driver=driver)
        for d in driver_qs:
            items = d.stock_items or {}
            for pid, qty in items.items():
                if pid in demand:
                    demand[pid] += int(qty or 0)
        summary[driver] = {
            "total_deliveries": driver_qs.count(),
            "demand": demand,
        }

    return JsonResponse({"date": date_filter, "summary": summary, "products": PRODUCTS})