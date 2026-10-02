from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer
from .services.geocoding import geocode_location
from .services.routing import get_route
from .services.stations import find_route_stations
from .services.optimizer import build_fuel_plan
from django.conf import settings

class RouteOptimizationView(APIView):
    """
    POST /api/v1/route/optimize/
    {
      "start": "New York, NY",
      "finish": "Chicago, IL"
    }
    """

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_text = serializer.validated_data["start"]
        finish_text = serializer.validated_data["finish"]

        try:
            start = geocode_location(start_text)
            finish = geocode_location(finish_text)

            route = get_route(start["lon"], start["lat"], finish["lon"], finish["lat"])

            stations = find_route_stations(
                route["geometry"]["coordinates"],
                route["distance_miles"],
                corridor_miles=settings.ROUTE_CORRIDOR_MILES,
            )

            plan = build_fuel_plan(
                stations=stations,
                route_distance_miles=route["distance_miles"],
                max_range_miles=settings.MAX_RANGE_MILES,
                mpg=settings.MPG,
                initial_fuel_gallons=settings.INITIAL_FUEL_GALLONS,
            )

            return Response(
                {
                    "start": start,
                    "finish": finish,
                    "route": route,
                    "fuel": {
                        "mpg": settings.MPG,
                        "max_range_miles": settings.MAX_RANGE_MILES,
                        "initial_fuel_gallons": settings.INITIAL_FUEL_GALLONS,
                        "total_gallons_consumed": round(
                            route["distance_miles"] / settings.MPG, 2
                        ),
                        "total_cost": round(plan["total_cost"], 2),
                    },
                    "fuel_stops": plan["stops"],
                    "assumptions": {
                        "route_corridor_miles": settings.ROUTE_CORRIDOR_MILES,
                        "initial_tank_is_full": True,
                        "optimization": (
                            "At each stop, buy enough to reach the first cheaper "
                            "reachable station; otherwise fill to the maximum range "
                            "or only enough to reach the destination."
                        ),
                    },
                },
                status=status.HTTP_200_OK,
            )

        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as exc:
            return Response(
                {"error": "Unable to calculate route.", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
