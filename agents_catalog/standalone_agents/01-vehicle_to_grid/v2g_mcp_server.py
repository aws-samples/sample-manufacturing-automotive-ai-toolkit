from typing import Optional
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

# Third Party
from mcp.server.fastmcp import FastMCP
import httpx

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("V2GServer")

# Constants
class Config:
    # Request API Key: https://apps.openei.org/services/api/signup/
    OPENEI_API_KEY = os.getenv("OPENEI_API_KEY", "")


@mcp.tool()
async def get_market_data(region: str) -> str:
    """Get current market prices and grid load data for a specific region.
    Args:
        region: str - Region code (e.g., 'CAL', 'NY', 'TEX')
    """
    async with httpx.AsyncClient() as client:
        # Get market prices and grid load from EIA
        eia_url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/"
        params = {
            "api_key": Config.OPENEI_API_KEY,
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": region,
            "facets[type][]": ["D", "LMP"],  # D for Demand, LMP for Locational Marginal Price
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 24
        }
        response = await client.get(eia_url, params=params, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            return json.dumps({
                "market_data": data,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return json.dumps({
                "error": "Failed to fetch market data",
                "status": response.status_code
            })


@mcp.tool()
async def get_utility_rates(zip_code: str, sector: str = "Residential") -> str:
    """Get utility rates for a specific location and return simplified data.
    Args:
        zip_code: str - ZIP code to look up rates for
        sector: str - Sector for the utility rates. Valid options: Residential, Commercial, Industrial, or Lighting
    Returns:
        str: JSON string containing simplified utility rate data
    """
    async with httpx.AsyncClient() as client:
        url = "https://api.openei.org/utility_rates"
        params = {
            "api_key": Config.OPENEI_API_KEY,
            "version": 3,
            "format": "json",
            "address": zip_code,
            "sector": sector
        }
        response = await client.get(url, params=params, timeout=30.0)

        if response.status_code != 200:
            return json.dumps({
                "error": "Failed to fetch utility rates",
                "status": response.status_code
            })

        # Parse and clean the response data
        data = response.json()

        def parse_date(date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return None

        # Create simplified version of items
        simplified_items = []
        for item in data.get('items', []):
            simplified_item = {
                'name': item.get('name', ''),
                'utility': item.get('utility', ''),
                'sector': item.get('sector', ''),
                'start_date': parse_date(item.get('startdate')),
                'end_date': parse_date(item.get('enddate')),
                'revision_count': len(item.get('revisions', [])),
                'approved': item.get('approved', False),
                'description': item.get('description', '').split('\n')[0],  # Just the first line
                'uri': item.get('uri', '')
            }
            simplified_items.append(simplified_item)

        # Sort items by name
        simplified_items.sort(key=lambda x: x['name'])

        # Create final response
        cleaned_response = {
            "count": len(simplified_items),
            "items": simplified_items
        }

        return json.dumps(cleaned_response, indent=2)


@mcp.tool()
async def optimize_schedule(
    region: str = "CAL",
    battery_capacity: float = 75.0,
    current_charge: float = 30.0,
    min_charge_needed: float = 20.0,
    arrival_time: Optional[str] = None,
    departure_time: Optional[str] = None,
    max_charge_rate: float = 11.5,
    discharge_enabled: bool = True,
    miles_needed: Optional[float] = None
) -> str:
    """Generate optimal charging/discharging schedule for an electric vehicle.

    Args:
        region: str - Region code (e.g., 'CAL', 'NY', 'TEX') to fetch market data
        battery_capacity: float - Battery capacity in kWh
        current_charge: float - Current charge level (0-100%)
        min_charge_needed: float - Minimum charge level needed (0-100%)
        arrival_time: Optional[str] - When vehicle is plugged in (time format like "2:00 PM")
        departure_time: Optional[str] - When vehicle needs to be ready (time format like "7:00 AM")
        max_charge_rate: float - Maximum charging rate in kW
        discharge_enabled: bool - Whether vehicle can discharge to grid
        miles_needed: Optional[float] - Minimum miles needed (will override min_charge_needed)

    Returns:
        str: JSON string containing optimized charging/discharging schedule
    """
    # Process time inputs
    now = datetime.now()

    # Handle arrival time
    if arrival_time is None:
        arrival_dt = now
    else:
        # Parse time strings like "2:00 PM"
        try:
            # Extract hours and minutes
            time_parts = arrival_time.replace("AM", "").replace("PM", "").strip().split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            # Adjust for PM
            if "PM" in arrival_time.upper() and hour < 12:
                hour += 12
            elif "AM" in arrival_time.upper() and hour == 12:
                hour = 0

            arrival_dt = now.replace(hour=hour, minute=minute)

            # If arrival time is in the past, assume it's for tomorrow
            if arrival_dt < now:
                arrival_dt += timedelta(days=1)
        except (ValueError, IndexError):
            arrival_dt = now

    # Handle departure time
    if departure_time is None:
        departure_dt = arrival_dt + timedelta(days=1)
    else:
        try:
            # Extract hours and minutes
            time_parts = departure_time.replace("AM", "").replace("PM", "").strip().split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            # Adjust for PM
            if "PM" in departure_time.upper() and hour < 12:
                hour += 12
            elif "AM" in departure_time.upper() and hour == 12:
                hour = 0

            departure_dt = now.replace(hour=hour, minute=minute)

            # If departure time is before arrival time, assume it's for the next day
            if departure_dt <= arrival_dt:
                departure_dt += timedelta(days=1)
        except (ValueError, IndexError):
            departure_dt = arrival_dt + timedelta(days=1)

    # Convert miles needed to charge percentage if provided
    if miles_needed is not None:
        # Assume average efficiency of 4 miles per kWh
        energy_needed_for_miles = miles_needed / 4.0
        min_charge_needed = (energy_needed_for_miles / battery_capacity) * 100

    # Get market data
    market_data = await get_market_data(region)

    # Parse market data
    try:
        market_data_dict = json.loads(market_data)
        if "error" in market_data_dict:
            return json.dumps({
                "error": f"Market data error: {market_data_dict['error']}",
                "user_message": "Unable to fetch electricity market data. Please try again later or specify a different region."
            })
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid market data format",
            "user_message": "There was a problem processing the market data. Please try again."
        })

    # Extract price and demand data
    price_data = []
    demand_data = []

    if "market_data" in market_data_dict and "response" in market_data_dict["market_data"]:
        for item in market_data_dict["market_data"]["response"]["data"]:
            period = item.get("period", "")
            value = item.get("value", 0)
            item_type = item.get("type", "")

            if item_type == "LMP":  # Locational Marginal Price
                price_data.append({"time": period, "price": value})
            elif item_type == "D":  # Demand
                demand_data.append({"time": period, "demand": value})

    # Sort data by time
    price_data.sort(key=lambda x: x["time"])
    demand_data.sort(key=lambda x: x["time"])

    # Calculate hours available for charging
    hours_available = max(1, int((departure_dt - arrival_dt).total_seconds() / 3600))

    # Calculate energy needed
    current_energy = battery_capacity * (current_charge / 100)
    target_energy = battery_capacity * (min_charge_needed / 100)
    energy_needed = max(0, target_energy - current_energy)

    # Create price map for all hours
    hourly_prices = {}
    for price_point in price_data:
        try:
            time = datetime.fromisoformat(price_point["time"].replace("Z", "+00:00"))
            # Use a 48-hour window to ensure we have enough data
            if now - timedelta(hours=24) <= time <= now + timedelta(hours=48):
                hourly_prices[time.isoformat()] = price_point["price"]
        except (ValueError, TypeError):
            continue

    # If we don't have enough price data, generate synthetic data
    if len(hourly_prices) < hours_available:
        # Create synthetic price data based on time of day
        for hour in range(48):
            time = now + timedelta(hours=hour)
            if time.isoformat() not in hourly_prices:
                # Higher prices during peak hours (4pm-9pm)
                if 16 <= time.hour <= 21:
                    price = 50.0 + (time.hour - 16) * 10  # Peak pricing
                # Medium prices during morning hours (7am-10am)
                elif 7 <= time.hour <= 10:
                    price = 35.0
                # Lower prices during night/early morning
                else:
                    price = 25.0
                hourly_prices[time.isoformat()] = price

    # Sort hours by price (cheapest first for charging, most expensive first for discharging)
    charging_hours = sorted(hourly_prices.items(), key=lambda x: x[1])
    discharging_hours = sorted(hourly_prices.items(), key=lambda x: x[1], reverse=True)

    # Filter hours to only include those between arrival and departure
    charging_hours = [(t, p) for t, p in charging_hours
                     if arrival_dt <= datetime.fromisoformat(t.replace("Z", "+00:00")) <= departure_dt]
    discharging_hours = [(t, p) for t, p in discharging_hours
                        if arrival_dt <= datetime.fromisoformat(t.replace("Z", "+00:00")) <= departure_dt]

    # Create schedule
    charging_schedule = []
    discharging_schedule = []

    # Calculate charging schedule
    energy_to_add = energy_needed

    for time_str, price in charging_hours:
        if energy_to_add <= 0:
            break

        # Calculate how much energy can be added in this hour
        energy_this_hour = min(energy_to_add, max_charge_rate)
        energy_to_add -= energy_this_hour

        if energy_this_hour > 0:
            time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            friendly_time = time_obj.strftime("%I:%M %p")

            charging_schedule.append({
                "time": time_str,
                "friendly_time": friendly_time,
                "action": "charge",
                "energy": round(energy_this_hour, 2),
                "price": round(price, 2),
                "cost": round(energy_this_hour * price / 1000, 2)  # Convert to cost in dollars
            })

    # Calculate discharging schedule if enabled
    if discharge_enabled:
        # Only consider discharging if we have enough charge and price is high enough
        avg_price = sum(p for _, p in charging_hours[:min(len(charging_hours), 5)]) / min(len(charging_hours), 5)
        discharge_threshold = avg_price * 1.5

        # Calculate available energy for discharge (don't go below target)
        max_discharge = current_energy - target_energy
        max_discharge = max(0, max_discharge)

        energy_to_discharge = max_discharge

        for time_str, price in discharging_hours:
            if energy_to_discharge <= 0 or price < discharge_threshold:
                break

            # Calculate how much energy can be discharged in this hour
            energy_this_hour = min(energy_to_discharge, max_charge_rate * 0.9)  # Assume 90% efficiency
            energy_to_discharge -= energy_this_hour

            if energy_this_hour > 0:
                time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                friendly_time = time_obj.strftime("%I:%M %p")

                discharging_schedule.append({
                    "time": time_str,
                    "friendly_time": friendly_time,
                    "action": "discharge",
                    "energy": round(energy_this_hour, 2),
                    "price": round(price, 2),
                    "revenue": round(energy_this_hour * price / 1000, 2)  # Convert to revenue in dollars
                })

    # Calculate financial summary
    total_cost = sum(item["cost"] for item in charging_schedule)
    total_revenue = sum(item["revenue"] for item in discharging_schedule)
    net_cost = total_cost - total_revenue

    # Create final schedule
    combined_schedule = sorted(
        charging_schedule + discharging_schedule,
        key=lambda x: x["time"]
    )

    # Format user-friendly response
    user_friendly = {
        "charging_times": [f"{item['friendly_time']} - {item['energy']:.1f} kWh at ${item['price']:.2f}/MWh"
                          for item in charging_schedule],
        "discharging_times": [f"{item['friendly_time']} - {item['energy']:.1f} kWh at ${item['price']:.2f}/MWh"
                             for item in discharging_schedule],
        "total_cost": f"${total_cost:.2f}",
        "total_revenue": f"${total_revenue:.2f}",
        "net_cost": f"${net_cost:.2f}",
        "savings": f"{(total_revenue / total_cost * 100) if total_cost > 0 else 0:.1f}%"
    }

    # Format response
    response = {
        "schedule": combined_schedule,
        "summary": {
            "total_charging_energy": round(sum(item["energy"] for item in charging_schedule), 2),
            "total_discharging_energy": round(sum(item["energy"] for item in discharging_schedule), 2),
            "total_cost": round(total_cost, 2),
            "total_revenue": round(total_revenue, 2),
            "net_cost": round(net_cost, 2),
            "savings_percentage": round((total_revenue / total_cost * 100) if total_cost > 0 else 0, 2)
        },
        "user_friendly": user_friendly,
        "input_parameters": {
            "battery_capacity": battery_capacity,
            "current_charge": current_charge,
            "min_charge_needed": min_charge_needed,
            "arrival_time": arrival_dt.isoformat(),
            "departure_time": departure_dt.isoformat(),
            "max_charge_rate": max_charge_rate,
            "discharge_enabled": discharge_enabled,
            "miles_needed": miles_needed
        },
        "timestamp": datetime.now().isoformat()
    }

    return json.dumps(response, indent=2)


@mcp.tool()
async def analyze_battery_degradation(
    vehicle_model: str,
    battery_capacity_kwh: float,
    current_cycles: int,
    proposed_schedule: str
) -> str:
    """Analyze the impact of a charging/discharging schedule on battery degradation.

    Args:
        vehicle_model: str - Vehicle model name
        battery_capacity_kwh: float - Battery capacity in kWh
        current_cycles: int - Current number of charge cycles
        proposed_schedule: str - JSON string of proposed charging/discharging schedule

    Returns:
        str: JSON string containing battery degradation analysis
    """
    try:
        schedule = json.loads(proposed_schedule)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Invalid schedule format"
        })

    # Calculate cycle depth and count from schedule
    charge_events = [item for item in schedule.get("schedule", []) if item.get("action") == "charge"]
    discharge_events = [item for item in schedule.get("schedule", []) if item.get("action") == "discharge"]

    total_charge = sum(event.get("energy", 0) for event in charge_events)
    total_discharge = sum(event.get("energy", 0) for event in discharge_events)

    # Calculate equivalent full cycles
    charge_cycles = total_charge / battery_capacity_kwh
    discharge_cycles = total_discharge / battery_capacity_kwh
    v2g_impact = discharge_cycles * 0.5  # V2G has less impact than full cycles

    total_new_cycles = charge_cycles + v2g_impact

    # Calculate degradation impact
    # Simple model: 20% capacity loss after 1500 cycles
    degradation_per_cycle = 20 / 1500  # % capacity loss per cycle

    new_degradation = total_new_cycles * degradation_per_cycle
    total_degradation = ((current_cycles + total_new_cycles) * degradation_per_cycle)

    # Calculate financial impact
    battery_replacement_cost = 150 * battery_capacity_kwh  # $150/kWh for replacement
    degradation_cost = (new_degradation / 100) * battery_replacement_cost

    return json.dumps({
        "vehicle_model": vehicle_model,
        "battery_capacity_kwh": battery_capacity_kwh,
        "current_cycles": current_cycles,
        "new_cycles_from_schedule": round(total_new_cycles, 3),
        "degradation": {
            "new_degradation_percent": round(new_degradation, 4),
            "total_degradation_percent": round(total_degradation, 4),
            "remaining_capacity_kwh": round(battery_capacity_kwh * (1 - total_degradation / 100), 2)
        },
        "financial_impact": {
            "degradation_cost_usd": round(degradation_cost, 2),
            "cost_per_kwh_cycled": round(degradation_cost / (total_charge + total_discharge), 4) if (total_charge + total_discharge) > 0 else 0
        },
        "recommendation": "The proposed schedule has a minimal impact on battery degradation." if new_degradation < 0.1 else "Consider reducing the number of discharge cycles to preserve battery health."
    }, indent=2)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
