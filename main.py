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

# Initate SAVs
# What is the fleet size we should use?
n = 500
controller = VehicleController(n, zoneDist)
print("Finished setting up model controller")

# Initial distribution of vehicles
initialDist = {k: 0 for k in zoneIdMap.keys()}

for vehicle in controller.parkedVehicles:
    initialDist[vehicle.currentZone] += 1

maxVal = max(initialDist.values())
print(maxVal)
zoneMap['initial_dist'] = [float(i)/maxVal for i in list(initialDist.values())]

# Calculations
parkingDemand = {k: 0 for k in zoneIdMap.keys()}
zoneAvgWait = {k: 0 for k in zoneIdMap.keys()}

print("Starting simulation day")
for hour in range(24):
    hourTrips = trips[trips[:,0] == hour]

    for minute in range(60):
        print(f"\nTime {hour}:{minute}")
        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        controller.matchVehicles(tripsToStart)
        controller.updateVehicles()

        for vehicle in controller.parkedVehicles:
            parkingDemand[vehicle.currentZone] += 1

        print(f"High priority trips: {len(controller.highPriorityTrips)}")
        print(f"Roaming vehicles: {len(controller.roamingVehicles)}")

print("\nEND\n")

zoneCentroids = zoneMap.geometry.centroid

# Calculating parking demand map
zoneMap['parking_demand'] = list(parkingDemand.values())

# Calculating per zone wait time
for vehicle in controller.allVehicles:
    for waitTime, zoneId in vehicle.totalTripWaitTime:
        zoneAvgWait[zoneId] += waitTime * -1 / numTrips
zoneMap['wait_time'] = list(zoneAvgWait.values())

plot(zoneMap, 'wait_time', save=True)
plt.show()

#plot(zoneMap, 'parking_demand', title='Zone Average Parking Demand')
#plt.plot(zoneCentroids[49].x, zoneCentroids[49].y, marker='o', markersize=3, color="red")

printStats = False
if (printStats):
    print(" -- Stats --")
    print(f"Availible vehicles: {len(controller.parkedVehicles + controller.roamingVehicles)}")
    print(f"Traveling vehicles: {len(controller.travelingVehicles)}")
    print(f"Google Maps Directions API Calls: {controller.gmapsClient.directionCount}")
    print(f"Google Maps Destination Matrix API Calls: {controller.gmapsClient.distanceCount}")
    print(f" => Total API Calls: {controller.gmapsClient.directionCount + controller.gmapsClient.distanceCount}")

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
