#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

dist = np.load('dist-graph.npy')

plt.figure()
plt.title('Bhattacharyya Distance: switch @ 1.5')
plt.plot(np.arange(len(dist)), dist)
plt.plot(np.arange(len(dist)), [1.5] * len(dist))

plt.show()
