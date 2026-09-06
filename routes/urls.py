from django.urls import path
from .views import RouteOptimizationView

urlpatterns = [
    path('', RouteOptimizationView.as_view(), name='route_home'),
]