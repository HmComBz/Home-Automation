import asyncio
import calendar
import configparser
import logging
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import threading
import time
import wx
import wx.adv

from datetime import datetime, timedelta
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from operator import add
from win32api import GetSystemMetrics

from Units import add_unit
from Exports.shelly_export import Shelly
from Exports import tibber_export

# Create loggers for code
logger = logging.getLogger("Main Panel")
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
x_pos = 0
y_pos = 0
x_size = GetSystemMetrics(0)
y_size = GetSystemMetrics(1)
left_panel_w = 300
DATA_PATH = config["PATHS"]["DATA_PATH"]
colors = ["#8FA6AC", "#8A584C", "#4F583D", "#CEB793", "#85865F", "#F5EACF", "#C39E9E", "#69A6D1", "#94DFFF",
            "#E06377", "#FFD481", "#FCADB0", "#F9D5E5", "#EEAC99", "#C9EBEF", "#C83349", "#5B9AA0", "#D6D44E0", "#B8A9C9",
            "#622569"]
plt.style.use('ggplot')


class MainPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.chart_data_details = {}
        self.chart_data_overview = {}
        self.end_date = None
        self.SetBackgroundColour((255, 255, 255))
        self.start_date = None
        self.tibber_updated = False
        self.timestamp_unit_consumption_data = None
        self.timestamp_tibber_data = None
        
        # Import csv data
        self.data_tibber = self.import_tibber_data_csv()
        self.data_unit_consumption = self.import_unit_consumption_data_csv()

        # Create box sizers
        self.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.visualSizer1 = wx.BoxSizer(wx.HORIZONTAL)

        # Add Sub-sizers to main sizer
        self.mainSizer.Add(self.visualSizer1)

        # Import data
        self.chart_data_overview = self.calculate_tibber_data()

        # Create barchart
        self.canvas1 = self.create_main_charts()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(self.canvas1, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)

    #------------------------------------------------------------------------------------------
    def calculate_default_date_selection(self):
        # Calculate default date based on current month
        try:
            first_date_this_m = datetime(year=datetime.now().year, month=datetime.now().month, day=1)
            last_day_this_m = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
            last_date_this_m = datetime(year=datetime.now().year, month=datetime.now().month, day=last_day_this_m)
            return first_date_this_m, last_date_this_m
        except Exception as e:
            logger.info("Failed to calculate default date selection: %s" % e)
            return None, None

    #------------------------------------------------------------------------------------------
    def calculate_tibber_data(self):
        # Import Tibber data
        unit_consumption_data = self.slice_dataset("unit_consumption", "tibber", "")
        tibber_consumption_all = self.slice_dataset("tibber", "tibber", "all")
        tibber_consumption_data = self.slice_dataset("tibber", "tibber", "")

        try:
            # Create dataset for consumption and prices per month
            monthly_data = tibber_consumption_all.groupby(by=["year_month"]).agg(
                Cost=("cost", "sum"),
                Consumption=("consumption", "sum"),
                AvgPrice=("electric_price", "mean")
            )
            monthly_data["AvgDailyCost"] = monthly_data["AvgPrice"] * monthly_data["Consumption"]
            monthly_data["DiffVsAverage"] = monthly_data["Cost"] - monthly_data["AvgDailyCost"]
        except Exception as e:
            logger.error("Failed to import data montly Tibber data: %s" % e)
            return {}

        try:
            # Create datasets for consumption and prices per day
            daily_data = tibber_consumption_data.groupby("date").agg(
                Cost=("cost", "sum"),
                Consumption=("consumption", "sum"),
                AvgPrice=("electric_price", "mean"), 
                MinPrice=("electric_price", "min"),
                MaxPrice=("electric_price", "max")
            )
            daily_data["AvgDailyCost"] = daily_data["AvgPrice"] * daily_data["Consumption"]
            daily_data["MinDailyCost"] = daily_data["MinPrice"] * daily_data["Consumption"]
            daily_data["MaxDailyCost"] = daily_data["MaxPrice"] * daily_data["Consumption"]
            daily_data["DiffVsAverage"] = daily_data["Cost"] - daily_data["AvgDailyCost"]
            daily_data["DiffVsMin"] = daily_data["Cost"] - daily_data["MinDailyCost"]
            daily_data["DiffVsMax"] = daily_data["MaxDailyCost"] - daily_data["Cost"]

            # Calculate data for savings detailed
            diffvsmin = daily_data["DiffVsMin"]
            diffvsmax = daily_data["DiffVsMax"]
            totals = [i+j for i,j in zip(diffvsmin, diffvsmax)]
            greenBars = [i / j * 100 for i,j in zip(diffvsmax, totals)]
            redBars = [i / j * 100 for i,j in zip(diffvsmin, totals)]
        except Exception as e:
            logger.error("Failed to import data for daily Tibber data: %s" % e)
            return {}

        try:
            # Create dataset for consumption per hour
            hourly_data = tibber_consumption_data.copy()
            hourly_data = self.filter_dataset_by_date_selection(hourly_data, "read_tibber_csv")
            hourly_data = hourly_data.groupby(by=["time"]).agg(
                Cost=("cost", "sum"),
                Consumption=("consumption", "sum"),
                AvgPrice=("electric_price", "mean")
            )
            hourly_data["AvgDailyCost"] = hourly_data["AvgPrice"] * hourly_data["Consumption"]
            hourly_data["DiffVsAverage"] = hourly_data["Cost"] - hourly_data["AvgDailyCost"]
        except Exception as e:
            logger.error("Failed to import data for daily Tibber data: %s" % e)
            return {}

        try:
            # Get lists for graphs monthly
            dates_monthly = monthly_data.index.tolist()
            dates_montly_formatted = [int(date) for date in dates_monthly]
            consumption_monthly = monthly_data["Consumption"].tolist()
            realcost_monthly = monthly_data["Cost"].tolist()
            avgprice_monthly = monthly_data["AvgPrice"].tolist()
            diffvsaverage_monthly = monthly_data["DiffVsAverage"].tolist()
        except Exception as e:
            logger.error("Failed to create lists for montly Tibber data: %s" % e)
            return {}

        try:
            # Get lists for graphs daily
            dates = daily_data.index.tolist()
            consumption = daily_data["Consumption"].tolist()
            realcost = daily_data["Cost"].tolist()
            avgprice = daily_data["AvgPrice"].tolist()
            minprice = daily_data["MinPrice"].tolist()
            maxprice = daily_data["MaxPrice"].tolist()
            avgdailyprice = daily_data["AvgDailyCost"].tolist()
            mindailyprice = daily_data["MinDailyCost"].tolist()
            maxdailyprice = daily_data["MaxDailyCost"].tolist()
            diffvsaverage = daily_data["DiffVsAverage"].tolist()
        except Exception as e:
            logger.error("Failed to create lists for daily Tibber data: %s" % e)
            return {}

        try:
            # Get lists for graphs hourly
            time_hourly = hourly_data.index.tolist()
            cost_hourly = hourly_data["Cost"].tolist()
            consumption_hourly = hourly_data["Consumption"].tolist()
            avgprice_hourly = hourly_data["AvgPrice"].tolist()
            avghourprice = hourly_data["AvgDailyCost"].tolist()
            diffvsaveragehour = hourly_data["DiffVsAverage"].tolist()
        except Exception as e:
            logger.error("Failed to create lists for hourly Tibber data: %s" % e)
            return {}

        return {"dates":dates, "consumption":consumption, "avgprice":avgprice, "minprice":minprice, 
        "maxprice":maxprice, "avgdailyprice":avgdailyprice, "mindailyprice":mindailyprice, "maxdailyprice":maxdailyprice, 
        "diffvsaverage":diffvsaverage, "diffvsmin":diffvsmin, "realcost":realcost, "dates_monthly":dates_montly_formatted, 
        "consumption_monthly":consumption_monthly, "avgprice_monthly":avgprice_monthly,
        "diffvsaverage_monthly":diffvsaverage_monthly, "realcost_monthly":realcost_monthly,
        "time_hourly":time_hourly, "consumption_hourly":consumption_hourly, "avgprice_hourly":avgprice_hourly,
        "avghourprice":avghourprice, "diffvsaveragehour":diffvsaveragehour, "cost_hourly":cost_hourly,
        "greenBars":greenBars, "redBars":redBars}

    #------------------------------------------------------------------------------------------
    def calculate_unit_consumption(self, unit):
        try:
            # Import unit consumption data
            unit_consumption_data = self.slice_dataset("unit_consumption", "all", "")
            unit_id_unique = unit_consumption_data["unit_id"].unique().tolist()
            print(unit_id_unique)
            
            # Import unit data
            unit_data = self.import_unit_data_csv()
            unit_data = unit_data[unit_data.index.isin(unit_id_unique)]
            unit_list = unit_data["name"].tolist()
            unit_list.append("Unknown")

            # Edit data
            dates_list = unit_consumption_data.index.unique().to_list()

            # Join tables
            combined_data = unit_consumption_data.join(unit_data, on=["unit_id"], how="inner")
            combined_data.sort_values(by="datestamp", ascending=True)
            daily_chart_data = combined_data.groupby(by=["date", "name"]).agg(
                LastPeriod=("last_period", "sum"),
            )
            hourly_chart_data = combined_data.groupby(by=["time", "name"]).agg(
                LastPeriod=("last_period", "sum"),
            )

            # Create daily data for selected unit
            daily_data = combined_data[combined_data["unit_id"] == int(unit)]
            daily_data = daily_data.groupby(by=["date"]).agg(
                Consumption=("last_period", "sum"),
            )
            daily_consumption = daily_data["Consumption"].to_list()
            daily_date = daily_data.index.to_list()

            # Create hour data for selected unit
            hour_data = combined_data[combined_data["unit_id"] == int(unit)]
            hour_data = hour_data.groupby(by=["time"]).agg(
                Consumption=("last_period", "sum"),
            )
            hour_consumption = hour_data["Consumption"].to_list()
            hour_labels = hour_data.index.to_list()
            unit_name = unit_list[int(unit)]

            # Create color list and dict
            num_units = len(unit_list)
            color_list = colors[0:num_units]
            color_dict = dict(zip(unit_list, color_list))

            # Create lists for combined daily graph
            units_dict = self.create_equal_size_dict(unit_list, dates_list, daily_chart_data, "date", "LastPeriod")

            # Create list for combined hourly graph
            units_dicts_hours = self.create_equal_size_dict(unit_list, hour_labels, hourly_chart_data, "time", "LastPeriod")

            return {"dates":dates_list, "units_dict":units_dict, "units":unit_list, "colors":color_list,
            "color_dict":color_dict, "hour_consumption":hour_consumption, "hour_labels":hour_labels,
            "units_dicts_hours":units_dicts_hours, "unit_name":unit_name, "daily_consumption":daily_consumption,
            "daily_date":daily_date}
        except Exception as e:
            logger.error("Failed to import consumption data: %s" % e)
            return None

    #------------------------------------------------------------------------------------------
    def calculate_unit_details(self):
        # Import unit consumption data
        unit_consumption_data = self.slice_dataset("unit_consumption", "tibber", "")
        unit_id_unique = unit_consumption_data["unit_id"].unique().tolist()

        # Import unit data for active units and create lists for labels
        unit_data = self.import_unit_data_csv()
        unit_data = unit_data[unit_data.index.isin(unit_id_unique)]
        unit_list = unit_data["name"].tolist()
        unit_list.append("Unknown")
        dates_list = unit_consumption_data.index.unique().to_list()
        hour_list = unit_consumption_data["time"].unique().tolist()

        # Import Tibber data
        tibber_data = self.slice_dataset("tibber", "unit_details", "")
        dates_list_tibber = tibber_data.index.unique().to_list()
        tibber_daily = tibber_data.groupby("date").agg(
                Consumption=("consumption", "sum"),
        )
        tibber_hourly = tibber_data.groupby("time").agg(
                Consumption=("consumption", "mean"),
        )

        # Create table for electric price per unit consumption
        unit_price_data = pd.merge(unit_consumption_data, tibber_data[["timestamp", "electric_price"]], on=["timestamp"], how="inner")
        unit_price_data["total_cost"] = unit_price_data["last_period"] * unit_price_data["electric_price"]
        unit_price_data["date"] = unit_price_data["timestamp"].astype(str).str[:10]
        unit_price_data["date"] = unit_price_data["date"].astype('datetime64[ns]')
        unit_price_data = unit_price_data.join(unit_data[["name"]], on=["unit_id"], how="inner")
        unit_price_data = unit_price_data.groupby(by=["date", "name"]).agg(
                TotalCost=("total_cost", "sum"),
                Consumption=("last_period", "sum")
            )
        unit_price_data["avg_eprice"] = unit_price_data["TotalCost"] / unit_price_data["Consumption"]
        unit_price_data.fillna(0)
        unit_price_dict = self.create_equal_size_dict(unit_list, dates_list, unit_price_data, "date", "TotalCost")
        
        # Calculate data for savings detailed
        total_list = []
        temp_sum = 0
        counter = 0
        for date in dates_list:
            for unit in unit_list:
                temp_sum += unit_price_dict[unit][counter]
            total_list.append(temp_sum)
            counter += 1
            temp_sum = 0

        # Calculate per unit data
        unit_price_lists = []
        temp_list = []
        counter = 0
        for unit in unit_list:
            for total in total_list:
                if total != 0:
                    temp_value = unit_price_dict[unit][counter] / total
                else:
                    temp_value = 0
                temp_list.append(temp_value)
                counter += 1
            unit_price_lists.append(temp_list)
            temp_list = []
            counter = 0

        # Combine datasets
        combined_data = unit_consumption_data.join(unit_data, on=["unit_id"], how="left")

        # Create grouped datasets for unit consumption based on different aggregations
        # Total daily data
        unit_daily = combined_data.groupby(by=["date"]).agg(
            Consumption=("last_period", "sum")
        )
        # Hourly data
        unit_hourly = combined_data.groupby(by=["time", "name"]).agg(
            Consumption=("last_period", "mean")
        )
        unit_hourly["Total Consumption"] = unit_hourly.groupby(level=0).Consumption.transform('sum')
        unit_hourly.index = unit_hourly.index.droplevel(1)
        unit_hourly = unit_hourly[~unit_hourly.index.duplicated(keep='first')]
        unit_hourly.drop(columns=["Consumption"], inplace=True)

        # Total per unit data
        unit_consumption = combined_data.groupby(by=["unit_id", "name"]).agg(
            Consumption=("last_period", "sum"),
        )

        # Total per unit data
        unit_daily_data = combined_data.groupby(by=["date", "name"]).agg(
            Consumption=("last_period", "sum"),
        )
        unit_daily_data["Total Consumption"] = unit_daily_data.groupby(level=0).Consumption.transform('sum')
        unit_daily_data["Quota"] = unit_daily_data["Consumption"] / unit_daily_data["Total Consumption"]

        # Data per hour and unit
        unit_hourly_data = combined_data.groupby(by=["time", "name"]).agg(
            Consumption=("last_period", "mean")
        )

        # Data for difference between Tibber and units
        total_difference = self.create_total_combined_consumption(tibber_data, combined_data)
  
        # Get lists for the graphs
        unit_consumption_list = unit_consumption["Consumption"].tolist()
        unit_daily_consumption_list = unit_daily["Consumption"].tolist()
        unit_hourly_consumption_list = unit_hourly["Total Consumption"].tolist()
        tibber_consumption_list = tibber_daily["Consumption"].tolist()
        tibber_hourly_consumption_list = tibber_hourly["Consumption"].tolist()
        difference_consumption = total_difference["Difference"].tolist()
        difference_hours = [datetime.strptime(date, "%Y-%m-%d %H:%M:%S") for date in total_difference.index.to_list()]

        # Create equal size data for graphs for unit daily data
        units_dict = self.create_equal_size_dict(unit_list, dates_list, unit_daily_data, "date", "Consumption")
        units_dict_hour = self.create_equal_size_dict(unit_list, hour_list, unit_hourly_data, "time", "Consumption")

        # Create a list for the difference between Tibber and unit consumption
        difference_daily = self.calculate_difference_tibber_unit_consumption(tibber_consumption_list, unit_daily_consumption_list)
        difference_hourly = self.calculate_difference_tibber_unit_consumption(tibber_hourly_consumption_list, unit_hourly_consumption_list)
        units_dict["Unknown"] = difference_daily
        units_dict_hour["Unknown"] = difference_hourly
        unit_consumption_list.append(sum(difference_daily))
        unit_daily_consumption_list.append(sum(difference_hourly))

        # If one or more units does not yet have consumption, add a 0
        if len(unit_consumption) < len(unit_list):
            for i in range(len(unit_consumption), len(unit_list)):
                if unit_list[i] != "Unknown":
                    unit_consumption.loc[(i, unit_list[i]),:] = 0
                else: 
                    unit_consumption.loc[(i, unit_list[i]),:] = sum(difference_daily)

        # Create color list and color dict
        num_units = len(unit_list)
        color_list = colors[0:num_units]
        color_dict = dict(zip(unit_list, color_list))

        return {"units":unit_list, "unit_consumption":unit_consumption_list, "units_dict":units_dict, "units_dict_hour":units_dict_hour, 
        "dates":dates_list, "tibber_dates":dates_list_tibber, "color_dict":color_dict, 
        "color_list":color_list, "tibber_consumption":tibber_consumption_list, "hours":hour_list, "diff_consumption":difference_consumption,
        "diff_time":difference_hours, "unit_price_dict":unit_price_dict, "unit_price_lists":unit_price_lists}

    #------------------------------------------------------------------------------------------
    def calculate_difference_tibber_unit_consumption(self, tibber_data_list, unit_data_list):
        # Calculate difference between tibber data and unit data
        difference = [tibb - unit if tibb > 0 else 0 for tibb, unit in zip(tibber_data_list, unit_data_list)]
        for i in range(0, (len(unit_data_list) - len(tibber_data_list))): # Since Tibber data lags, add 0 for each missing Tibber day
            difference.append(0)
        return difference

    #------------------------------------------------------------------------------------------
    def clear_sizer(self, sizer):
        # Clear sizer from content
        sizer.Clear(True)

    #------------------------------------------------------------------------------------------
    def create_total_combined_consumption(self, tibber_data, unit_data):
        # Create groupings of consumption data
        tibber_datestamp = tibber_data.groupby(by=["timestamp"]).agg(Consumption_tibber=("consumption", "sum"))
        unit_datestamp = unit_data.groupby(by=["timestamp"]).agg(Consumption_units=("last_period", "sum"))
        combined_data = tibber_datestamp.join(unit_datestamp, on=["timestamp"], how="inner")
        combined_data = combined_data[combined_data["Consumption_tibber"] > 0]
        combined_data["Difference"] = combined_data["Consumption_tibber"] - combined_data["Consumption_units"]
        return combined_data

    #------------------------------------------------------------------------------------------
    def create_savings_view(self):
        # create charts
        figure = Figure(figsize=((x_size-left_panel_w)/100, (y_size*0.9)/100), facecolor="None")
        figure.subplots_adjust(hspace=0.5, wspace=0.5, bottom=0.15)

        # Create subplot 1
        axes1 = figure.add_subplot(211)
        axes1.title.set_text('Potential Savings (Daily)')
        axes1.set_xlabel('Date')
        axes1.set_ylabel('Kr')
        bl1a = axes1.bar(self.chart_data_overview["dates"], self.chart_data_overview["diffvsmin"], color="grey")
        axes1.tick_params(rotation=45)
        if len(self.chart_data_overview["dates"]) <= 60:
            counter = 0
            for p in bl1a:
                height = p.get_height()
                axes1.annotate('{0:.0f}'.format(self.chart_data_overview["diffvsmin"][counter]),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
                counter += 1

        # Create subplot 2
        axes2 = figure.add_subplot(212)
        axes2.title.set_text('The real distance between the actual paid price, and max and min (%)')
        axes2.set_xlabel('Date')
        axes2.set_ylabel('%')
        barWidth = 0.85
        axes2.bar(self.chart_data_overview["dates"], self.chart_data_overview["redBars"], color='#f94449', edgecolor='white', width=barWidth)
        axes2.bar(self.chart_data_overview["dates"], self.chart_data_overview["greenBars"], bottom=self.chart_data_overview["redBars"], color='#a4c196', edgecolor='white', width=barWidth)
        if len(self.chart_data_overview["dates"]) <= 30:
            counter = 0
            for p in self.chart_data_overview["dates"]:
                width = self.chart_data_overview["dates"][counter]
                max_diff = self.chart_data_overview["greenBars"][counter]
                min_diff = self.chart_data_overview["redBars"][counter]
                axes2.annotate('{0:.0f}'.format(max_diff),
                    xy=(width, min_diff + (max_diff/2)),
                    xytext=(0, 0), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
                axes2.annotate('{0:.0f}'.format(min_diff),
                    xy=(width, min_diff/2),
                    xytext=(0, 0), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
                counter += 1

        # Create a canvas to add to the panel
        canvas = FigureCanvas(self, -1, figure)
        canvas.mpl_connect("motion_notify_event", self.hover)
        
        return canvas

    #------------------------------------------------------------------------------------------
    def create_detailed_unit_view(self):
        # Create canvas with detailed graphs
        figure = Figure(figsize=((x_size-left_panel_w)/100, (y_size*0.9)/100), facecolor="None")
        figure.subplots_adjust(hspace=0.5, wspace=0.5, bottom=0.15)

        # Create subplot 1
        axes1 = figure.add_subplot(221)
        axes1.title.set_text('Consumption per unit')
        bh1 = axes1.barh(self.chart_data_unit_details["units"], self.chart_data_unit_details["unit_consumption"], 
        color=self.chart_data_unit_details["color_list"])
        for p in bh1:
                width = p.get_width()
                axes1.annotate('{0:.0f}'.format(width),
                    xy=(p.get_width() + 1, p.get_y() + p.get_height() / 2),
                    xytext=(0, -3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
        handles = [plt.Rectangle((0,0),1,1, color=self.chart_data_unit_details["color_dict"][label]) for label in self.chart_data_unit_details["units"]]
        handles.append(mlines.Line2D([], [], marker='_',
                          markersize=15, color="#000000"))
        legend_list = self.chart_data_unit_details["units"].copy()
        axes1.legend(handles, legend_list)
        axes1.set_facecolor('white')

        # Create subplot 2
        axes2 = figure.add_subplot(222)
        axes2.title.set_text('Tibber vs. Unit Consumption')     
        axes2.plot(self.chart_data_unit_details["tibber_dates"], self.chart_data_unit_details["tibber_consumption"], color="#000000")
        color_count = 0
        bottom_value = self.create_list_of_zeroes(len(self.chart_data_unit_details["dates"]))
        for unit in self.chart_data_unit_details["units"]:
            axes2.bar(self.chart_data_unit_details["dates"], self.chart_data_unit_details["units_dict"][unit], 
            bottom=bottom_value, color=self.chart_data_unit_details["color_dict"][unit])
            bottom_value = list(map(add, bottom_value, self.chart_data_unit_details["units_dict"][unit]))
            color_count += 1
        axes2.set_facecolor('white')
        handles = [plt.Rectangle((0,0),1,1, color=self.chart_data_unit_details["color_dict"][label]) for label in self.chart_data_unit_details["units"]]
        handles.append(mlines.Line2D([], [], marker='_',
                          markersize=15, color="#000000"))
        legend_list = self.chart_data_unit_details["units"].copy()
        legend_list.append("Tibber consumption")
        axes2.legend(handles, legend_list)
        axes2.tick_params(rotation=45)

        # Create subplot 3
        axes3 = figure.add_subplot(223)
        axes3.title.set_text('Difference between real and measured consumption')
        axes3.set_xlabel('Hour')
        axes3.set_ylabel('kWh')
        axes3.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        axes3.tick_params(rotation=45)
        bl3 = axes3.bar(self.chart_data_unit_details["diff_time"], self.chart_data_unit_details["diff_consumption"], width=0.1, color="#E06377")
        list_of_values = self.get_largest_values_from_list(bl3, 30)
        for p in list_of_values:
            height = p.get_height()
            axes3.annotate('{0:.2f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
        
        # Create subplot 4
        axes4 = figure.add_subplot(224)
        axes4.title.set_text('Unit Consumption per unique hour')     
        color_count = 0
        bottom_value = self.create_list_of_zeroes(len(self.chart_data_unit_details["hours"]))
        for unit in self.chart_data_unit_details["units"]:
            bl4 = axes4.bar(self.chart_data_unit_details["hours"], self.chart_data_unit_details["units_dict_hour"][unit], 
            bottom=bottom_value, color=self.chart_data_unit_details["color_dict"][unit])
            bottom_value = list(map(add, bottom_value, self.chart_data_unit_details["units_dict_hour"][unit]))
            color_count += 1
        axes4.set_facecolor('white')
        handles = [plt.Rectangle((0,0),1,1, color=self.chart_data_unit_details["color_dict"][label]) for label in self.chart_data_unit_details["units"]]
        handles.append(mlines.Line2D([], [], marker='_',
                          markersize=15, color="#000000"))
        legend_list = self.chart_data_unit_details["units"].copy()
        axes4.legend(handles, legend_list)
        axes4.tick_params(rotation=45)

        # Create a canvas to add to the panel
        canvas = FigureCanvas(self, -1, figure)
        canvas.mpl_connect("motion_notify_event", self.hover)
        
        return canvas

    #-------------------------------------------------------------------------------------------
    def get_largest_values_from_list(self, list1, N):
        # Get largest N values from a selected list
        temp_list = []
        for p in list1:
            if len(temp_list) == 0:
                temp_list.append(p)
            else:
                for i in range(0, len(temp_list)):
                    if p.get_height() > temp_list[i].get_height():
                        if len(temp_list) < N:
                            temp_list.insert(i, p)
                            break
                        else:
                            del temp_list[0]
                            temp_list.insert(i, p)
                            break
        return temp_list

    #-------------------------------------------------------------------------------------------
    def create_detailed_view(self):
        # Create canvas with detailed graphs
        figure = Figure(figsize=((x_size-left_panel_w)/100, (y_size*0.9)/100), facecolor="None")
        figure.subplots_adjust(hspace=0.5, wspace=0.5, bottom=0.15)

        # Create subplot 1
        axes1 = figure.add_subplot(221)
        axes1.title.set_text('Consumption')
        axes1.set_xlabel('Date')
        axes1.set_ylabel('kWh')
        axes1.set_ylim([0, 1.2*max(self.chart_data_details["daily_consumption"])])
        bl1 = axes1.bar(self.chart_data_details["daily_date"], self.chart_data_details["daily_consumption"], 
        color=self.chart_data_details["color_dict"][self.chart_data_details["unit_name"]])
        axes1.tick_params(rotation=45)
        if len(self.chart_data_details["daily_date"]) <= 31:
            for p in bl1:
                height = p.get_height()
                axes1.annotate('{0:.1f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

        # Create subplot 2
        axes2 = figure.add_subplot(222)
        axes2.title.set_text('Consumption per unit')
        axes2.set_xlabel('Date')
        axes2.set_ylabel('kWh')
        axes2.tick_params(rotation=45)
        color_count = 0
        bottom_value = self.create_list_of_zeroes(len(self.chart_data_details["dates"]))
        for unit in self.chart_data_details["units"]:
            axes2.bar(self.chart_data_details["dates"], self.chart_data_details["units_dict"][unit], bottom=bottom_value, color=self.chart_data_details["colors"][color_count])
            bottom_value = list(map(add, bottom_value, self.chart_data_details["units_dict"][unit]))
            color_count += 1
        handles = [plt.Rectangle((0,0),1,1, color=self.chart_data_details["color_dict"][label]) for label in self.chart_data_details["units"]]
        axes2.legend(handles, self.chart_data_details["units"])

        # Create subplot 3
        axes3 = figure.add_subplot(223)
        axes3.title.set_text('Consumption per hour')
        axes3.set_xlabel('Date')
        axes3.set_ylabel('kWh')
        axes3.set_ylim([0, 1.2*max(self.chart_data_details["hour_consumption"])])
        bl3 = axes3.bar(self.chart_data_details["hour_labels"], self.chart_data_details["hour_consumption"], 
        color=self.chart_data_details["color_dict"][self.chart_data_details["unit_name"]])
        axes3.tick_params(rotation=45)
        if len(self.chart_data_details["hour_labels"]) <= 25:
            for p in bl3:
                height = p.get_height()
                axes3.annotate('{0:.0f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

        # Create subplot 4
        axes4 = figure.add_subplot(224)
        axes4.title.set_text('Consumption per unit and hour')
        axes4.set_xlabel('Date')
        axes4.set_ylabel('kWh')
        axes4.tick_params(rotation=45)
        color_count = 0
        bottom_value = self.create_list_of_zeroes(len(self.chart_data_details["hour_labels"]))
        for unit in self.chart_data_details["units"]:
            axes4.bar(self.chart_data_details["hour_labels"], self.chart_data_details["units_dicts_hours"][unit], bottom=bottom_value, color=self.chart_data_details["colors"][color_count])
            bottom_value = list(map(add, bottom_value, self.chart_data_details["units_dicts_hours"][unit]))
            color_count += 1
        handles = [plt.Rectangle((0,0),1,1, color=self.chart_data_details["color_dict"][label]) for label in self.chart_data_details["units"]]
        axes4.legend(handles, self.chart_data_details["units"])

        # Create a canvas to add to the panel
        canvas = FigureCanvas(self, -1, figure)
        canvas.mpl_connect("motion_notify_event", self.hover)
        
        return canvas

    #------------------------------------------------------------------------------------------
    def create_equal_size_dict(self, units, label_list, dataset, index_name, column_title):
        # Create a equal size dict from a grouped dataset containing 2 group by columns and one value
        try:
            start_time = time.time()
            units_dict = self.create_unit_dict(units)
            for label in label_list:
                active_units = []
                for index, row in dataset[dataset.index.get_level_values(index_name) == label].iterrows():
                    if index[0] == label: 
                        units_dict[index[1]].append(row[column_title])
                        active_units.append(index[1])
                for unit in units:
                    if unit not in active_units:
                        units_dict[unit].append(0)
            logger.info("Equal size dict created successfully in %s" % (time.time()-start_time))
            return units_dict
        except Exception as e:
            logger.info("Failed to create equal size dict: %s" % e)
            return None

    #------------------------------------------------------------------------------------------
    def create_list_of_zeroes(self, num):
        # Create a list of zeroes
        zeroes_list = []
        for i in range(0, num):
            zeroes_list.append(0)
        return zeroes_list

    #------------------------------------------------------------------------------------------
    def create_main_charts(self):
        # Create a barchart
        figure = Figure(figsize=((x_size-left_panel_w)/100, (y_size*0.9)/100), facecolor="None", edgecolor='none')
        figure.subplots_adjust(hspace=0.5, wspace=0.5, bottom=0.15)

        # Create subplot 1
        axes1 = figure.add_subplot(331)
        axes1.title.set_text('Real cost (R12)')
        axes1.set_xlabel('Year-Month')
        axes1.set_ylabel('Kr')
        axes1.yaxis.set_major_formatter(FormatStrFormatter('%.0f'))
        axes1.tick_params(rotation=45)
        bl1 = axes1.bar(self.chart_data_overview["dates_monthly"], self.chart_data_overview["realcost_monthly"])
        axes1.ticklabel_format(useOffset=False, style='plain', axis="x")
        for p in bl1:
            height = p.get_height()
            axes1.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')

        # Create subplot 2
        axes2 = figure.add_subplot(332)
        axes2.title.set_text('Real cost vs. average cost (R12)')
        axes2.set_xlabel('Year-Month')
        axes2.set_ylabel('Kr')
        axes2.ticklabel_format(style='plain')
        x = np.asarray(self.chart_data_overview["dates_monthly"])
        y = np.asarray(self.chart_data_overview["diffvsaverage_monthly"])
        mask1 = y < 0
        mask2 = y >= 0
        bl2a = axes2.bar(x[mask1], y[mask1], color="green")
        bl2b = axes2.bar(x[mask2], y[mask2], color="red")
        axes2.ticklabel_format(useOffset=False, style='plain', axis="x")
        for p in bl2a:
            height = p.get_height()
            axes2.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, -15), # -15 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
        for p in bl2b:
            height = p.get_height()
            axes2.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
        axes2.tick_params(rotation=45)

        # Create subplot 3
        axes3 = figure.add_subplot(333)
        axes32 = axes3.twinx()  
        axes3.title.set_text('Consumption vs Electrical price (R12)')
        axes3.set_xlabel('Year-Month')
        axes3.set_ylabel('kWh')
        axes32.set_ylabel('Kr')
        axes3.tick_params(rotation=45)
        axes32.plot(self.chart_data_overview["dates_monthly"], self.chart_data_overview["avgprice_monthly"], color="black")
        axes32.grid(False)
        bl3 = axes3.bar(self.chart_data_overview["dates_monthly"], self.chart_data_overview["consumption_monthly"], color="orange")
        axes3.ticklabel_format(useOffset=False, style='plain', axis="x")
        for p in bl3:
            height = p.get_height()
            axes3.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
        y_max = 1.0

        # Create subplot 4
        axes4 = figure.add_subplot(334)
        axes4.title.set_text('Real Cost (Daily)')
        axes4.set_xlabel('Date')
        axes4.set_ylabel('Kr')
        bl4 = axes4.bar(self.chart_data_overview["dates"], self.chart_data_overview["realcost"])
        axes4.tick_params(rotation=45)
        if len(self.chart_data_overview["dates"]) <= 14:
            for p in bl4:
                height = p.get_height()
                axes4.annotate('{0:.0f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

        # Create subplot 5
        axes5 = figure.add_subplot(335)
        axes5.title.set_text('Real cost vs. average cost (Daily)')
        axes5.set_xlabel('Date')
        axes5.set_ylabel('Kr')
        x = np.asarray(self.chart_data_overview["dates"])
        y = np.asarray(self.chart_data_overview["diffvsaverage"])
        mask1 = y < 0
        mask2 = y >= 0
        
        bl5a = axes5.bar(x[mask1], y[mask1], color="green")
        bl5b = axes5.bar(x[mask2], y[mask2], color="red")
        axes5.tick_params(rotation=45)
        if len(self.chart_data_overview["dates"]) <= 14:
            for p in bl5a:
                height = p.get_height()
                axes5.annotate('{0:.0f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
            for p in bl5b:
                height = p.get_height()
                axes5.annotate('{0:.0f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

        # Create subplot 6
        axes6 = figure.add_subplot(336)
        axes62 = axes6.twinx()  
        axes6.title.set_text('Consumption vs Electrical price (Daily)')
        axes6.set_xlabel('Date')
        axes6.set_ylabel('kWh')
        axes62.set_ylabel('Kr')
        axes62.grid(False)
        bl6a = axes62.plot(self.chart_data_overview["dates"], self.chart_data_overview["avgprice"], color="black")
        bl6b = axes6.bar(self.chart_data_overview["dates"], self.chart_data_overview["consumption"], color="orange")
        axes6.tick_params(rotation=45)
        y_max = 1.0
        if len(self.chart_data_overview["dates"]) <= 14:
            for p in bl6b:
                height = p.get_height()
                axes6.annotate('{0:.0f}'.format(height),
                    xy=(p.get_x() + p.get_width() / 2, height),
                    xytext=(0, 3), # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')

        # Create subplot 7
        axes7 = figure.add_subplot(337)
        axes7.title.set_text('Real cost (Hour)')
        axes7.set_xlabel('Date')
        axes7.set_ylabel('Kr')
        bl7 = axes7.bar(self.chart_data_overview["time_hourly"], self.chart_data_overview["cost_hourly"])
        axes7.tick_params(rotation=45)
        axes7.set_xticks(np.arange(len(self.chart_data_overview["time_hourly"])))
        for p in bl7:
            height = p.get_height()
            axes1.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')


        # Create subplot 8
        axes8 = figure.add_subplot(338)
        axes8.title.set_text('Real cost vs. average cost (Hour)')
        axes8.set_xlabel('Hour')
        axes8.set_ylabel('Kr')
        x = np.asarray(self.chart_data_overview["time_hourly"])
        y = np.asarray(self.chart_data_overview["diffvsaveragehour"])
        mask1 = y < 0
        mask2 = y >= 0
        bl8a = axes8.bar(x[mask1], y[mask1], color="green")
        bl8b = axes8.bar(x[mask2], y[mask2], color="red")
        axes8.tick_params(rotation=45)
        axes8.set_xticks(np.arange(len(self.chart_data_overview["time_hourly"])))
        for p in bl8a:
            height = p.get_height()
            axes8.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')
        for p in bl8b:
            height = p.get_height()
            axes8.annotate('{0:.0f}'.format(height),
                xy=(p.get_x() + p.get_width() / 2, height),
                xytext=(0, 3), # 3 points vertical offset
                textcoords="offset points",
                ha='center', va='bottom')

        # Create subplot 9
        axes9 = figure.add_subplot(339)
        axes92 = axes9.twinx()
        axes9.title.set_text('Consumption vs Electrical price (Hour)')
        axes9.set_xlabel('Hour')
        axes9.set_ylabel('kWh')
        axes92.set_ylabel('Kr')
        axes92.grid(False)
        axes92.plot(self.chart_data_overview["time_hourly"], self.chart_data_overview["avgprice_hourly"], color="black")
        axes9.bar(self.chart_data_overview["time_hourly"], self.chart_data_overview["consumption_hourly"], color="orange")
        axes9.tick_params(rotation=45)
        axes9.set_xticks(np.arange(len(self.chart_data_overview["time_hourly"])))

        # Create annotations
        self.txt = axes1.text(30, 30, "Chart Ready", ha='center', fontsize=36, color='#DD4012')

        # Create a canvas to add to the panel
        canvas = FigureCanvas(self, -1, figure)
        canvas.mpl_connect("motion_notify_event", self.hover)
        
        return canvas

    #------------------------------------------------------------------------------------------
    def create_unit_dict(self, units):
        temp_dict = {}
        for unit in units:
            temp_dict[unit] = []
        return temp_dict

    #------------------------------------------------------------------------------------------
    def filter_dataset_by_date_selection(self, dataset, parent_func):
        # If user has selected start and end date, filter that range
        if self.start_date is not None and self.end_date is not None:
            try:
                dataset_curr_m = dataset[(dataset["timestamp"] >= str(self.start_date)) & (dataset["timestamp"] <= str(self.end_date))]
                return dataset
            except Exception as e:
                logger.error("Failed to slice dataset based on users selection for %s: %s" % (parent_func, e))
                return None
        # If no range selected, filter current month
        else:
            try:
                start_date, end_date = self.calculate_default_date_selection()
            except Exception as e:
                logger.error("Failed to calculate start and end date for filter_dataset and %s: %s" % (parent_func, e))
                start_date, end_date = None, None
            try:
                dataset_curr_m = dataset[(dataset["timestamp"] >= str(start_date)) & (dataset["timestamp"] <= str(end_date))]
                # Check if the dataset is empty or not. If no tibber data exists for current month (like in the beginning),
                # then go for the previous month
                if len(dataset_curr_m) == 0:
                    return dataset
                else:
                    return dataset_curr_m
            except Exception as e:
                logger.error("Failed to slice the dataset for %s: %s" % (parent_func, e))
                return None
           
    #------------------------------------------------------------------------------------------
    def get_min_max_date(self, dataset1, dataset2):
        # Get min and max date from two datasets
        try:
            min_list = []
            max_list = []
            min_list.append(dataset1.index.min())
            max_list.append(dataset1.index.max())
            min_list.append(dataset2.index.min())
            max_list.append(dataset2.index.max())

            # Take largetst min and smallest max
            final_min = max(min_list)
            final_max = min(max_list)

            return [final_min, final_max]
        except Exception as e:
            logger.error("Failed to calculate min and max date: %s" % e)
            return [None, None]

    #------------------------------------------------------------------------------------------
    def hover(self, event):
        self.txt.set_text("")

    #------------------------------------------------------------------------------------------
    def import_tibber_data(self, evt):
        # Import data from Tibber
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tibber_export.main())

        # Update main panel
        self.update_overview()

        # Update parameter showing status
        self.tibber_udpated = True

        # Message user
        wx.MessageBox("Tibber data imported successfully!", "Download successful" ,wx.OK | wx.ICON_INFORMATION)

    #------------------------------------------------------------------------------------------
    def import_tibber_data_csv(self):
        # Import tibber consumption data from csv
        try:
            tibber_data = pd.read_csv("%stibber_consumption.csv" % DATA_PATH)
            tibber_data["date"] = tibber_data["from"].str[:10]
            tibber_data["time"] = tibber_data["from"].str[11:13]
            tibber_data["time_long"] = tibber_data["from"].str[11:19]
            tibber_data["timestamp"] = tibber_data["date"] + " " + tibber_data["time_long"]
            tibber_data["date"] = tibber_data["date"].astype('datetime64[ns]')
            tibber_data["time"] = tibber_data["time"].astype('int64')
            tibber_data["consumption"] = tibber_data["consumption"].astype(np.float16)
            tibber_data["electric_price"] = tibber_data["cost"] / tibber_data["consumption"]
            tibber_data["year_month"] = tibber_data["date"].dt.strftime("%Y%m")
            tibber_data.set_index("date", inplace=True)
            self.timestamp_tibber_data = datetime.strptime(tibber_data["timestamp"].max(), "%Y-%m-%d %H:%M:%S")
            return tibber_data
        except Exception as e:
            logger.error("Failed to import tibber consumption data from csv: %s" % e)

    #------------------------------------------------------------------------------------------
    def import_unit_consumption_data_csv(self):
        # Import unit consumption data from csv
        try:
            unit_consumption = pd.read_csv("%sconsumption.csv" % DATA_PATH)
            unit_consumption["date"] = unit_consumption["datestamp"].str[:10]
            unit_consumption["time"] = unit_consumption["datestamp"].str[11:13]
            unit_consumption["time_long"] = unit_consumption["datestamp"].str[11:19]
            unit_consumption["timestamp"] = unit_consumption["date"] + " " + unit_consumption["time_long"]
            unit_consumption["date"] = unit_consumption["date"].astype('datetime64[ns]')
            unit_consumption = unit_consumption.copy()
            unit_consumption.set_index("date", inplace=True)
            self.timestamp_unit_consumption_data = datetime.strptime(unit_consumption["timestamp"].max(), "%Y-%m-%d %H:%M:%S")
            return unit_consumption
        except Exception as e:
            logger.error("Failed to import unit consumption data from csv: %s" % e)

    #------------------------------------------------------------------------------------------
    def import_unit_data_csv(self):
        # Import unit data from csv
        try:
            unit_data = pd.read_csv("%sunits.csv" % DATA_PATH, delimiter=",")
            unit_data.sort_values(by="id", ascending=True)
            unit_data.set_index("id", inplace=True)
            return unit_data
        except Exception as e:
            logger.error("Failed to import unit data from csv: %s" % e)

    #------------------------------------------------------------------------------------------
    def OnExit(self, evt):
        # Close the main window
        try:
            self.Destroy()
        except Exception as e:
            logger.error("Failed to destroy main window: %s" % e)

    #------------------------------------------------------------------------------------------
    def slice_dataset(self, source, category, data_range):
        # Import Tibber consumption data
        try:
            # Check if newer consumption data exists, if yes, import new data
            temp_date = datetime.now() - timedelta(hours=1)
            if self.timestamp_unit_consumption_data > temp_date:
                self.data_unit_consumption = self.import_unit_consumption_data_csv()
                logger.info("New unit consumption data was imported successfully")

            # Check if tibber data has been updated during this session, if yes, update from csv
            if self.tibber_updated == True:
                self.data_tibber = self.import_tibber_data_csv()
                self.tibber_updated = False
                logger.info("New tibber consumption data was imported successfully")
            
            # If all is selected, import all data. If not, filter after user selection
            if data_range != "all":
                if source == "tibber":
                    tibber_data = self.filter_dataset_by_date_selection(self.data_tibber, "import_tibber_data")
                elif source == "unit_consumption":
                    unit_consumption_data = self.filter_dataset_by_date_selection(self.data_unit_consumption, "import_unit_consumption_data")
            else:
                if source == "tibber":
                    tibber_data = self.data_tibber
                elif source == "unit_consumption":
                    unit_consumption_data = self.data_unit_consumption

            # Import the same time interval as unit consumption data if unit details, else go on with normal dataset
            if category == "unit_details":
                start_date, end_date = self.get_min_max_date(self.data_tibber, self.data_unit_consumption)
                if source == "tibber":
                    tibber_data = tibber_data[(tibber_data["timestamp"] >= str(start_date)) & (tibber_data["timestamp"] <= str(end_date))]
                    return tibber_data
                elif source == "unit_consumption":
                    unit_consumption_data = unit_consumption_data[(unit_consumption_data["timestamp"] >= str(start_date)) & (unit_consumption_data["timestamp"] <= str(end_date))]
                    return unit_consumption_data
            else:
                if source == "tibber":
                    return tibber_data
                elif source == "unit_consumption":
                    return unit_consumption_data
        except Exception as e:
            logger.error("Failed to slice dataset: %s" % e)

    #------------------------------------------------------------------------------------------
    def update_add_unit_form(self):
        # Create form
        add_form = add_unit.CreateForm(self)
        form_panel = add_form.create_panel()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(form_panel, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)

    #------------------------------------------------------------------------------------------
    def update_details(self, unit):
        # Import data
        self.chart_data_details = self.calculate_unit_consumption(unit)

        # Create barchart
        self.canvas1 = self.create_detailed_view()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(self.canvas1, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)

    #------------------------------------------------------------------------------------------
    def update_overview(self):
        # Import data
        self.chart_data_overview = self.calculate_tibber_data()

        # Create barchart
        self.canvas1 = self.create_main_charts()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(self.canvas1, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)

    #------------------------------------------------------------------------------------------
    def update_tibber_details(self):
        # Import data
        self.chart_data_tibber_details = self.calculate_tibber_data()

        # Create barchart
        self.canvas1 = self.create_savings_view()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(self.canvas1, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)

    #------------------------------------------------------------------------------------------
    def update_unit_details(self):
        # Import data
        self.chart_data_unit_details = self.calculate_unit_details()

        # Create barchart
        self.canvas1 = self.create_detailed_unit_view()

        # Clean sizers
        self.clear_sizer(self.visualSizer1)

        # Add charts to sizers
        self.visualSizer1.Add(self.canvas1, 0, wx.EXPAND)

        # Set sizers
        self.SetSizer(self.mainSizer)
