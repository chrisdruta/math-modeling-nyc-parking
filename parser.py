import pandas as pd
import numpy as np
from shapely.geometry import MultiPoint

def parse(filenameList):
    """
    Parses through given filename list to generate one output csv
    for all useful data from all datasets

    Args:
        filenameList: list of strings containing file names to parse

    Returns:
        Nothing, clears and writes new 'output.csv' in root dir
    """
    # Clear output.csv
    open('output.csv', 'w').close()

    for filename in filenameList:
        data = pd.read_csv(f"./data/{filename}").values

        # Format: [start hour, start minute, pickup zone id, dropoff zone id]
        parsed = [ [int(row[1][11:13]), int(row[1][14:16]), row[7], row[8]] for row in data if row[7] != row[8] and row[7] != 264 and row[8] != 264 and row[7] != 265 and row[8] != 265 ]

        # Appends to output.csv
        pd.DataFrame(parsed).to_csv("./data/output.csv", index=False, header=False, mode='a')

def generateTripsAndZoneDist(filename, numDataSets, percentUsing):
    """
    Samples a parsed csv to generate trips for simulation day and the zone distribution

    Args:
        filename: name of file to sample from (should be output of parse func above)
        numDataSets: number of datasets used to generate file
        percentUsing: percent of taxi rider population that is replace by SAV

    Returns:
        trips: numpy array containing samples
        zoneDistribution: dictionary containing (zoneId, pmfVal) pairs describing city
    """

    data = pd.read_csv(filename).values
    zoneData = pd.read_csv("taxi_zones/zone_lookup.csv").values

    # Making time distribution and zone distributions
    timeDistribution = np.zeros(24)
    zoneDistribution = {k: 0 for k in range(1,zoneData[-1][0] + 1)}
    for d in data:
        timeDistribution[d[0]] += 1
        zoneDistribution[d[2]] += 1

    total = len(data)
    for i in range(24):
        timeDistribution[i] /= total
    for i in range(1,zoneData[-1][0] + 1):
        zoneDistribution[i] /= total

    # n = number of data points divided by (30 * number of datasets) * 0.02 (2% of population uses it)
    n = int(len(data) / (30 * numDataSets) * percentUsing)

    # Sample trips according to time distribution
    sample = np.random.choice(np.arange(0, 24), size=n, p=timeDistribution)

    # Randomly sample existing trips and add them to new list
    trips = []
    for time in range(24):
        indices = np.random.choice(len(data[data[:, 0] == time]), size=len(sample[sample == time]))
        trips.extend(data[data[:, 0] == time][indices])

    return np.array(trips), zoneDistribution

def readZoneIdMap():
    """
    Reads in csv and returns a map: zoneId -> location name

    Args:
        None
    
    Returns:
        zoneMap: dictionary containing (zoneId, location name string) pairs
    """
    zoneData = pd.read_csv("taxi_zones/zone_lookup.csv").values
    zoneMap = {}

    for zone in zoneData:
        zoneMap[zone[0]] = f"{zone[2]}, {zone[1]}"
    
    return zoneMap

def readZoneRadiusMap(zoneMap):
    """
    Reads in given geogreophy data to calculate avg radius of each zone in milesa

    Args:
        zoneMap: Geopandas dataframe that contains zone data

    Returns:
        zoneRadiusMap: Dictionary containing the average radius in miles for each zone
    """
    centroids = zoneMap.centroid
    hulls = zoneMap.convex_hull
    zoneRadiusMap = {}
    for i in range(len(centroids)):
        corners = MultiPoint(hulls[i].exterior.coords)
        center = centroids[i]
        distSum = sum(np.sqrt((center.x - corner.x)**2 + (center.y - corner.y)**2) for corner in corners)

        # Average distance to centroid = (meters) / 1000 (meters) * Km -> Mile Factor
        zoneRadiusMap[i + 1] = distSum/len(corners) / 1000 * 0.621371 

    return zoneRadiusMap
    
# parse(['yellow_tripdata_2018-01.csv',
#         'yellow_tripdata_2018-03.csv',
#         'yellow_tripdata_2018-05.csv',
#         'yellow_tripdata_2018-07.csv',
#         'yellow_tripdata_2018-09.csv',
#         'yellow_tripdata_2018-11.csv'
#         ])