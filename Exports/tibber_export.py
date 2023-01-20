import asyncio
import configparser
import logging
import os
import tibber
import wx
import pandas as pd

# Create loggers for code
logger = logging.getLogger("Tibber export")
logger.setLevel(logging.INFO)
logger.propagate = False

# Create handler
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.INFO)

# Add handler to logger
logger.addHandler(consoleHandler)

# Set formatting to logger
formatter = logging.Formatter('%(asctime)s  %(name)s  %(levelname)s: %(message)s')
consoleHandler.setFormatter(formatter)

# Import config file
config = configparser.ConfigParser()
config.read('config.ini')

DATA_PATH = config["PATHS"]["DATA_PATH"]


async def main():
    access_token = os.getenv("TIBBER_API")
    tibber_connection = tibber.Tibber(access_token)
    await tibber_connection.update_info()

    # The imported consumption data
    consumption = pd.DataFrame(columns=["from", "totalCost", "cost", "consumption"])

    homes = tibber_connection.get_homes()
    for home in homes: 
        await home.update_info()
        await home.update_price_info()
        await home.fetch_consumption_data()
        for data in home.hourly_consumption_data:
            consumption = consumption.append(data, ignore_index=True)
        
        # Check if any data was imported
        if len(consumption.index) > 0:
            consumption.to_csv("%stibber_consumption.csv" % DATA_PATH, decimal=".")
            wx.MessageBox("Tibber data imported successfully!", "Download successful" ,wx.OK | wx.ICON_INFORMATION)
        else:
            logger.error("No data was imported from Tibber")
            wx.MessageBox("Failed to download Tibber data!", "Download failed" ,wx.OK | wx.ICON_INFORMATION)

    await tibber_connection.close_connection()


if __name__ ==  '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())