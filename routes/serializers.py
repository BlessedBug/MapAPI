from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=255, trim_whitespace=True)
    destination = serializers.CharField(max_length=255, trim_whitespace=True)
    origin_fuel_price = serializers.DecimalField(max_digits=6, decimal_places=3, min_value=0, required=False, default=3.0)
    initial_fuel_gallons = serializers.FloatField(required=False,default=30.0,min_value=0.0,max_value=50.0)

    def validate(self, attrs):
        if attrs["origin"].casefold() == attrs["destination"].casefold():
            raise serializers.ValidationError("Origin and destination must be different.")
        return attrs
