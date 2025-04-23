First commit i commented out the adjust_lock_in_phase function and added a new one to allow plotting the data and fit curve in the GUI itself. Added relevant code to the GUI section and global variables section to produce this.

original file students used sp25:
power data took 1:15 to collect
Adjust phase Lock-in took 1:02 for pixel 1
    terminal reported 0.214500 @ 360 deg, locked to 359.6 deg with 0.214000
PV measurement for pixel1 took 3:04

PV measurement for pixel2 took 3:07
Adjust phase lock-in took 0:58 for pixel 2
    set to 357.9 with  0.272200

adjust phase lock took 0:58 for pixel 3
    set to 357.7 deg with 0.275800
PV measurement for pixel3 took 3:08

adjust phase lock could not find a proper set for 4-6
    student data confirms pixels stopped working

PLots work, moving on to add text and drop downs for cell# pixel# to automate file naming
added validation for cell# conventions (currently C60_XX or 2501-XX) Can be adjusted depending on later cellID format

Starting to adjust phase timing and degree checks
6 data points completes in ~12s
4 data points completes in ~8-9s

adjusting the function to produce a csv of 10 runs of data_points = 3-13 for consideration for actual use

missed statement here - have a thorough description in the commit documentation - functionally complete and GUI tweaked 

pyside version is up to date with everything from before - also added a pop up for R^2<0.90 for students to make sure lamp is on or potentially dead pixel.

pyside version of JV is up to date with everything from before prompting cell#, pixel #, auto save with filename conventions