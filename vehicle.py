import math
import numpy as np

import parser

import googlemaps

zoneIdMap = parser.readZoneIdMap()

class mockClient:

    def __init__(self):
        self.directionCount = 0
        self.distanceCount = 0
    
    def directions(self, origin, destination):
        self.directionCount += 1
        return (15, [1])

    def distance_matrix(self, origins, destinations):
        self.distanceCount += 1
        return {
            'rows': [
                {
                    'elements': [
                        {
                            'duration':{
                                'value': 900
                            }
                        }
                    ]
                }
            ] * len(origins)
        }


class Vehicle:
    def __init__(self, zoneId):
        self.currentZone = zoneId
        self.travelZone = None
        self.nextZone = None
        self.travelTimeRemaining = 0 # in minutes
        self.nextTravelTimeRemaining = 0
        self.route = []

    def __str__(self):
        return f"Id: {hex(id(self))}, Curr Zone: {self.currentZone}, Travel Zone: {self.travelZone}, Next Zone: {self.nextZone}, Travel Time Remaining: {self.travelTimeRemaining}"
    
    def getCurrentZone(self):
        # if route length is 0, has no route => is parked
        if len(self.route) == 0:
            return self.currentZone
        else:
            # From google maps route, convert long lat to zone id on map w/ geopanda
            return 50

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

        #self.gmapsClient = googlemaps.Client(key='Add Your Key here')
        self.gmapsClient = mockClient()

        # Give all parked vehicles initial positions
        sample = np.random.choice(list(self.zoneDist.keys()),
                                    size=self.fleetSize,
                                    p=list(self.zoneDist.values()))
        for i in range(self.fleetSize):
            self.parkedVehicles.append(Vehicle(sample[i]))

    def updateVehicles(self):

        for vehicle in self.roamingVehicles:
            vehicle.travelTimeRemaining -= 1

            if vehicle.travelTimeRemaining <= 0:
                vehicle.currentZone = vehicle.travelZone
                vehicle.travelZone = None
                vehicle.nextZone = None
                vehicle.route = []

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
                    response = self.gmapsClient.directions(zoneIdMap[vehicle.currentZone], zoneIdMap[vehicle.travelZone])
                    vehicle.travelTimeRemaining = response[0]
                    vehicle.route = response[1]
                    
                    vehicle.nextTravelTimeRemaining = 0

                    #print(f"Client dropped off, roaming: {vehicle}")

                    self.travelingVehicles.remove(vehicle)
                    self.roamingVehicles.append(vehicle)

    def matchVehicles(self, trips):

        googleMapsApiBuffer = []
        roamingBuffer = []
     
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

            # If in same zone already, set travelTimeRemaining now and ignore later
            if bestDistance == 0:
                # randomly sample average centroid radius to get estimated pick up time, 17.6 is avg mph for NYC
                bestSav.travelTimeRemaining = math.ceil(np.random.uniform() * self.zoneRadiusMap[trip[2]] / 17.6 * 60)
          
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
            if sav not in roamingBuffer:
                origins.append(zoneIdMap[sav.currentZone])
            else:
                lon, lat = 69, 69 # TODO: Get actual long lat coords from sav route
                origins.append(f"{lon},{lat}")

            destinations.append(zoneIdMap[sav.travelZone])
            
        # get travel -> next times
        for sav in googleMapsApiBuffer:
            origins.append(zoneIdMap[sav.travelZone])
            destinations.append(zoneIdMap[sav.nextZone])

        # Send and await response
        response = self.gmapsClient.distance_matrix(origins, destinations)
        response = response['rows']

        # First half of response is current -> travel
        for sav, resp in zip(googleMapsApiBuffer, response[:int(len(response)/ 2)]):
            if sav.travelTimeRemaining <= 0:
                sav.travelTimeRemaining = int(resp['elements'][0]['duration']['value'] / 60)

        # Second half is travel -> next
        for sav, resp in zip(googleMapsApiBuffer, response[int(len(response)/ 2):]):
            sav.nextTravelTimeRemaining = int(resp['elements'][0]['duration']['value'] / 60)
