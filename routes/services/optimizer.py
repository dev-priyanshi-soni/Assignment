from __future__ import annotations

from typing import Any


def build_fuel_plan(
    stations: list[dict[str, Any]],
    route_distance_miles: float,
    max_range_miles: float,
    mpg: float,
    initial_fuel_gallons: float,
) -> dict[str, Any]:
    """
    Build a cost-aware fuel plan for a route.

    Assumptions:
    - Vehicle starts with initial_fuel_gallons.
    - max_range_miles represents the maximum distance on a full tank.
    - mpg is constant.
    - Fuel prices are provided per gallon.
    - Fuel can be purchased at any matched station.
    - Stations are already associated with positions along the route.
    """

    if route_distance_miles < 0:
        raise ValueError("Route distance cannot be negative.")

    if max_range_miles <= 0:
        raise ValueError("Maximum range must be greater than zero.")

    if mpg <= 0:
        raise ValueError("MPG must be greater than zero.")

    if initial_fuel_gallons < 0:
        raise ValueError("Initial fuel cannot be negative.")

    tank_capacity_gallons = max_range_miles / mpg

    if initial_fuel_gallons > tank_capacity_gallons:
        initial_fuel_gallons = tank_capacity_gallons

    # No fuel stop is necessary if the vehicle can complete
    # the entire trip with its starting fuel.
    initial_range = initial_fuel_gallons * mpg

    if route_distance_miles <= initial_range:
        gallons_used = route_distance_miles / mpg

        return {
            "stops": [],
            "total_cost": 0.0,
            "total_gallons_purchased": 0.0,
            "gallons_used": round(gallons_used, 3),
        }

    # Work only with stations that have valid route positions/prices.
    usable_stations = []

    for station in stations:
        position = station.get("route_position_miles")
        price = station.get("price")

        if position is None or price is None:
            continue

        try:
            position = float(position)
            price = float(price)
        except (TypeError, ValueError):
            continue

        if position <= 0 or position >= route_distance_miles:
            continue

        if price < 0:
            continue

        usable_stations.append(
            {
                **station,
                "route_position_miles": position,
                "price": price,
            }
        )

    # Sort stations according to their position on the route.
    usable_stations.sort(key=lambda station: station["route_position_miles"])

    if not usable_stations:
        raise ValueError(
            "The route is longer than the available starting fuel, "
            "but no usable fuel stations were found."
        )

    # Remove duplicate station positions by keeping the cheapest
    # station at the same route position.
    deduplicated = {}

    for station in usable_stations:
        position = station["route_position_miles"]

        if (
            position not in deduplicated
            or station["price"] < deduplicated[position]["price"]
        ):
            deduplicated[position] = station

    usable_stations = sorted(
        deduplicated.values(),
        key=lambda station: station["route_position_miles"],
    )

    stops: list[dict[str, Any]] = []

    total_cost = 0.0
    total_gallons_purchased = 0.0

    current_position = 0.0
    current_fuel = initial_fuel_gallons

    while current_position < route_distance_miles:

        # ---------------------------------------------------------
        # Find the next station we can physically reach.
        # ---------------------------------------------------------
        reachable = []

        for station in usable_stations:
            station_position = station["route_position_miles"]

            if station_position <= current_position:
                continue

            distance = station_position - current_position

            if distance <= current_fuel * mpg + 1e-9:
                reachable.append(station)

        # Can we reach the destination directly?
        distance_to_finish = route_distance_miles - current_position

        if distance_to_finish <= current_fuel * mpg + 1e-9:
            fuel_needed = distance_to_finish / mpg
            current_fuel -= fuel_needed
            current_position = route_distance_miles
            break

        # We need another fuel stop.
        if not reachable:
            raise ValueError(
                "The selected station sequence is not reachable "
                "with the available fuel."
            )

        current_station = reachable[0]
        current_station_position = current_station["route_position_miles"]

        # ---------------------------------------------------------
        # Look for a cheaper station that can be reached from the
        # current station with a full tank.
        #
        # If we find one, we only buy enough fuel to get there.
        # Otherwise, we fill enough to reach the destination or
        # maximize the useful next leg.
        # ---------------------------------------------------------

        cheaper_station = None

        for candidate in usable_stations:
            candidate_position = candidate["route_position_miles"]

            if candidate_position <= current_station_position:
                continue

            distance_to_candidate = (
                candidate_position - current_station_position
            )

            if distance_to_candidate > max_range_miles:
                break

            if candidate["price"] < current_station["price"]:
                cheaper_station = candidate
                break

        # ---------------------------------------------------------
        # First, calculate how much fuel we need to reach the
        # current station.
        # ---------------------------------------------------------

        distance_to_station = current_station_position - current_position
        fuel_needed_to_station = distance_to_station / mpg

        if current_fuel < fuel_needed_to_station - 1e-9:
            raise ValueError(
                f"Cannot reach station {current_station['name']} "
                f"at mile {current_station_position:.1f}."
            )

        current_fuel -= fuel_needed_to_station
        current_position = current_station_position

        # ---------------------------------------------------------
        # Calculate fuel purchase at this station.
        # ---------------------------------------------------------

        if cheaper_station is not None:
            target_position = cheaper_station["route_position_miles"]

            distance_to_cheaper = target_position - current_position

            required_fuel = distance_to_cheaper / mpg

            # Buy enough to reach the cheaper station.
            gallons_to_buy = max(0.0, required_fuel - current_fuel)

        else:
            # No cheaper station within one full tank.
            #
            # Buy enough to reach the destination if possible.
            # Otherwise fill the tank.
            distance_to_destination = route_distance_miles - current_position
            fuel_needed_for_destination = distance_to_destination / mpg

            gallons_to_buy = max(
                0.0,
                min(
                    tank_capacity_gallons - current_fuel,
                    fuel_needed_for_destination - current_fuel,
                ),
            )

            # If the destination requires more than one tank,
            # fill the tank so we can reach the next station.
            if gallons_to_buy <= 0:
                gallons_to_buy = max(
                    0.0,
                    tank_capacity_gallons - current_fuel,
                )

        # Never exceed tank capacity.
        gallons_to_buy = min(
            gallons_to_buy,
            tank_capacity_gallons - current_fuel,
        )

        gallons_to_buy = round(gallons_to_buy, 3)

        if gallons_to_buy > 0:
            cost = gallons_to_buy * current_station["price"]

            stop = {
                "truckstop_id": current_station.get("truckstop_id"),
                "name": current_station.get("name"),
                "address": current_station.get("address"),
                "city": current_station.get("city"),
                "state": current_station.get("state"),
                "latitude": current_station.get("latitude"),
                "longitude": current_station.get("longitude"),
                "route_position_miles": round(
                    current_station_position,
                    2,
                ),
                "price_per_gallon": round(
                    current_station["price"],
                    4,
                ),
                "gallons_purchased": gallons_to_buy,
                "cost": round(cost, 2),
            }

            stops.append(stop)

            current_fuel += gallons_to_buy
            total_cost += cost
            total_gallons_purchased += gallons_to_buy

    return {
        "stops": stops,
        "total_cost": round(total_cost, 2),
        "total_gallons_purchased": round(
            total_gallons_purchased,
            3,
        ),
        "gallons_used": round(
            route_distance_miles / mpg,
            3,
        ),
    }