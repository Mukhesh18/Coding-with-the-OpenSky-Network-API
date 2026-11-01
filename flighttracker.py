import json
from datetime import datetime
from typing import Dict, List, Optional
import requests


class OpenSkyFlightInfo:
  """Class to interact with OpenSky Network API and retrieve flight information."""

  BASE_URL = "https://opensky-network.org/api"

  def __init__(
      self, username: Optional[str] = None, password: Optional[str] = None
  ):
    self.session = requests.Session()
    self.session.headers.update({
        "User-Agent": "FlightInfoScript/1.0",
    })
    self.username = username
    self.password = password
    self.route_cache = {}

  def get_all_flights(self) -> Optional[List[Dict]]:
    try:
      url = f"{self.BASE_URL}/states/all"
      response = self.session.get(url, timeout=10)
      response.raise_for_status()

      data = response.json()

      if "states" not in data or data["states"] is None:
        print("No flight data available at this time.")
        return []

      flights = []

      for state in data["states"]:
        if state is None:
          continue

        flight_info = {
            "icao24": state[0] if len(state) > 0 else "N/A",
            "callsign": (state[1] or "N/A").strip()
            if len(state) > 1 and state[1]
            else "N/A",
            "origin_country": state[2] if len(state) > 2 else "N/A",
            "time_position": state[3] if len(state) > 3 else None,
            "last_contact": state[4] if len(state) > 4 else None,
            "longitude": state[5] if len(state) > 5 else None,
            "latitude": state[6] if len(state) > 6 else None,
            "baro_altitude": state[7] if len(state) > 7 else None,
            "on_ground": state[8] if len(state) > 8 else False,
            "velocity": state[9] if len(state) > 9 else None,
            "true_track": state[10] if len(state) > 10 else None,
            "vertical_rate": state[11] if len(state) > 11 else None,
            "geo_altitude": state[13] if len(state) > 13 else None,
            "squawk": state[14] if len(state) > 14 else None,
        }
        flights.append(flight_info)

      return flights

    except requests.exceptions.RequestException as e:
      print(f"Error connecting to OpenSky API: {e}")
      return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
      print(f"Error parsing API response: {e}")
      return None

  def format_altitude(self, altitude: Optional[float]) -> str:
    if altitude is None:
      return "N/A"
    return f"{altitude:.0f} m"

  def format_velocity(self, velocity: Optional[float]) -> str:
    if velocity is None:
      return "N/A"
    velocity_kmh = velocity * 3.6
    return f"{velocity_kmh:.0f} km/h"

  def format_coordinates(
      self, lat: Optional[float], lon: Optional[float]
  ) -> str:
    if lat is None or lon is None:
      return "N/A"
    return (
        f"{lat:.4f}°N, {lon:.4f}°E"
        if lat >= 0
        else f"{abs(lat):.4f}°S, {lon:.4f}°E"
    )

  def format_timestamp(self, timestamp: Optional[int]) -> str:
    if timestamp is None:
      return "N/A"
    try:
      dt = datetime.fromtimestamp(timestamp)
      return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
      return "N/A"

  def get_flight_route(
      self,
      icao24: str,
      begin: Optional[int] = None,
      end: Optional[int] = None,
  ) -> Optional[Dict]:
    if not icao24 or icao24 == "N/A":
      return None

    if icao24 in self.route_cache:
      return self.route_cache[icao24]

    try:
      if end is None:
        end = int(datetime.now().timestamp())
      if begin is None:
        begin = end - 172800

      url = f"{self.BASE_URL}/flights/aircraft"
      params = {"icao24": icao24, "begin": begin, "end": end}

      auth = (
          (self.username, self.password)
          if self.username and self.password
          else None
      )

      response = self.session.get(url, params=params, auth=auth, timeout=10)

      if response.status_code == 401:
        response = self.session.get(url, params=params, timeout=10)

      if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
          flight_data = data[0]
          route_info = {
              "departure_airport": flight_data.get("estDepartureAirport")
              or "N/A",
              "arrival_airport": flight_data.get("estArrivalAirport") or "N/A",
              "departure_time": flight_data.get("firstSeen"),
              "arrival_time": flight_data.get("lastSeen"),
          }
          if (
              route_info["departure_airport"] != "N/A"
              or route_info["arrival_airport"] != "N/A"
          ):
            self.route_cache[icao24] = route_info
          return route_info

    except:
      pass

    return None

  def enrich_flights_with_routes(
      self, flights: List[Dict], max_requests: int = 20
  ) -> List[Dict]:
    enriched = []
    requests_made = 0

    for flight in flights:
      icao24 = flight.get("icao24")
      callsign = flight.get("callsign", "N/A")

      if (
          icao24
          and icao24 != "N/A"
          and callsign != "N/A"
          and len(callsign.strip()) > 0
          and requests_made < max_requests
      ):
        route_info = self.get_flight_route(icao24)
        if route_info:
          flight["departure_airport"] = route_info.get("departure_airport")
          flight["arrival_airport"] = route_info.get("arrival_airport")
          flight["departure_time"] = route_info.get("departure_time")
          flight["arrival_time"] = route_info.get("arrival_time")
          requests_made += 1
        else:
          flight["departure_airport"] = None
          flight["arrival_airport"] = None
          flight["departure_time"] = None
          flight["arrival_time"] = None
      else:
        flight["departure_airport"] = None
        flight["arrival_airport"] = None
        flight["departure_time"] = None
        flight["arrival_time"] = None

      enriched.append(flight)

    return enriched
