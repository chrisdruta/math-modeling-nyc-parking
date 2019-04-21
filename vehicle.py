import math
import numpy as np

import parser

zoneMap = parser.readZoneIdMap()

class Vehicle:
    def __init__(self, zoneId):
        self.currentZone = zoneId
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
        self.drivingVehicles = []

        self.highPriorityTrips = []

        # Give all parked vehicles initial positions
        sample = np.random.choice(list(self.zoneDist.keys()),
                                    size=self.fleetSize,
                                    p=list(self.zoneDist.values()))
        for i in range(self.fleetSize):
            self.parkedVehicles.append(Vehicle(sample[i]))

    def __str__(self):
        return '\n'.join(f"{i}: {vehicle.currentZone}" for i, vehicle in enumerate(self.allVehicles))

    @property
    def availableVehicles(self):
        return self.roamingVehicles + self.parkedVehicles

    def updateVehicles(self):

        googleMapsApiBuffer = []

        for vehicle in self.drivingVehicles:
            # Decrement trip travel time remaining
            vehicle.travelTimeRemaining -= 1

            # Trip is complete
            if vehicle.travelTimeRemaining == 0:
                # Case 1: Just picked up client, going to drop off
                if vehicle.nextZone >= 1:
                    nextZone = vehicle.nextZone
                    vehicle.nextZone = 0
                    googleMapsApiBuffer.append((vehicle, nextZone))
                
                # Case 2: Dropped off client, going to roam
                if vehicle.nextZone == 0:
                    randomZone = 50
                    vehicle.nextZone = None
                    googleMapsApiBuffer.append((vehicle, randomZone))
                    self.roamingVehicles.append(vehicle)

                # Case 3: Finished roaming, going to park
                else:
                    self.drivingVehicles.remove(vehicle)
                    self.roamingVehicles.remove(vehicle)
                    self.parkedVehicles.append(vehicle)

        for vehcile, zone in googleMapsApiBuffer:
            pass

    def matchVehicles(self, trips, t):

        googleMapsApiBuffer = []
     
        #tripsToLoop = np.concatenate(np.array(self.highPriorityTrips), trips, axis=0)
        tripsToLoop = self.highPriorityTrips + trips.tolist()

        for trip in tripsToLoop:
            try:
                trip = trip.tolist()
            except:
                pass

            # Find nearest available SAV
            bestDistance = 100000
            bestSav = None
            for sav in self.availableVehicles:
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
                self.drivingVehicles.append(bestSav)
            else:
                # use google maps
                googleMapsApiBuffer.append(bestSav)

            # Set next zone to trip's destination
            bestSav.nextZone = trip[3]
                
            # Remove from available vehicles
            print("Trip matched!")
            try:
                self.roamingVehicles.remove(bestSav)
            except:
                self.parkedVehicles.remove(bestSav)

            if trip in self.highPriorityTrips:
                self.highPriorityTrips.remove(trip)

        # Construct 1 api request (destination matrix) to google maps
        googleMapsDriving = []
        for sav in googleMapsApiBuffer:
            googleMapsApiBuffer.append(sav)

        # Send and await response

        self.drivingVehicles.extend(googleMapsApiBuffer)
