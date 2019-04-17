import pandas as pd
import numpy as np

def readZoneIdMap():
    zoneData = pd.read_csv("taxi_zones/zone_lookup.csv").values
    zoneMap = {}

    for zone in zoneData:
        zoneMap[zone[0]] = f"{zone[2]}, {zone[1]}"
    
    return zoneMap

def parse(filenameList):

    # Clear output.csv
    open('output.csv', 'w').close()

    for filename in filenameList:
        data = pd.read_csv(filename).values

        # Format: [start hour, start minute, pickup zone id, dropoff zone id]
        parsed = [ [int(row[1][11:13]), int(row[1][14:16]), row[7], row[8]] for row in data if row[7] != row[8]]

        # Appends to output.csv
        pd.DataFrame(parsed).to_csv("output.csv", index=False, header=False, mode='a')

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
