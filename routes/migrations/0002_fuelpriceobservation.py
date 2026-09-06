from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("routes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FuelPriceObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("retail_price", models.DecimalField(decimal_places=3, max_digits=6)),
                ("source_row", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("station", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="price_observations", to="routes.fuelstation")),
            ],
            options={"ordering": ["source_row"]},
        ),
        migrations.AddConstraint(
            model_name="fuelpriceobservation",
            constraint=models.UniqueConstraint(fields=("station", "source_row"), name="unique_station_source_row"),
        ),
        migrations.AddIndex(
            model_name="fuelpriceobservation",
            index=models.Index(fields=["station", "source_row"], name="routes_fuel_station_0d31fd_idx"),
        ),
        migrations.AddIndex(
            model_name="fuelpriceobservation",
            index=models.Index(fields=["station", "retail_price"], name="routes_fuel_station_7f6b61_idx"),
        ),
    ]
