from django.contrib import admin

from .models import Material, CommercialProduct, ProductComponent


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display  = ('sku', 'name', 'unit', 'active', 'sort_order')
    list_editable = ('active', 'sort_order')
    list_filter   = ('active',)
    search_fields = ('sku', 'name', 'unit')
    ordering      = ('sort_order', 'sku')


class ProductComponentInline(admin.TabularInline):
    model             = ProductComponent
    extra             = 1
    autocomplete_fields = ('material',)
    fields            = ('material', 'quantity')
    ordering          = ('material__sort_order', 'material_id')


@admin.register(CommercialProduct)
class CommercialProductAdmin(admin.ModelAdmin):
    list_display  = ('label', 'active', 'sort_order')
    list_editable = ('active', 'sort_order')
    list_filter   = ('active',)
    search_fields = ('label',)
    ordering      = ('sort_order', 'label')
    inlines       = (ProductComponentInline,)


@admin.register(ProductComponent)
class ProductComponentAdmin(admin.ModelAdmin):
    list_display  = ('product', 'material', 'quantity')
    list_filter   = ('product', 'material')
    search_fields = ('product__label', 'material__sku', 'material__name')
    autocomplete_fields = ('product', 'material')
