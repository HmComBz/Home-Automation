import asyncio
import calendar
import configparser
import logging
import matplotlib.pyplot as plt
import numpy as np
import pushover
import pandas as pd
import requests
import threading
import time
from datetime import datetime, timedelta
from win32api import GetSystemMetrics

from Exports.shelly_export import Shelly

# Create logger for imported modules
logging_modules = logging.getLogger("imported_module")
logging_modules.setLevel(logging.ERROR)

# Create loggers for code
logger = logging.getLogger("server")
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

# GLOBAL VARS
DATA_PATH = config["PATHS"]["DATA_PATH"]


class Server():
    def __init__(self):
        # Parameters for importing data
        self.last_total_consumption_value = 0
        self.list_of_unit_IDs = []
        self.stopped = False

    #------------------------------------------------------------------------------------------
    def calculate_consumption_delta(self, last_value, time_diff, since_start, unit_id):
        # Calculate delta between this and last consumption value
        try:
            # Check if latest value is larger than last value
            if since_start > last_value:
                # If the difference between following row is maximum 1 hour
                if time_diff < 1.01:
                    consumption_kwh = (since_start - last_value) / (60*1000)
                # If the difference between following row is more than 1 hour
                else:
                    consumption_kwh = (since_start - last_value) / (60*1000*time_diff)
                return consumption_kwh
            # If no consumption has happend, return 0
            elif since_start == last_value:
                return 0
            # If the latest value is lower, alert the user
            else:
                message = "The since start counter has been reset for unit %s" % unit_id
                logger.info(message)
                self.pushover(message)
                return 0        
            logger.info("Consumption data calculated successfully")
        except Exception as e:
            logger.error("Failed to calculate consumption delta: %s" % e)
            return None

    #------------------------------------------------------------------------------------------
    def calculate_power_consumption(self, consumption_dict, unit_data, last_value):
        # Calculate the power and since start
        try:
            if unit_data[2] == "Energy Meter":
                power = consumption_dict[unit_data[0]]["power"]
                since_start = consumption_dict[unit_data[0]]["total"]
                return power, since_start
            # If a 3-phase, calculate since start from total, and power based on since start
            elif unit_data[2] == "Energy Meter 3-phase":   
                since_start = consumption_dict[unit_data[0]]["emeters"][0]["total"] * 60
                if last_value != 0:
                    power = (since_start - last_value) / 60
                else:
                    power = 0
                return power, since_start
        except Exception as e:
            logger.error("Failed to calculate power consumption: %s" % e)
            return None

    #------------------------------------------------------------------------------------------
    def import_consumption_data(self, units):
        # Loop through registered units and extract data, only extract data first
        # to avoid values to be too far from even hour.
        consumption_dict = {}
        for index, row in units.iterrows():
            try:
                if row[4] == "dynamic":
                    # Import data from unit
                    sh = Shelly(row[3])
                    if row[2] == "Energy Meter 3-phase":
                        consumption_dict[row[0]] = sh.get_status_3phase()
                    elif row[2] == "Energy Meter":
                        consumption_dict[row[0]] = sh.get_status_plug()
                    else:
                        consumption_dict[row[0]] = {"power":0, "total":0}      
                elif row[4] == "static":
                    power_temp = row[5] * 1000
                    consumption_dict[row[0]] = {"power":power_temp, "total":row[5]}
                else:
                    consumption_dict[row[0]] = {"power":0, "total":0}
            except Exception as e:
                logger.error("Retrieve data for unit %s failed: %s" % (row[3], e))
                self.pushover("Retrieve data for unit %s failed: %s" % (row[3], e))

        # Import consumption data from units
        try:
            csv_data = pd.read_csv("%sconsumption.csv" % DATA_PATH, delimiter=",")
            csv_data["datestamp"] = csv_data["datestamp"].astype('datetime64[ns]')
            csv_data.sort_values(by='datestamp', ascending=True)
        except Exception as e:
            logger.error("Import old consumption data failed: %s" % e)

        # Format data
        temp_list = []
        for index, row in units.iterrows():
            try:
                # Make a slice based on unit
                start_time = time.time()
                unit_history = csv_data.loc[csv_data["unit_id"] == row[0]]
                unit_history.sort_values(by=["datestamp"], ascending=True)

                # Get datestamp now rounded to even hours
                now = datetime.now().timestamp()
                now_rounded = now - (now % 3600)
                datestamp = datetime.fromtimestamp(now_rounded)
 
                # Get latest value and date rounded to even hours
                if len(unit_history) > 0:
                    last_date = unit_history["datestamp"].max()
                    last_date_timestamp = last_date.timestamp()
                    last_rounded = last_date_timestamp - (last_date_timestamp % 3600)
                    last_datestamp = datetime.utcfromtimestamp(last_rounded)

                    #  Get latest since start value
                    last_value = unit_history.iloc[-1]["since_start"]
                    end_time = time.time() - start_time
                    logger.info("Runtime for %s: %s" % (row[3], end_time))
                else:
                    # If first row from a new registered unit
                    last_datestamp = None
                    last_value = 0
                    time_diff = 1

                # Calculate diff between now and latest date and create a list of dates
                start_date = last_date + timedelta(hours=1)
                time_range = pd.date_range(start_date, datestamp, freq="H")
                time_diff = len(time_range) - 1

                # Exctract data from consumption csv data and create a temporary dict
                if row[4] == "dynamic":
                    power, since_start = self.calculate_power_consumption(consumption_dict, row, last_value)
                    if last_value != 0:
                        last_period = self.calculate_consumption_delta(last_value, time_diff, since_start, row[0])
                    else:
                        # For when no previous data exists, assuming the same power during the whole last hour
                        if row[2] == "Energy Meter":    
                            last_period = (since_start - power * 60) / (60*1000)
                        elif row[2] == "Energy Meter 3-phase":
                            last_period = 0
                        else:
                            last_period = 0
                elif row[4] == "static":
                    power = consumption_dict[row[0]]["power"]
                    if len(unit_history) == 0:
                        since_start = consumption_dict[row[0]]["total"]
                    else:
                        since_start = len(unit_history) * consumption_dict[row[0]]["total"]
                    last_period = consumption_dict[row[0]]["total"]

                # Check if normal period or extended period
                if time_diff == 1 or len(unit_history) == 0:
                    temp_list.append({"unit_id":row[0], "datestamp":datestamp, "power":power, 
                    "since_start":since_start, "last_period":last_period})
                else:
                    # If a break has occured, enter rows with average values for the period of the break
                    counter = 1
                    for h in time_range:
                        next_since_start = last_value + round(counter * last_period * (60*1000))
                        temp_list.append({"unit_id":row[0], "datestamp":h, "power":power, 
                        "since_start":next_since_start, "last_period":last_period})
                        counter += 1
                logger.info("Consumption data imported successfully from all units")
            except Exception as e:
                logger.error("Format imported consumption data from %s failed: %s" % (row[3], e))

        # Save consumption to csv
        self.save_unit_consumption(csv_data, temp_list)
        logger.info("Unit data successfully imported")

        return temp_list

    #------------------------------------------------------------------------------------------
    def import_unit_data(self):
        # Import units
        try:
            units = pd.read_csv("%sunits.csv" % DATA_PATH, delimiter=",")
            self.list_of_unit_IDs = units["id"].tolist()
            logger.info("Unit CSV load succesfully")
            return units
        except Exception as e:
            logger.error("Unit CSV failed to load: %s" % e)
            return None

    #------------------------------------------------------------------------------------------
    def pushover(self, message):
        ''' pushover.net. The app-token comes from the registered app on the
        webpage. The user-key comes from the user account.'''
        try:
            r = requests.post("https://api.pushover.net/1/messages.json", data = {
              "token": "ax77amfzph7vnxs95f5gr2q298u6eq",
              "user": "u6584c5ty6g8mgm7jf7nk9ii551gzr",
              "message": message
            }
            )
        except Exception as e:
            logging.error("Pushover failed to deliver message.", exc_info=True)
    
    #------------------------------------------------------------------------------------------
    def run(self):
        # Main loop
        try:
            while not self.stopped:
                # Get current minute and hour for deleting old alarms
                now = datetime.now()
                minute = now.minute
                second = now.second

                # Chech if start of hour
                if minute == 0 and second == 0:
                    # Update unit data
                    units = self.import_unit_data()

                    # Import unit consumption
                    self.import_consumption_data(units)

                    # Wait 60 seconds
                    time.sleep(60)
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.error("Caught keyboard interrupt, exiting.")
        except Exception as e:
            logger.error("The main loop got canceled due to: %s" % e)
        finally:
            logger.error("Something unexpected went wrong.")

    #------------------------------------------------------------------------------------------
    def save_unit_consumption(self, csv_data, new_data):
        # Save unit consumption to CSV
        try:
            for row in new_data:
                csv_data = csv_data.append(row, ignore_index = True)
            csv_data.to_csv("%sconsumption.csv" % DATA_PATH, decimal=".", index=False)
            logger.info("Consumption data updated successfully")
        except Exception as e:
            logger.error("Consumption CSV failed to update: %s" % e)
            self.pushover("Consumption CSV failed to update: %s" % e)

    #------------------------------------------------------------------------------------------
    def stop(self):
        # Stop Server script
        self.stopped = True
        logger.info('Server has been shut down.')


if __name__ == '__main__':
    # Run main script
    server = Server()
    server.run()
