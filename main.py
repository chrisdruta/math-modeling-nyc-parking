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
    plot_polygon_collection(ax, geopandaMap.geometry, geopandaMap['parking_demand'])
    plt.axis('off')

zoneIdMap = parser.readZoneIdMap()

print("Generating trips...")
trips, zoneDist = parser.generateTripsAndZoneDist("output.csv", 1, 0.02)
print(f"Number of trips: {len(trips)}")

# Read in nyc zone map
zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')

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

        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        controller.matchVehicles(tripsToStart, (hour, minute))

        # Check if any trips were completed and add SAVs back to available SAVs with new location

print(len(controller.availableVehicles))
