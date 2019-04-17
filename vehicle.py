
import numpy as np

import parser

zoneMap = parser.readZoneIdMap()

class Vehicle():

    def __init__(self, zoneId):
        self.currentZone = zoneId
        self.destinationZone = 0
        self.route = []

class VehicleController():

    def __init__(self, n, zoneDist):
        self.fleetSize = n
        self.zoneDist = zoneDist

        self.availableVehicles = []
        self.travelingVehicles = []

        sample = np.random.choice(list(self.zoneDist.keys()), size=self.fleetSize, p=list(self.zoneDist.values()))
        for i in range(self.fleetSize):
            self.availableVehicles.append(Vehicle(sample[i]))

    def __str__(self):
        return '\n'.join(f"{i}: {vehicle.currentZone}" for i, vehicle in enumerate(self.availableVehicles))


    @property
    def allVehicles(self):
        return self.availableVehicles + self.travelingVehicles

    def updateVehicles(self):
        pass

    def matchVehicles(self, trips):
        pass
