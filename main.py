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
    plot_polygon_collection(ax, geopandaMap['geometry'], geopandaMap['parking_demand'], vmin=0, vmax=1)
    plt.axis('off')

zoneIdMap = parser.readZoneIdMap()

# Initate trips
#trips = parser.generateTrips("output.csv", 1, 0.02)
#print(f"Number of trips: {len(trips)}")

# Iniate SAVs
# What is the fleet size we should use?
n = 500
# Where will they initially be placed?
#   Maybe initialize them in zones from distribution created from all data
controller = VehicleController(n)

zoneMap = geopandas.read_file('taxi_zones/taxi_zones.shp')

colors = np.arange(0, 1, 1/len(zoneMap))
zoneMap['parking_demand'] = colors

plot(zoneMap)

plt.show()
quit()
for hour in range(24):
    hourTrips = trips[trips[:,0] == hour]

    for minute in range(60):
        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        #print(tripsToStart) comments
        
        # Match SAVs to trips and use google api destination matrix for travel times
        #   Remove matched SAVs from availibile SAVs

        # Check if any trips were completed and add SAVs back to available SAVs with new location

        # Keep track of roaming SAVs => Note: Available SAVs = Parked and roaming SAVs

        pass
        