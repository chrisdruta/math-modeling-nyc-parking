#!/usr/bin/env python

import pandas as pd
import numpy as np

import parser

#parser.parse(["yellow_tripdata_2018-01.csv"])

trips = parser.generateTrips("output.csv", 1, 0.02)

print(trips)
