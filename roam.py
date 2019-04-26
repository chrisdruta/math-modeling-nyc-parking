#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

dist = np.load('dist-graph.npy')

plt.figure()
plt.title(r'$\lambda_{crit} = 2.0$')
plt.xlabel('Time (minutes)')
plt.ylabel('Bhattacharyya Distance')
plt.plot(np.arange(len(dist)), dist)
plt.plot(np.arange(len(dist)), [2] * len(dist))

#plt.savefig("./bhat_dist.png", bbox_inches='tight', dpi=800)

plt.show()
