#!/usr/bin/env python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import geopandas
from geopandas.plotting import plot_polygon_collection

import parser
from vehicle import VehicleController

def plot(geopandaMap, plotAxis, title=None, save=False):
    """
    Plots colored Geopandas GeoDataFrame objects

    Args:
        geopandaMap: GeoDataFrame object with an added 'parking_demand' coloumn

    Returns:
        Nothing
    """
    fig, ax = plt.subplots()
    ax.set_aspect('equal')
    if title:
        ax.set_title(title)
    
    idk = plot_polygon_collection(ax, geopandaMap.geometry, geopandaMap[plotAxis], edgecolor='black')
    plt.colorbar(ax=ax,mappable=idk)
    plt.axis('off')

    if save:
        plt.savefig("./{}.png".format(plotAxis), bbox_inches='tight', dpi=1000)

# Read in nyc zone map
zoneIdMap = parser.readZoneIdMap()
zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')

print("Generating trips...")
trips, zoneDist = parser.generateTripsAndZoneDist("output.csv", 1, 0.02)
numTrips = len(trips)
print(f"Number of trips: {numTrips}")

# Initate controller
idealZoneDist = np.array(list(zoneDist.values()))
n = 250
crit = 1.5
controller = VehicleController(n, zoneDist, crit)
print("Finished setting up model controller")

# Initial distribution of vehicles
initialDist = {k: 0 for k in zoneIdMap.keys()}
for vehicle in controller.parkedVehicles:
    initialDist[vehicle.currentZone] += 1
maxVal = np.max(list(initialDist.values()))
zoneMap['initial_dist'] = [float(i)/maxVal for i in list(initialDist.values())]

# Calculations
parkingDemand = {k: 0 for k in zoneIdMap.keys()}
zoneAvgWait = {k: 0 for k in zoneIdMap.keys()}

distGraph = []

print("Starting simulation day")
for hour in range(24):
    hourTrips = trips[trips[:,0] == hour]
    for minute in range(60):

        print(f"\nTime {hour}:{minute}")

        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        controller.matchVehicles(tripsToStart)

        # Update parking demand
        for vehicle in controller.parkedVehicles:
            parkingDemand[vehicle.currentZone] += 1

        # Calculate current vehicle distribution and variance
        availibleVehicles = controller.roamingVehicles + controller.parkedVehicles
        vehicleCountMap = {k: 0 for k in zoneIdMap.keys()}
        for vehicle in availibleVehicles:
            vehicleCountMap[vehicle.getCurrentZone()] += 1
        currDist = np.array(list(vehicleCountMap.values())) / len(availibleVehicles)

        bhatDistance = -1 * np.log(np.sum([np.sqrt(p * q) for p, q in zip(idealZoneDist, currDist)]))
        distGraph.append(bhatDistance)
        print(f"Bhattacharyya distance: {bhatDistance}")

        # Update all vehicles
        controller.updateVehicles(bhatDistance)

        print(f"High priority trips: {len(controller.highPriorityTrips)}")
        print(f"Roaming vehicles: {len(controller.roamingVehicles)}")

print("\nEND\n")

np.save('dist-graph', np.array(distGraph))

zoneCentroids = zoneMap.geometry.centroid

# Calculating parking demand map
parkingDemandValues = np.array(list(parkingDemand.values()))
zoneMap['parking_demand'] = parkingDemandValues / np.max(parkingDemandValues)
print(f"Zone with highest parking demand: {np.argmax(parkingDemandValues) + 1}")

# Calculating per zone wait time
for vehicle in controller.allVehicles:
    for waitTime, zoneId in vehicle.totalTripWaitTime:
        zoneAvgWait[zoneId] += waitTime * -1 / numTrips
zoneMap['wait_time'] = list(zoneAvgWait.values())

plot(zoneMap, 'wait_time', title='Wait Time', save=True)
plot(zoneMap, 'parking_demand', title='Parking Demand', save=True)

plt.show()

printStats = True
if (printStats):
    print(" -- Stats --")
    print(f"Availible vehicles: {len(controller.parkedVehicles + controller.roamingVehicles)}")
    print(f"Traveling vehicles: {len(controller.travelingVehicles)}")
    #print(f"Google Maps Directions API Calls: {controller.gmapsClient.directionCount}")
    #print(f"Google Maps Destination Matrix API Calls: {controller.gmapsClient.distanceCount}")
    #print(f" => Total API Calls: {controller.gmapsClient.directionCount + controller.gmapsClient.distanceCount}")

printDebug = False
if (printDebug):
    print("\nDuplications Test")
    test1 = len(set(controller.travelingVehicles))
    test2 = len(controller.travelingVehicles)
    print(test1)
    print(test2)

    print("\nTraveling in Roaming Test")
    for sav in controller.travelingVehicles:
        if sav in controller.roamingVehicles:
            print("BAD")


    print("\nFirst 10 traveling vehicles:")
    for sav in controller.travelingVehicles[:10]:
            print(sav)
