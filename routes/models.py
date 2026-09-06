from django.db import models

# Create your models here.
from django.db import models


class FuelStation(models.Model):
    truckstop_id = models.BigIntegerField(
        unique=True,
        db_index=True,
    )

    name = models.CharField(
        max_length=255,
    )

    address = models.CharField(
        max_length=255,
    )

    city = models.CharField(
        max_length=100,
        db_index=True,
    )

    state = models.CharField(
        max_length=2,
        db_index=True,
    )

    rack_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    retail_price = models.DecimalField(
        max_digits=6,
        decimal_places=3,
    )

    latitude = models.FloatField(
        null=True,
        blank=True,
    )

    longitude = models.FloatField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["state", "city", "name"]
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"