def calculate_fuel_gallons(distance_miles, mpg=10.0):
    return round(distance_miles / mpg, 2)

def calculate_stop_cost(gallons, retail_price):
    return round(gallons * float(retail_price), 2)

def calculate_total_cost(stops):
    return round(sum(stop["estimated_cost"] for stop in stops), 2)