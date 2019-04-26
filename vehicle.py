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
            #print(timeGoal)
            timeSum = 0
            for step in self.route:
                timeSum += step[0]
                if timeSum >= timeGoal:
                    x, y = transformer.transform(step[1][0], step[1][1])
                    #print(f"Transformed coords: {x},{y}")
                    return self.near(Point(x, y))

            raise RuntimeError(f"Route crawl failed: {timeGoal - timeSum} off")

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

        mock = False
        if mock is True:
            self.gmapsClient = MockClient()
        else:
            with open('secret') as fp:
                key = fp.readlines()[0]
                self.gmapsClient = googlemaps.Client(key=key)

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
                sample = np.random.choice(_zoneKeyList)
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
                    #print("Sending directions request")
                    response = self.gmapsClient.directions(_zoneIdMap[vehicle.currentZone],
                                                            _zoneIdMap[vehicle.travelZone])
                    
                    steps = []
                    #print(response)

                    for step in response[0]['legs'][0]['steps']:
                        lat = step['end_location']['lat']
                        lng = step['end_location']['lng']
                        steps.append((math.ceil(step['duration']['value']/60), (lat, lng)))

                    # NOTE: There is a premium api for 'duration_in_traffic'
                    duration = math.ceil(response[0]['legs'][0]['duration']['value'] / 60)

                    vehicle.route = steps
                    #print(vehicle.route)
                    vehicle.travelTimeRemaining = duration
                    vehicle.nextTravelTimeRemaining = 0

                    #print(f"Client dropped off, roaming: {vehicle}")
                    self.travelingVehicles.remove(vehicle)
                    self.roamingVehicles.append(vehicle)

    def matchVehicles(self, trips):

        googleMapsApiBuffer = []
     
        tripsToMatch = self.highPriorityTrips + trips.tolist()
        print(f"Attempting to match {len(tripsToMatch)} trips")

        for trip in tripsToMatch:
            try:
                trip = trip.tolist()
            except:
                pass

            # Find nearest available SAV
            bestDistance = 100000
            bestSav = None
            # NOTE: Interesting results when switching park/roam match priority
            # for sav in self.parkedVehicles + self.roamingVehicles:
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
            sameZone = False
            if bestDistance == 0:
                # sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                time = math.ceil(np.random.uniform() * _zoneRadiusMap[trip[2]] / 17.6 * 60)
                bestSav.travelTimeRemaining = time
                sameZone = True
          
            # Set next zone to trip's destination
            bestSav.travelZone = trip[2]
            bestSav.nextZone = trip[3]

            googleMapsApiBuffer.append((bestSav, sameZone))
            self.travelingVehicles.append(bestSav)

            # Remove from available vehicles
            try:
                self.roamingVehicles.remove(bestSav)
                #print(f"Roaming SAV matched: {bestSav}")
            except:
                try:
                    self.parkedVehicles.remove(bestSav)
                    #print(f"Parked SAV matched: {bestSav}")
                except:
                    raise RuntimeError

            if trip in self.highPriorityTrips:
                self.highPriorityTrips.remove(trip)

        # Construct 2 api request (destination matrix) to google maps
        origins1 = []; origins2 = []
        destinations1 = []; destinations2 = []

        googleMapsMask = np.zeros(len(googleMapsApiBuffer), dtype=int)
        # get current -> travel times
        for i, tup in enumerate(googleMapsApiBuffer):
            sav, flag = tup
            if flag is not True:
                origins1.append(sav.getCurrentBestLocationForAPI())
                destinations1.append(_zoneIdMap[sav.travelZone])
                googleMapsMask[i] = 1

        googleMapsMask = np.nonzero(googleMapsMask)[0]
        googleMapsApiBufferMasked = [googleMapsApiBuffer[i] for i in googleMapsMask]
            
        # get travel -> next times
        for tup in googleMapsApiBuffer:
            sav = tup[0]
            origins2.append(_zoneIdMap[sav.travelZone])
            destinations2.append(_zoneIdMap[sav.nextZone])

        # Send and await response
        response1 = None
        if len(origins1) > 0:
            #print("Sending dist matrix request 1")
            try:
                response1 = self.gmapsClient.distance_matrix(origins1, destinations1)
            except Exception as e:
                print("Sending dist matrix request 1")
                print(e)
                print(len(origins1))
                quit()
            response1 = response1['rows']

        response2 = None
        if len(origins2) > 0:
            #print("Sending dist matrix request 2")
            try:
                response2 = self.gmapsClient.distance_matrix(origins2, destinations2)
            except Exception as e:
                print("Sending dist matrix request 2")
                print(e)
                print(len(origins2))
                quit()
            response2 = response2['rows']

        #print(f"Response 1:\n{response1}\n")
        # Assign current -> travel
        if response1 is not None:
            for tup, resp in zip(googleMapsApiBufferMasked, response1):
                sav = tup[0]
                sav.travelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
                sav.totalTripWaitTime.append((int(sav.travelTimeRemaining), int(sav.travelZone)))

        # Assign travel -> next
        if response2 is not None:
            for tup, resp in zip(googleMapsApiBuffer, response2):
                sav = tup[0]
                sav.nextTravelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
