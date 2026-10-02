from django.urls import path
from .views import RouteOptimizationView

urlpatterns = [
    path("route/optimize/", RouteOptimizationView.as_view(), name="route-optimize"),
]
