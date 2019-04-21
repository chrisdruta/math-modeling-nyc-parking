import math
import numpy as np

import parser

import googlemaps

zoneIdNameMap = parser.readZoneIdMap()

class Vehicle:
    def __init__(self, zoneId):
        self.currentZone = zoneId
        self.travelZone = None
        self.nextZone = None
        self.travelTimeRemaining = 0 # in minutes
        self.route = []
    
    def getCurrentZone(self):
        # if route length is 0, has no route => is parked
        if len(self.route) == 0:
            return self.currentZone
        else:
            return -1 # From google maps route, convert long lat to zone id on map w/ geopanda

class VehicleController:
    def __init__(self, n, zoneDist, zoneMap):
        self.fleetSize = n
        self.zoneDist = zoneDist
        self.zoneMap = zoneMap
        self.zoneCentroids = {(i + 1): p for i, p in enumerate(zoneMap['geometry'].centroid)}
        self.zoneRadiusMap = parser.readZoneRadiusMap(self.zoneMap)

        self.roamingVehicles = []
        self.parkedVehicles = []
        self.travelingVehicles = []

        self.highPriorityTrips = []

        self.gmapsClient = googlemaps.Client(key='Add Your Key here')

        # Give all parked vehicles initial positions
        sample = np.random.choice(list(self.zoneDist.keys()),
                                    size=self.fleetSize,
                                    p=list(self.zoneDist.values()))
        for i in range(self.fleetSize):
            self.parkedVehicles.append(Vehicle(sample[i]))

    def updateVehicles(self):

        googleMapsApiBuffer = []

        for vehicle in self.drivingVehicles:
            # Decrement traveling time
            vehicle.travelTimeRemaining -= 1

            # Trip is complete
            if vehicle.travelTimeRemaining == 0:

                # Case 1: Just picked up client, going to drop off
                if vehicle.nextZone >= 1:
                    vehicle.currentZone = vehicle.travelZone
                    vehicle.travelZone = vehicle.nextZone
                    vehicle.nextZone = 0
                    
                    googleMapsApiBuffer.append(vehicle)
                
                # Case 2: Dropped off client, going to roam
                if vehicle.nextZone == 0:
                    randomZone = 50
                    vehicle.currentZone = vehicle.travelZone
                    vehicle.travelZone = randomZone
                    vehicle.nextZone = None

                    self.roamingVehicles.append(vehicle)

                    googleMapsApiBuffer.append(vehicle)
                    

                # Case 3: Finished roaming, going to park
                else:
                    self.drivingVehicles.remove(vehicle)
                    self.roamingVehicles.remove(vehicle)
                    self.parkedVehicles.append(vehicle)

        for vehcile, zone in googleMapsApiBuffer:
            
            pass

        self.gmapsClient.distance_matrix()

    def matchVehicles(self, trips, t):

        googleMapsApiBuffer = []
     
        #tripsToLoop = np.concatenate(np.array(self.highPriorityTrips), trips, axis=0)
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
                distance = self.zoneCentroids[sav.getCurrentZone()].distance(self.zoneCentroids[trip[2]])
                if distance < bestDistance:
                    bestDistance = distance
                    bestSav = sav

            if bestSav == None:
                if trip not in self.highPriorityTrips:
                    self.highPriorityTrips.append(trip)
                continue

            # Updated matched sav
            if bestDistance == 0:
                # randomly sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                bestSav.travelTimeRemaining = math.ceil(np.random.uniform() * self.zoneRadiusMap[trip[2]] / 17.6 * 60)
            else:
                # use google maps
                googleMapsApiBuffer.append(bestSav)

            # Set next zone to trip's destination
            bestSav.travelZone = trip[2]
            bestSav.nextZone = trip[3]

            self.drivingVehicles.append(bestSav)
                
            # Remove from available vehicles
            print("Trip matched!")
            try:
                self.roamingVehicles.remove(bestSav)
            except:
                self.parkedVehicles.remove(bestSav)

            if trip in self.highPriorityTrips:
                self.highPriorityTrips.remove(trip)

        # Construct 1 api request (destination matrix) to google maps
        origins = []
        destinations = []
        for sav in googleMapsApiBuffer:
            if sav in self.parkedVehicles:
                origins.append(zoneIdNameMap[sav.currentZone])
            elif sav in self.roamingVehicles:
                lon, lat = 69, 69 # TODO
                origins.append(f"{lon},{lat}")
            else:
                raise RuntimeError("Shouldn't happen")

            destinations.append(zoneIdNameMap[sav.travelZone])

        # Send and await response
        response = self.gmapsClient.distance_matrix(origins, destinations)
        response = response['rows']

        for sav, resp in zip(googleMapsApiBuffer, resp):
            sav.travelTimeRemaining = int(resp['elements']['duration']['value'] / 60)
