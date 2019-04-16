import pandas as pd
import numpy as np
from collections import deque

def readZoneMap():
    zoneData = pd.read_csv("zone_lookup.csv").values
    zoneMap = {}

    for zone in zoneData:
        zoneMap[zone[0]] = f"{zone[2]}, {zone[1]}"
    
    return zoneMap

def parse(filenameList):

    # Clear output.csv
    open('output.csv', 'w').close()

    for filename in filenameList:
        data = pd.read_csv(filename).values

        #parsed = [ [ row[1][11:], row[2][11:], row[7], row[8] ] for row in data ]
        parsed = [ [int(row[1][11:13]), int(row[1][14:16]), row[7], row[8]] for row in data if row[7] != row[8]]

        # Appends to output.csv
        pd.DataFrame(parsed).to_csv("output.csv", index=False, header=False, mode='a')

def generateTrips(filename, numDataSets, percentUsing):
    """
    Samples n rows from filename and sort sample by time

    Args:
        filename: name of file to sample and sort data from
        numDataSets: number of datasets used to generate file
        percentUsing: percent of taxi rider population that is replace by SAV

    Returns:
        trips: deque object containing sorted sample
    """

    data = pd.read_csv(filename).values

    # Making time distribution
    timeDistribution = np.zeros(24)
    for d in data:
        timeDistribution[d[0]] += 1

    total = len(data)
    for i in range(24):
        timeDistribution[i] /= total

    # n = number of data points divided by (30 * number of datasets) * 0.02 (2% of population uses it)
    n = int(len(data) / (30 * numDataSets) * percentUsing)

    # Sample trips according to time distribution
    sample = np.random.choice(np.arange(0, 24), size=n, p=timeDistribution)

    # Randomly sample existing trips and sort them
    trips = []
    for time in range(24):
        indices = np.random.choice(len(data[data[:, 0] == time]), size=len(sample[sample == time]))
        subTrips = data[data[:, 0] == time][indices]
        trips.extend((subTrips[np.argsort(subTrips[:, 1])]).tolist())

    return deque(trips)

