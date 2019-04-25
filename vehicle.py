import math
import numpy as np

import googlemaps
import geopandas
import pyproj
from shapely.geometry import Point
from shapely.ops import nearest_points

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import parser
from mock_client import MockClient

# Setting up coordinate transformer
_zoneIdMap = parser.readZoneIdMap()
_zoneKeyList = list(_zoneIdMap.keys())
_zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')
_zoneRadiusMap = parser.readZoneRadiusMap(_zoneMap)
_zoneCentroids = _zoneMap.geometry.centroid
_zoneCentroidsUnion = _zoneCentroids.unary_union
_zoneCentroidsMap = {(i + 1): p for i, p in enumerate(_zoneCentroids)}
_zoneCentroidsInverseMap = {(v.x, v.y):k for k, v in _zoneCentroidsMap.items()}

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

        # Simulation calculation parameter
        self.totalTripWaitTime = []

    def __str__(self):
        return (f"Id: {hex(id(self))}, Curr Zone: {self.currentZone}, Travel Zone: {self.travelZone} " +
                f"Next Zone: {self.nextZone}, Travel Time Remaining: {self.travelTimeRemaining}")
    
    def near(self, point):
        # find the nearest point and return the corresponding zone value
        nearest = nearest_points(point, _zoneCentroidsUnion)[1]
        return _zoneCentroidsInverseMap[(nearest.x, nearest.y)]

    def getCurrentZone(self):
        if self.route is None:
            return self.currentZone
        else:
            # From google maps route, convert long lat to zone id on map w/ geopanda
            timeGoal = sum(step[0] for step in self.route) - self.travelTimeRemaining
            timeSum = 0
            for step in self.route:
                timeSum += step[0]
                if timeSum >= timeGoal:
                    x, y = transformer.transform(step[1][0], step[1][1])
                    #print(f"Transformed coords: {x},{y}")
                    return self.near(Point(x, y))

            raise RuntimeError("Route crawl failed")

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
    def __init__(self, n, zoneDist, distanceTolerance):
        self.fleetSize = n
        self.zoneDist = zoneDist
        self.zoneDistValsList = np.array(list(zoneDist.values()))
        
        self.distanceTolerance = distanceTolerance

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

    @property
    def allVehicles(self):
        return self.roamingVehicles + self.parkedVehicles + self.travelingVehicles

    def getRoamZone(self, bhatDistance, currZone):
        
        if bhatDistance >= self.distanceTolerance:
            # sample initital dist to force distribution towards there
            sample = np.random.choice(_zoneKeyList, p=self.zoneDistValsList)
            while sample == currZone:
                sample = np.random.choice(_zoneKeyList, p=self.zoneDistValsList)
            return sample
        else:
            # move randomly
            sample = np.random.choice(_zoneKeyList)
            while sample == currZone:
                sample = np.random.choice(_zoneKeyList, p=self.zoneDistValsList)
            return sample

    def updateVehicles(self, bhatDist):

        for vehicle in self.roamingVehicles:
            vehicle.travelTimeRemaining -= 1

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
                    randomZone = self.getRoamZone(bhatDist, vehicle.travelZone)
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
            # NOTE: Interesting results when switching park/roam match priority
            #for sav in self.parkedVehicles + self.roamingVehicles:
            for sav in self.roamingVehicles + self.parkedVehicles:
                distance = _zoneCentroidsMap[sav.getCurrentZone()].distance(_zoneCentroidsMap[trip[2]])
                if distance < bestDistance:
                    bestDistance = distance
                    bestSav = sav
                    if distance == 0: break

            if bestSav == None:
                if trip not in self.highPriorityTrips:
                    print(f"high priority pickup:{trip[2]}, trip:{trip}")
                    self.highPriorityTrips.append(trip)
                continue

            # If in same zone already, set travelTimeRemaining now and ignore later
            if bestDistance == 0:
                # sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                time = math.ceil(np.random.uniform() * _zoneRadiusMap[trip[2]] / 17.6 * 60)
                bestSav.travelTimeRemaining = time
          
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
                sav.totalTripWaitTime.append((int(sav.travelTimeRemaining), int(sav.travelZone)))

        # Second half is travel -> next
        for sav, resp in zip(googleMapsApiBuffer, response[int(len(response)/ 2):]):
            sav.nextTravelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
