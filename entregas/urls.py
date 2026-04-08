from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/clients',                       views.clients,       name='clients'),
    path('api/clients/<str:phone>',           views.client_detail, name='client_detail'),
    path('api/deliveries',                    views.deliveries,    name='deliveries'),
    path('api/deliveries/<str:delivery_id>',  views.delivery_detail, name='delivery_detail'),
    path('api/calendar',  views.calendar,  name='calendar'),
    #path('api/optimize',  views.optimize,  name='optimize'),
    path('api/config',    views.config,    name='config'),
    # GPS tracking
    path('api/gps/update', views.gps_update, name='gps_update'),
    path('api/gps/status', views.gps_status, name='gps_status'),
    path('api/gps/clear',  views.gps_clear,  name='gps_clear'),
    # Ruta optimizada guardada (espejo servidor)
    path('api/opt-route', views.opt_route, name='opt_route'),
    # Stock / Carga del Día
    path('api/products',      views.products,      name='products'),
    path('api/stock',         views.stock,          name='stock'),
    path('api/stock/summary', views.stock_summary,  name='stock_summary'),
]