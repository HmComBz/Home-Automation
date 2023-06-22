HOME AUTOMATION

This application was created in order to optimize our electrical consumption. I bought a bunch of Shelly electrical meters and connected them to the Wifi for all major consumers in the house. 
Also connected our heat pump and FTX ventilation, network infrastructure etc. 

Using Shellys built in REST API I could log the consumption 24/7 for all of our electrical consumers. Our electrical distributor, Tibber (In Sweden) has a Python API for extracting the total consumption and the electrical price for each hour. 
So by combining this data I could calculate and visualize:
1. The consumption for each unit
2. The gap between the total energy consumption (from the grid) and the consumption from all our meters. This so that we could find things I was not aware of or had forgotten.

We ran this for 6 months and where able to track, plan and reduce our consumption and plan when it happens. 
