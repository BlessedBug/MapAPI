from django.db import models


class FuelStation(models.Model):

    truckstop_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.CharField(max_length=50, blank=True, null=True)

    retail_price = models.DecimalField(max_digits=6, decimal_places=3)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    coordinate_source = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "city", "name"]
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def get_effective_price(self):

        return self.retail_price

    @property
    def effective_price_policy(self):
        return "latest_source_row"

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"


class FuelPriceObservation(models.Model):

    station = models.ForeignKey(
        FuelStation,
        on_delete=models.CASCADE,
        related_name="price_observations",
    )
    retail_price = models.DecimalField(max_digits=6, decimal_places=3)
    source_row = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_row"]
        constraints = [
            models.UniqueConstraint(
                fields=["station", "source_row"],
                name="unique_station_source_row",
            )
        ]
        indexes = [
            models.Index(fields=["station", "source_row"]),
            models.Index(fields=["station", "retail_price"]),
        ]

    def __str__(self):
        return f"{self.station_id}: ${self.retail_price} (row {self.source_row})"
