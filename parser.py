#!/usr/bin/env python

import pandas as pd
import numpy as np

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
        parsed = [ [row[1][11:16], row[7], row[8]] for row in data if row[7] != row[8]]

        # Appends to output.csv
        pd.DataFrame(parsed).to_csv("output.csv", index=False, header=False, mode='a')

parse(["yellow_tripdata_2018-01.csv"])
