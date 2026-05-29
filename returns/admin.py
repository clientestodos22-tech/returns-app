from django.contrib import admin
from .models import ReturnRequest


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = [
        'fecha_recepcion',
        'numero_documento',
        'documento_ingreso',
        'cliente',
        'sku',
        'cantidad',
        'estado',
        'responsable',
        'creado_en',
    ]

    list_filter = [
        'estado',
        'cliente',
        'responsable',
        'fecha_recepcion',
    ]

    search_fields = [
        'numero_documento',
        'documento_ingreso',
        'cliente',
        'sku',
        'codigo_numerico',
        'serie',
        'responsable',
    ]