from django.contrib import admin

from .models import FuelPriceObservation, FuelStation


class FuelPriceObservationInline(admin.TabularInline):
    model = FuelPriceObservation
    extra = 0
    readonly_fields = ("source_row", "created_at")
    ordering = ("source_row",)


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = (
        "truckstop_id", "name", "city", "state", "retail_price",
        "latitude", "longitude",
    )
    search_fields = ("name", "city", "state", "truckstop_id")
    list_filter = ("state",)
    inlines = (FuelPriceObservationInline,)


@admin.register(FuelPriceObservation)
class FuelPriceObservationAdmin(admin.ModelAdmin):
    list_display = ("station", "retail_price", "source_row", "created_at")
    search_fields = ("station__truckstop_id", "station__name")
    list_select_related = ("station",)
