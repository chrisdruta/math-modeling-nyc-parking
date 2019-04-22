#!/usr/bin/env python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import geopandas
from geopandas.plotting import plot_polygon_collection

import parser
from vehicle import VehicleController

def plot(geopandaMap):
    """
    Plots colored Geopandas GeoDataFrame objects

    Args:
        geopandaMap: GeoDataFrame object with an added 'parking_demand' coloumn

    Returns:
        Nothing
    """
    fig, ax = plt.subplots()
    ax.set_aspect('equal')
    plt.hold(True)
    plot_polygon_collection(ax, geopandaMap.geometry, geopandaMap['parking_demand'])
    plt.axis('off')

# Read in nyc zone map
zoneIdMap = parser.readZoneIdMap()
zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')

print("Generating trips...")
trips, zoneDist = parser.generateTripsAndZoneDist("output.csv", 1, 0.02)
print(f"Number of trips: {len(trips)}")

# Initate SAVs
# What is the fleet size we should use?
n = 500
controller = VehicleController(n, zoneDist, zoneMap)
print("Finished setting up model controller")

# Initial distribution of vehicles
colors = {k: 0 for k in range(1, zoneMap.shape[0] + 1)}
for vehicle in controller.parkedVehicles:
    colors[vehicle.currentZone] += 1

zoneMap['parking_demand'] = list(colors.values())

print("Starting simulation day")
for hour in range(24):
    hourTrips = trips[trips[:,0] == hour]

    for minute in range(60):
        print(f"\nTime {hour}:{minute}")
        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        controller.matchVehicles(tripsToStart)
        controller.updateVehicles()
        print(f"High priority trips: {len(controller.highPriorityTrips)}")
        print(f"Roaming vehicles: {len(controller.roamingVehicles)}")

print("\nEND\n")

print(" -- Stats --")
print(f"Availible vehicles: {len(controller.parkedVehicles + controller.roamingVehicles)}")
print(f"Traveling vehicles: {len(controller.travelingVehicles)}")
print(f"Google Maps Directions API Calls: {controller.gmapsClient.directionCount}")
print(f"Google Maps Destination Matrix API Calls: {controller.gmapsClient.distanceCount}")

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
