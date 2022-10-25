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
logger = logging.getLogger("Top Panel")
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


class TopPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.SetBackgroundColour((115, 144, 134))
        #self.SetBackgroundColour((216, 216, 214))

        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn1 = wx.Button(self, label="Overview", size=(80,30))
        self.btn2 = wx.Button(self, label="Savings", size=(80,30))
        self.btn3 = wx.Button(self, label="Unit Overview", size=(80,30))
        self.btn1.Bind(wx.EVT_BUTTON, self.show_overview)
        self.btn2.Bind(wx.EVT_BUTTON, self.show_tibber_details)
        self.btn3.Bind(wx.EVT_BUTTON, self.show_unit_overview)

        # Add buttons to sizer
        self.main_sizer.Add(self.btn1, 0, wx.ALL | wx.EXPAND, 5)
        self.main_sizer.Add(self.btn2, 0, wx.ALL | wx.EXPAND, 5)
        self.main_sizer.Add(self.btn3, 0, wx.ALL | wx.EXPAND, 5)
        self.SetSizerAndFit(self.main_sizer)

    #-------------------------------------------------------------------------------------------------
    def show_overview(self, evt):
        # Show overview at the main panel
        self.parent.main_panel.update_overview()

    #-------------------------------------------------------------------------------------------------
    def show_tibber_details(self, evt):
        # Show overview at the main panel
        self.parent.main_panel.update_tibber_details()

    #-------------------------------------------------------------------------------------------------
    def show_unit_overview(self, evt):
        # Show overview at the main panel
        self.parent.main_panel.update_unit_details()