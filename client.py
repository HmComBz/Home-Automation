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
from Panels.main_panel import MainPanel
from Panels.top_panel import TopPanel
from Panels.left_panel import LeftPanel

# Create loggers for code
logger = logging.getLogger("Main")
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


######################################################################################################
class MainFrame(wx.Frame):
    def __init__(self):

        """Constructor"""
        wx.Frame.__init__(self, None, title="Panels", pos=(x_pos, y_pos), size=(x_size, y_size))

        # Initiate GUI
        self.panel_root = self.initUI()

        # Create main menu
        self.menu1 = wx.Menu()
        self.menu1.Append(1,'&Update')
        self.menu1.AppendSeparator()
        self.menu1.Append(2,'E&xit')
        self.menu2 = wx.Menu()
        self.menu2.Append(3, 'Add unit')
        self.menu2.AppendSeparator()
        self.menu2.Append(4, 'Edit unit')
        self.menu3 = wx.Menu()
        self.menu3.Append(6, 'Profile')
        self.menu3.AppendSeparator()
        self.menu3.Append(7, 'Settings')
        self.menuBar = wx.MenuBar()
        self.menuBar.Append(self.menu1,'&File')
        self.menuBar.Append(self.menu2,'&Units')
        self.menuBar.Append(self.menu3,'&Settings')
        self.Bind(wx.EVT_MENU, self.panel_root.main_panel.import_tibber_data, id=1)
        self.Bind(wx.EVT_MENU, self.OnExit, id=2)
        self.Bind(wx.EVT_MENU, self.add_unit, id=3)
        self.Bind(wx.EVT_MENU, self.OnExit, id=4)
        self.SetMenuBar(self.menuBar)
        self.Layout()

    #----------------------------------------------------------------------
    def add_unit(self, evt):
        # Add a new unit
        self.panel_root.main_panel.update_add_unit_form()

    #----------------------------------------------------------------------
    def initUI(self):
        # Create the root panel containing all panels
        return Panel_root(self)

    #----------------------------------------------------------------------
    def OnExit(self, evt):
        # Close window
        self.Destroy()


######################################################################################################
class Panel_root(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, size=(y_size, 100))
        self.left_panel = LeftPanel(self)
        self.top_panel = TopPanel(self)
        self.main_panel = MainPanel(self)

        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(self.top_panel, 1, wx.EXPAND)
        s.Add(self.main_panel, 1, wx.EXPAND)

        root_sizer = wx.BoxSizer(wx.HORIZONTAL)
        root_sizer.Add(self.left_panel, 1, wx.EXPAND)
        root_sizer.Add(s, 3, wx.EXPAND)
        self.SetSizer(root_sizer)

        self.Bind(wx.EVT_BUTTON, self.onclic)

    #-------------------------------------------------------------------------------------------------
    def onclic(self, e):
        origin = e.GetEventObject().GetName()
        if origin == 'first button':
            self.top_panel.update('hello') # note that we use an API...
        elif origin == 'second button':
            self.main_panel.update('hello') # ...to avoid direct access


if __name__ == "__main__":
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()

