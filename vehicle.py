import math
import numpy as np

import parser

zoneMap = parser.readZoneIdMap()

class Vehicle:
    def __init__(self, zoneId):
        self.currentZone = zoneId
        self.nextZone = 0
        self.route = []
        self.tripStartHour = 0
        self.tripStartMinute = 0
        self.tripLength = 0
    
    def getCurrentZone(self, timeInTrip):
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
        pass

    def matchVehicles(self, trips, t):

        googleMapsBuffer = []
     
        if len(self.highPriorityTrips) == 0:
            tripsToLoop = trips
        else:
            try:
                #tripsToLoop = np.concatenate(np.array(self.highPriorityTrips), trips, axis=0)
                tripsToLoop = self.highPriorityTrips + trips.tolist()
            except Exception as err:
                print(err)
                quit()

        for trip in tripsToLoop:
            # Find nearest available SAV
            bestDistance = 100000
            bestSav = None

            for sav in self.availableVehicles:
                timeInTrip = (t[0] - sav.tripStartHour, t[1] - sav.tripStartMinute)
                distance = self.zoneCentroids[sav.getCurrentZone(timeInTrip)].distance(self.zoneCentroids[trip[2]])
                if distance < bestDistance:
                    bestDistance = distance
                    bestSav = sav

            if bestSav == None:
                # TODO: THIS IS BROKEN!
                print(type(trip))
                print(type(self.highPriorityTrips))
                if [trip] in self.highPriorityTrips:
                    self.highPriorityTrips.append([trip])
                continue

            # Updated matched sav
            bestSav.nextZone = trip[3]
            bestSav.tripStartHour = t[0]
            bestSav.tripStartMinute = t[1]

            if bestDistance == 0:
                # randomly sample average centroid radius to get estimated pick up time
                bestSav.tripLength = math.ceil(np.random.uniform() * self.zoneRadiusMap[trip[2]] / 17.6 * 60)
                self.drivingVehicles.append(bestSav)
            else:
                # use google maps
                googleMapsBuffer.append(bestSav)
                
            # Remove from available vehicles
            print("Trip matched!")
            try:
                self.roamingVehicles.remove(bestSav)
            except:
                self.parkedVehicles.remove(bestSav)

            if trip in self.highPriorityTrips:
                self.highPriorityTrips.remove(trip)

        # Construct 1 api request (destination matrix) to google maps
        for sav in googleMapsBuffer:
            pass

        # Send and await response

        self.drivingVehicles.extend(googleMapsBuffer)
