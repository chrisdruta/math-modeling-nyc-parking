import math
import numpy as np

import googlemaps
import geopandas
import pyproj
from shapely.geometry import Point

import parser
from mock_client import MockClient

# Setting up coordinate transformer
_zoneIdMap = parser.readZoneIdMap()
_zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')
_zoneCentroids = {(i + 1): p for i, p in enumerate(_zoneMap['geometry'].centroid)}
_zoneRadiusMap = parser.readZoneRadiusMap(_zoneMap)

_zoneMapCrs = pyproj.CRS.from_user_input(_zoneMap.crs)
_geodeticCrs = _zoneMapCrs.to_geodetic()
transformer = pyproj.Transformer.from_crs(_geodeticCrs, _zoneMapCrs)

class Vehicle:
    def __init__(self, zoneId):
        self.currentZone = zoneId
        self.travelZone = None
        self.nextZone = None
        self.travelTimeRemaining = 0 # in minutes
        self.nextTravelTimeRemaining = 0
        self.route = None

    def __str__(self):
        return f"Id: {hex(id(self))}, Curr Zone: {self.currentZone}, Travel Zone: {self.travelZone}, Next Zone: {self.nextZone}, Travel Time Remaining: {self.travelTimeRemaining}"
    
    def getCurrentZone(self):
        if self.route is None:
            return self.currentZone
        else:
            # From google maps route, convert long lat to zone id on map w/ geopanda
            # TODO: Speed this up - giving a big slow down
            timeGoal = sum(step[0] for step in self.route) - self.travelTimeRemaining
            timeSum = 0
            bestDistance = 100000
            bestId = None
            for step in self.route:
                timeSum += step[0]
                if timeSum >= timeGoal:
                    x, y = transformer.transform(step[1][0], step[1][1])
                    #print(f"Transformed coords: {x},{y}")
                    for zoneId, point in _zoneCentroids.items():
                        distance = point.distance(Point(x, y))
                        if  distance < bestDistance:
                            bestDistance = distance
                            bestId = zoneId
                    break
            if bestId != None:
                return bestId
            else:
                raise RuntimeError("Route crawl failed to transform lat lng to zone id")

    def getCurrentBestLocationForAPI(self):
        if self.route is None:
            return _zoneIdMap[self.currentZone]
        else:
            timeGoal = sum(step[0] for step in self.route) - self.travelTimeRemaining
            timeSum = 0
            for step in self.route:
                timeSum += step[0]
                if timeSum >= timeGoal:
                    # Format: "lat,long"
                    return f"{step[1][0]},{step[1][1]}"
            raise RuntimeError("Route crawl failed for best location")

class VehicleController:
    def __init__(self, n, zoneDist):
        self.fleetSize = n
        self.zoneDist = zoneDist

        self.roamingVehicles = []
        self.parkedVehicles = []
        self.travelingVehicles = []

        self.highPriorityTrips = []

        # TODO: self.gmapsClient = googlemaps.Client(key='Add Your Key here')
        self.gmapsClient = MockClient()

        # Give all parked vehicles initial positions
        sample = np.random.choice(list(self.zoneDist.keys()),
                                    size=self.fleetSize,
                                    p=list(self.zoneDist.values()))
        for i in range(self.fleetSize):
            self.parkedVehicles.append(Vehicle(sample[i]))

    def updateVehicles(self):

        for vehicle in self.roamingVehicles:
            vehicle.travelTimeRemaining -= 1

            if vehicle.travelTimeRemaining < 0:
                raise RuntimeError("Not suposed to happen")

            if vehicle.travelTimeRemaining == 0:
                vehicle.currentZone = vehicle.travelZone
                vehicle.travelZone = None
                vehicle.nextZone = None
                vehicle.route = None

                #print("Vehicle stopped roaming")
                self.roamingVehicles.remove(vehicle)
                self.parkedVehicles.append(vehicle)

        for vehicle in self.travelingVehicles:
            vehicle.travelTimeRemaining -= 1

            if vehicle.travelTimeRemaining <= 0:
                # Case 1: Just picked up client, switching to drop off client
                if vehicle.nextZone != None and vehicle.nextZone > 0:
                    vehicle.currentZone = vehicle.travelZone
                    vehicle.travelZone = vehicle.nextZone
                    vehicle.nextZone = 0

                    vehicle.travelTimeRemaining = vehicle.nextTravelTimeRemaining
                    vehicle.nextTravelTimeRemaining = 0
                    #print(f"Client picked up: {vehicle}")
                
                # Case 2: Dropped off client, switching to roam
                elif vehicle.nextZone == 0:
                    randomZone = 50 # TODO: Pick this some how
                    vehicle.currentZone = vehicle.travelZone
                    vehicle.travelZone = randomZone
                    vehicle.nextZone = None

                    # Get new travel time + route
                    response = self.gmapsClient.directions(_zoneIdMap[vehicle.currentZone],
                                                            _zoneIdMap[vehicle.travelZone])
                    
                    steps = []
                    for step in response['routes'][0]['legs'][0]['steps']:
                        lat = step['end_location']['lat']
                        lng = step['end_location']['lng']
                        steps.append((math.ceil(step['duration']['value']/60), (lat, lng)))

                    # NOTE: There is a premium api for 'duration_in_traffic'
                    duration = math.ceil(response['routes'][0]['legs'][0]['duration']['value'] / 60)

                    vehicle.route = steps
                    vehicle.travelTimeRemaining = duration
                    vehicle.nextTravelTimeRemaining = 0

                    #print(f"Client dropped off, roaming: {vehicle}")

                    self.travelingVehicles.remove(vehicle)
                    self.roamingVehicles.append(vehicle)

    def matchVehicles(self, trips):

        googleMapsApiBuffer = []
        roamingBuffer = []
     
        tripsToMatch = self.highPriorityTrips + trips.tolist()

        for trip in tripsToMatch:
            try:
                trip = trip.tolist()
            except:
                pass

            # Find nearest available SAV
            bestDistance = 100000
            bestSav = None
            for sav in self.roamingVehicles + self.parkedVehicles:
                distance = _zoneCentroids[sav.getCurrentZone()].distance(_zoneCentroids[trip[2]])
                if distance < bestDistance:
                    bestDistance = distance
                    bestSav = sav

            if bestSav == None:
                if trip not in self.highPriorityTrips:
                    self.highPriorityTrips.append(trip)
                continue

            # If in same zone already, set travelTimeRemaining now and ignore later
            if bestDistance == 0:
                # randomly sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                bestSav.travelTimeRemaining = math.ceil(np.random.uniform() * _zoneRadiusMap[trip[2]] / 17.6 * 60)
          
            # Set next zone to trip's destination
            bestSav.travelZone = trip[2]
            bestSav.nextZone = trip[3]

            googleMapsApiBuffer.append(bestSav)
            self.travelingVehicles.append(bestSav)

            # Remove from available vehicles
            try:
                self.roamingVehicles.remove(bestSav)
                roamingBuffer.append(bestSav)
                #print(f"Roaming SAV matched: {bestSav}")
            except:
                try:
                    self.parkedVehicles.remove(bestSav)
                    #print(f"Parked SAV matched: {bestSav}")
                except:
                    raise RuntimeError

            if trip in self.highPriorityTrips:
                self.highPriorityTrips.remove(trip)

        # Construct 1 api request (destination matrix) to google maps
        origins = []
        destinations = []

        # get current -> travel times
        for sav in googleMapsApiBuffer:
            origins.append(sav.getCurrentBestLocationForAPI())
            destinations.append(_zoneIdMap[sav.travelZone])
            
        # get travel -> next times
        for sav in googleMapsApiBuffer:
            origins.append(_zoneIdMap[sav.travelZone])
            destinations.append(_zoneIdMap[sav.nextZone])

        # Send and await response
        response = self.gmapsClient.distance_matrix(origins, destinations)
        response = response['rows']

        # First half of response is current -> travel
        for sav, resp in zip(googleMapsApiBuffer, response[:int(len(response)/ 2)]):
            if sav.travelTimeRemaining == 0:
                sav.travelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)

        # Second half is travel -> next
        for sav, resp in zip(googleMapsApiBuffer, response[int(len(response)/ 2):]):
            sav.nextTravelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
