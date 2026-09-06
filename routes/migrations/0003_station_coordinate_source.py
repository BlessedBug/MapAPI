from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("routes", "0002_fuelpriceobservation")]

    operations = [
        migrations.AddField(
            model_name="fuelstation",
            name="coordinate_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
