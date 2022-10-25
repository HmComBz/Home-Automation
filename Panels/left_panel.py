import asyncio
import calendar
import logging
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import threading
import time
from win32api import GetSystemMetrics
import wx
import wx.adv

from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

from Units import add_unit
from Exports.shelly_export import Shelly
from Exports import tibber_export

# Create loggers for code
logger = logging.getLogger("Left Panel")
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

# GLOBAL VARS
x_pos = 0
y_pos = 0
x_size = GetSystemMetrics(0)
y_size = GetSystemMetrics(1)
left_panel_w = 300
DATA_PATH = "C:\\Users\\Patrik\\Dropbox\\Patrik\\Home Automation\\Server\\Data\\"


########################################################################################
class Unit():
    def __init__(self, unit):
        self.datestamp = ""
        self.has_timer = ""
        self.ipadress = unit["ipadress"]
        self.ison = ""
        self.name = unit["name"]
        self.power = ""
        self.type = unit["type"]
        self.unit_id = unit["unit_id"]

        # Get status
        self.get_status()

        # Update data
        self.update()

    #------------------------------------------------------------------------------------------
    def get_status(self):
        # Get current status of unit
        try:
            status = Shelly(self.ipadress).get_settings_plug()
            self.has_timer = status["has_timer"]
            self.ison = status["ison"]
        except Exception as e:
            logger.error("Failed to import unit status for unit %s: %s" % (self.unit_id, e))

    #------------------------------------------------------------------------------------------
    def turn_off(self):
        # Turn unit on
        try:
            Shelly(self.ipadress).turn_plug_off()
        except Exception as e:
            logger.error("Failed to turn unit %s off due to: %s" % (self.unit_id, e))

    #------------------------------------------------------------------------------------------
    def turn_on(self):
        # Turn unit on
        try:
            Shelly(self.ipadress).turn_plug_on()
        except Exception as e:
            logger.error("Failed to turn unit %s on due to: %s" % (self.unit_id, e))

    #------------------------------------------------------------------------------------------
    def update(self):
        try:
            # Update unit with data
            consumption = pd.read_csv("%sconsumption.csv" % DATA_PATH)
            consumption["datestamp"] = consumption["datestamp"].astype('datetime64[ns]')

            # Select latest consumption data
            unit_consumption = consumption.loc[consumption['unit_id'] == self.unit_id]
            if len(unit_consumption) > 0:
                unit_consumption.sort_values(by='datestamp', ascending=True)
                latest_row = unit_consumption.iloc[-1]
                self.power = str(round(latest_row["power"], 2))
                self.datestamp = str(latest_row["datestamp"].strftime("%Y-%m-%d %H:%M:%S"))
            else:
                logger.info("No consumption data exists for unit %s" % self.unit_id)
        except Exception as e:
            logger.error("Failed to update consumption for unit %s: %s" % (self.unit_id, e))
        

########################################################################################
class LeftPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.chart_data = None
        self.default_start, self.default_end = self.calculate_default_date_selection()
        self.list_of_units = self.import_unit_data() # Main list containing unit classes
        self.number_of_units = len(self.list_of_units)
        self.parent = parent
        self.SetBackgroundColour((164, 189, 190))

        # Create box sizers
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.bag_sizer = wx.GridBagSizer(3, 2)
        self.unit_sizer = wx.GridBagSizer(self.number_of_units, 2)
        
        # Populate the panel
        self.create_content("first")

    #------------------------------------------------------------------------------------------
    def clear_sizer(self, sizer):
        # Clear sizer from content
        sizer.Clear(True)

    #------------------------------------------------------------------------------------------
    def create_content(self, status):
        # Create dropdowns for start and end date
        self.title_dates = wx.StaticText(self, label = "Select your date range:", style = wx.ALIGN_CENTRE) 
        self.sDate = wx.adv.GenericDatePickerCtrl(self, size=(120,25),
                                    style = wx.TAB_TRAVERSAL
                                    | wx.adv.DP_DROPDOWN
                                    | wx.adv.DP_SHOWCENTURY
                                    | wx.adv.DP_ALLOWNONE )
        self.sDate.SetValue(self.default_start)
        self.Bind(wx.adv.EVT_DATE_CHANGED, self.get_start_date, self.sDate)

        self.eDate = wx.adv.GenericDatePickerCtrl(self, size=(120,25),
                                    style = wx.TAB_TRAVERSAL
                                    | wx.adv.DP_DROPDOWN
                                    | wx.adv.DP_SHOWCENTURY
                                    | wx.adv.DP_ALLOWNONE )
        self.eDate.SetValue(self.default_end)
        self.Bind(wx.adv.EVT_DATE_CHANGED, self.get_end_date, self.eDate)

        # Add unit sizers
        self.title_buttons = wx.StaticText(self, label = "List of units", style = wx.ALIGN_CENTRE)

        # Add things go GridBoxSizer
        self.title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.title_sizer.Add(self.title_dates, 0, wx.ALL, 15)
        self.bag_sizer.Add(self.title_sizer, flag=wx.EXPAND, pos=(1,0), span=(1,2))
        self.bag_sizer.Add(self.sDate, flag=wx.ALL, pos=(2,0), border=5)
        self.bag_sizer.Add(self.eDate, flag=wx.ALL, pos=(2,1), border=5)
        self.bag_sizer.Add(self.title_buttons, flag=wx.EXPAND, pos=(3,0), span=(1,2))

        # Loop to create all unit panels
        self.temp_list = []
        for i in range(0, self.number_of_units):
            self.unit_sizer.Add(self.create_unit_boxes(self.list_of_units[i]), flag=wx.EXPAND, pos=(1+i,0), border=15)

        # Add all sizers to the main sizer
        try:
            if status == "first":
                self.bag_sizer.AddGrowableCol(0)
                self.bag_sizer.AddGrowableCol(1)
                self.main_sizer.Add(self.bag_sizer, 0, wx.CENTER)
                self.main_sizer.Add(wx.StaticLine(self), 0, wx.ALL|wx.EXPAND, 5)
                self.main_sizer.Add(self.unit_sizer, 0, wx.CENTER)
            self.SetSizerAndFit(self.main_sizer)
            self.main_sizer.Fit(self)
        except Exception as e:
            logger.error("Error while adding growable columns: %s" % e)

    #------------------------------------------------------------------------------------------
    def calculate_default_date_selection(self):
        # Calculate default date based on current month
        first_date_this_m = datetime.today().replace(day=1)
        last_day_this_m = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
        last_date_this_m = datetime(year=datetime.now().year, month=datetime.now().month, day=last_day_this_m)
        return first_date_this_m, last_date_this_m

    #------------------------------------------------------------------------------------------
    def create_unit_boxes(self, unit):
        # Create boxes for units
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        content_left_sizer = wx.BoxSizer(wx.VERTICAL)
        content_right_sizer = wx.BoxSizer(wx.VERTICAL)
        content_right_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create a sizer for a specific unit
        unit_title = unit.name + " - " + unit.type
        title = wx.StaticText(self, label = unit_title, style = wx.ALIGN_LEFT, size=(left_panel_w-100,20))
        ip = wx.StaticText(self, label = unit.ipadress, style = wx.ALIGN_RIGHT, size=(80,20))

        # Create buttons
        btn1 = wx.Button(self, label="On", size=(40,30))
        btn2 = wx.Button(self, label="Off", size=(40,30))
        if unit.ison == True:
            btn1.SetBackgroundColour((255, 255, 255))
        else:
            btn2.SetBackgroundColour((255, 255, 255))  
        btn3 = wx.Button(self, label="Details", size=(80,30))
        
        btn1.Bind(wx.EVT_BUTTON, lambda event: self.turn_on(event, unit.unit_id))
        btn2.Bind(wx.EVT_BUTTON, lambda event: self.turn_off(event, unit.unit_id))
        btn3.Bind(wx.EVT_BUTTON, lambda event: self.details(event, unit.unit_id))

        # Create labels
        value = wx.StaticText(self, label = unit.power, style = wx.ALIGN_LEFT, size=(200,40))
        font = wx.Font(18, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        value.SetFont(font)
        datetime = wx.StaticText(self, label = unit.datestamp, style = wx.ALIGN_LEFT, size=(200,20))

        # Add content to sizers
        title_sizer.Add(title, 0, wx.LEFT, 10)
        title_sizer.Add(ip, 0, wx.RIGHT, 10)
        content_left_sizer.Add(value, 0, wx.LEFT, 20)
        content_left_sizer.Add(datetime, 0, wx.LEFT, 20)
        content_right_btn_sizer.Add(btn1, 0, wx.RIGHT, 0)
        content_right_btn_sizer.Add(btn2, 0, wx.RIGHT, 0)
        content_right_sizer.Add(content_right_btn_sizer, 0, wx.RIGHT, 20)
        content_right_sizer.Add(btn3, 0, wx.RIGHT, 20)
        content_sizer.Add(content_left_sizer, 0, wx.LEFT, 0)
        content_sizer.Add(content_right_sizer, 0, wx.LEFT, 0)
        main_sizer.Add(title_sizer, 0, wx.EXPAND, 0)
        main_sizer.Add(content_sizer, 0, wx.EXPAND, 0)
        return main_sizer

    #-------------------------------------------------------------------------------------------
    def details(self, evt, unit):
        # Clear the canvas on the main panel
        self.parent.main_panel.clear_sizer(self.parent.main_panel.visualSizer1)

        # Add new canvas with detailed graphs
        self.parent.main_panel.update_details(unit)

    #-------------------------------------------------------------------------------------------
    def get_start_date(self, event):
        # Get the selected start date from the drop down
        self.selected_date = event.GetDate()
        self.formatted_date = self.selected_date.Format("%a %b %d %H:%M:%S %Y")
        self.start_date = datetime.strptime(self.formatted_date, "%a %b %d %H:%M:%S %Y").date()
        self.parent.main_panel.start_date = str(self.start_date)

        # Update data
        self.parent.main_panel.update_overview()        

    #-------------------------------------------------------------------------------------------
    def get_end_date(self, event):
        # Get the selected end date from the drop down
        self.selected_date = event.GetDate()
        self.formatted_date = self.selected_date.Format("%a %b %d %H:%M:%S %Y")
        self.end_date = datetime.strptime(self.formatted_date, "%a %b %d %H:%M:%S %Y").date()
        self.parent.main_panel.end_date = str(self.end_date)

        # Update data
        self.parent.main_panel.update_overview()

    #------------------------------------------------------------------------------------------
    def import_unit_data(self):
        # Import units
        units = pd.read_csv("%sunits.csv" % DATA_PATH, delimiter=",")
        unit_dict = {}
        for index, row in units.iterrows():
            temp_dict = {"unit_id":row[0], "name":row[1], "type":row[2], "ipadress":row[3]}
            unit_dict[row[0]] = Unit(temp_dict)
        logger.info("Unit data successfully imported")
        return unit_dict

    #------------------------------------------------------------------------------------------
    def turn_off(self, evt, unit_id):
        # Turn unit on
        self.list_of_units[unit_id].turn_off()

        # Update panel
        self.update()

    #------------------------------------------------------------------------------------------
    def turn_on(self, evt, unit_id):
        # Turn unit on
        self.list_of_units[unit_id].turn_on()

        # Update panel
        self.update()

    #------------------------------------------------------------------------------------------
    def update(self):
        # Clear panel
        self.clear_sizer(self.unit_sizer)
        self.clear_sizer(self.bag_sizer)

        # Set sizers
        self.SetSizerAndFit(self.main_sizer)
        
        # Create new content
        self.create_content("update")

        # Set sizers
        self.SetSizerAndFit(self.main_sizer)

