
import parser

zoneMap = parser.readZoneMap()

class Vehicle():

    def __init__(self):
        self.currentZone = 0
        self.destinationZone = 0
        self.route = []

class VehicleController():

    def __init__(self, n):
        self.fleetSize = n

        self.allVehicles = []
        self.availableVehicles = []

        for i in range(self.fleetSize):
            pass
    
    @property
    def availableVehicles(self):

        pass

    def updateVehicles(self):
        pass

    def matchVehicles(self, trips):
        pass
