# h2simulator
A full cycle Hydrogen Storage and Return system simulator for coupling and optimizing PV, Battery storage, Electrolyzer, H2 storage, and Fuel cell.


# Description
This is a python tkinter program, which simulates the operation of an electricity storage and return system based on hydrogen. Freely available solar irradiance data is used to determine the production of green electricity at any location and in small time intervals (5 to 15 minutes). Alternatively, actual data from existing PV installations can be used for the simulation. From this input power, current consumption is subtracted, where the consumption at any moment is generated by a Monte-Carlo simulation based upon actual consumption data (i.e. yearly total energy used and minimum/maximum power draw). If excess electricity from the PV is available, it is used to charge a battery bank and run electrolyzer(s). The produced H2 is stored in a tank. During heating periods, H2 gas is drawn from the tanks and mixed with natural gas for heaters up to a maximum permitted mixing ratio.
When no solar power is available, H2 is drawn from the tank and fed to a fuel cell, which produces electricity according to the current consumption. Surpluses and shortages in supply and demand are exchanged with the grid at current price rates.
All of the components involved, i.e. PV system, battery, electrolyzer(s), H2 storage, and fuel cell can individually be included or excluded in the simulation and all their parameters adapted at will and conveniently in a graphical user interface (GUI). As a result, the simulation produces live graphics which show the relevant data at each time interval or in daily samples for a maximum period of one year. A summary is also generated, which determines the productivity and generated savings of the system and the investment costs are estimated based on recently obtained quotations (See Parameters). From this data, a return-on-investment is calculated, which can be optimized by execution of an included algorithm that optimally matches the components to each other and maximizes yearly savings.

# Installation
Below is a list of python modules necessary to run the program:<br>
numpy <br>
datetime<br>
calendar<br>
random<br>
tkinter<br>
PIL<br>
pandas<br>
threading<br>
matplotlib<br>

# Usage
*Obtain insolation data from the web: 
  NREL NSRDB data viewer. Link: https://maps.nrel.gov/nsrdb-viewer (26.10.2021). Choose METEOSAT PSM v3, or similar for Europe. Click “Download Data” and select ‘point data download’. Then fill in credentials and pick desired data columns DNI & GHI, time span and interval from the respective model’s tab. Download data and open with spreadsheet manipulator. Make a column where DNI and GHI are added together and fill in the column numbers into the simulation configuration (A=col 1, B = col 2, etc.).Save file without header (numbers starting from first row) as csv. Fill in the filename in configuration/solar input.<br><br>

*Configure the components to be included in the simulated installtion under Configuration/General<br><br>

*Configure the consumption profile of the site under Configuration/Sinks<br><br>

*(OPTIONAL) Configure Optimization parameters under Configuration/Optimize<br><br>

*Press "RUN" to run the simulation. Tick the checkboxes to activate graphs and click the buttons to look at other times, days or the whole year.


# Additional Comments and hints
* "PV-ALONE SAVINGS": This setting is found under Configuration/PV and is used to separate the PV generated savings from
the hydrogen production cycle, for example when a PV installation already exists and only the H2 production, storage and return 
need additional investments. In this case, set "PV-alone savings" to zero and uncheck all modules but PV under Configuration/General.
Now run the simulation and note the yearly savings under the "Summary" tab (Costs). Fill in this value under "PV-alone savings", which
will subtract this value from the generated savings when more modules are included.

* When optimizing the photovoltaics (Configuration/Optimize/optimize pv: y), it is best to set the revenue per kWh sold to zero under Configuration/Sinks, such that the required area will be optimized to the other components.
