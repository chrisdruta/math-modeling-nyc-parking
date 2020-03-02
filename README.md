# math-modeling-nyc-parking

Simulation of a fleet of autonomous vehicles to visualize traffic / parking demand for NYC that utilizes historical NYC taxi zoning data (courtesy of NYC government Taxi & Limousine Commission) with realistic travel estimations via Google Maps API. [Project Poster](https://github.com/chrisdruta/math-modeling-nyc-parking/blob/master/images/poster.pdf "Poster")

<p align="center">
    <img src="https://raw.githubusercontent.com/chrisdruta/math-modeling-nyc-parking/master/images/1.png" width="60%">
</p>

> Example parking demand visualization

## Installing Dependencies

 Run `pip3 install -r requirements.txt`

 If that doesn't work, run
 
 `brew install https://raw.githubusercontent.com/Homebrew/homebrew-core/122f2a2a2c44462823360fc5a1becec968b9abf7/Formula/proj.rb`
 
 then
 
 `pip3 install Cartopy==0.16.0 geoplot`

## Notes

### Model Parameters

* Fleet Size
* Percent Utilization
* Lambda crit (Bhattacharyya distance correction threshold)

### Todo

* Parking demand (maps) - Done
* Avg waiting time by region - Done
* Avg waiting time (axis = traffic %, fleet size)
* Environmental Analysis?
