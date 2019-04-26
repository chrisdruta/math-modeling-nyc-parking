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
            
            #raise RuntimeError(f"Route crawl failed: {timeGoal - timeSum} off")
            x, y = transformer.transform(self.route[-1][1][0], self.route[-1][1][1])
            return self.near(Point(x, y))

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

            #raise RuntimeError("Route crawl failed for best location")
            return f"{self.route[-1][1][0]},{self.route[-1][1][1]}"

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

        mock = True
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

    @staticmethod
    def groupByTen(origins, destinations):
        originsBuffered = []
        destinationsBuffered = []
        count = 1
        for o, d in zip(origins, destinations):
            if count == 1:
                originsBuffered.append([])
                destinationsBuffered.append([])
            if count <= 10:
                originsBuffered[-1].append(o)
                destinationsBuffered[-1].append(d)
            else:
                count = 0
            count += 1
        return originsBuffered, destinationsBuffered

    def updateVehicles(self, bhatDist):

        for vehicle in self.roamingVehicles:
            vehicle.travelTimeRemaining -= 1

            if vehicle.travelTimeRemaining <= 0:
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

        mapsApiBufferFirst = []
        mapsApiBufferSecond = []
     
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

            # Set next zone to trip's destination
            bestSav.travelZone = trip[2]
            bestSav.nextZone = trip[3]

            # If in same zone already, set travelTimeRemaining now and ignore later
            if bestDistance == 0:
                # sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                time = math.ceil(np.random.uniform() * _zoneRadiusMap[trip[2]] / 17.6 * 60)
                bestSav.travelTimeRemaining = time
            
            else:
                mapsApiBufferFirst.append(bestSav)

            mapsApiBufferSecond.append(bestSav)
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

        for av in mapsApiBufferFirst:
            origins1.append(av.getCurrentBestLocationForAPI())
            destinations1.append(_zoneIdMap[av.travelZone])
            
        for av in mapsApiBufferSecond:
            origins2.append(_zoneIdMap[av.travelZone])
            destinations2.append(_zoneIdMap[av.nextZone])

        # Limit to 10 trips to per call
        bufferOrigins1, bufferDestinations1 = self.groupByTen(origins1, destinations1)
        bufferOrigins2, bufferDestinations2 = self.groupByTen(origins2, destinations2)

        reconstruct1 = None
        if len(origins1) > 0:
            #print("Sending dist matrix request 1")
            reconstruct1 = []
            for oBuf, dBuf in zip(bufferOrigins1, bufferDestinations1):
                try:
                    response = self.gmapsClient.distance_matrix(oBuf, dBuf)
                    reconstruct1.extend(response['rows'])
                except Exception as e:
                    print("Sending dist matrix request 1")
                    print(e)
                    print(len(oBuf))
                    quit()

        reconstruct2 = None
        if len(origins2) > 0:
            reconstruct2 = []
            for oBuf, dBuf in zip(bufferOrigins2, bufferDestinations2):
                try:
                    response = self.gmapsClient.distance_matrix(oBuf, dBuf)
                    reconstruct2.extend(response['rows'])
                except Exception as e:
                    print("Sending dist matrix request 2")
                    print(e)
                    print(len(oBuf))
                    quit()

        #print(f"Response 1:\n{response1}\n")
        # Assign current -> travel
        if reconstruct1 is not None:
            for av, resp in zip(mapsApiBufferFirst, reconstruct1):
                av.travelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
                # For average wait time calculation
                av.totalTripWaitTime.append((int(av.travelTimeRemaining), av.travelZone))

        # Assign travel -> next
        if reconstruct2 is not None:
            for av, resp in zip(mapsApiBufferSecond, reconstruct2):
                av.nextTravelTimeRemaining = math.ceil(resp['elements'][0]['duration']['value'] / 60)
