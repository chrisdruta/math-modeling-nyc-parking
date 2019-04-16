#!/usr/bin/env python

import pandas as pd
import numpy as np

import parser

#parser.parse(["yellow_tripdata_2018-01.csv"])

trips = parser.generateTrips("output.csv", 1, 0.02)

for hour in range(24):
    hourTrips = trips[trips[:,0] == hour]
    for minute in range(60):
        tripsToStart = hourTrips[hourTrips[:,1] == minute]
        print(tripsToStart)
        


