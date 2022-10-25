import logging
import pandas as pd
import wx

# Create logger for imported modules
logger_modules = logging.getLogger("imported_module")
logger_modules.setLevel(logging.ERROR)

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

DATA_PATH = "C:\\Users\\Patrik\\Dropbox\\Patrik\\Home Automation\\Server\\Data\\"

###############################################################################################
class CreateForm():
    def __init__(self, parent):
        self.description = ""
        self.ipadress = ""
        self.parent = parent
        self.panel = wx.Panel(self.parent)
        self.type = ""
        self.unit_name = ""
        self.value = ""

    #------------------------------------------------------------------------------------------
    def create_panel(self):
        # Add sizers
        self.panel.mainSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panel.ctrlSizer = wx.BoxSizer(wx.VERTICAL)

        # Create labels and listctrls
        self.title_add = wx.StaticText(self.panel, label = "Enter information about unit:", style = wx.CENTER)
        self.titleCtrl1 = wx.StaticText(self.panel, label = "Unit name:", style = wx.CENTER)
        self.nameTextCtrl1 = wx.TextCtrl(self.panel, value="", size=(200,20))
        self.titleCtrl2 = wx.StaticText(self.panel, label = "Description:", style = wx.CENTER)
        self.nameTextCtrl2 = wx.ComboBox(self.panel, choices=["Energy Meter", "Thermometer"], size=(200,20))
        self.titleCtrl3 = wx.StaticText(self.panel, label = "IP adress:", style = wx.CENTER)
        self.nameTextCtrl3 = wx.TextCtrl(self.panel, value="", size=(200,20))
        self.titleCtrl4 = wx.StaticText(self.panel, label = "Type:", style = wx.CENTER)
        self.nameTextCtrl4 = wx.ComboBox(self.panel, choices=["Dynamic", "Static"], size=(200,20))
        self.titleCtrl5 = wx.StaticText(self.panel, label = "Value:", style = wx.CENTER)
        self.nameTextCtrl5 = wx.TextCtrl(self.panel, value="", size=(200,20))

        # Add buttons
        self.saveButton = wx.Button(self.panel, label="Save")

        # Handle events
        self.saveButton.Bind(wx.EVT_BUTTON, self.onSave)
        self.nameTextCtrl1.Bind(wx.EVT_TEXT, self.onName)
        self.nameTextCtrl2.Bind(wx.EVT_COMBOBOX, self.onDescription)
        self.nameTextCtrl3.Bind(wx.EVT_TEXT, self.onIP)
        self.nameTextCtrl4.Bind(wx.EVT_COMBOBOX, self.onType)
        self.nameTextCtrl5.Bind(wx.EVT_TEXT, self.onValue)

        # Add content to sizers
        self.panel.titleSizer.Add(self.title_add, 0, wx.CENTER | wx.EXPAND, 50)
        self.panel.titleSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.titleCtrl1, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.nameTextCtrl1, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.titleCtrl2, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.nameTextCtrl2, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.titleCtrl3, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.nameTextCtrl3, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.titleCtrl4, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.nameTextCtrl4, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.titleCtrl5, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.nameTextCtrl5, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.ctrlSizer.Add(self.saveButton, 0, wx.LEFT, 50)
        self.panel.ctrlSizer.AddSpacer(20)
        self.panel.mainSizer.Add(self.panel.titleSizer, 0, wx.ALL|wx.EXPAND, 10)
        self.panel.mainSizer.AddSpacer(10)
        self.panel.mainSizer.Add(self.panel.ctrlSizer, 0, wx.ALL|wx.EXPAND, 10)
        self.panel.mainSizer.AddSpacer(20)
        self.panel.SetSizerAndFit(self.panel.mainSizer)

        return self.panel

    #------------------------------------------------------------------------------------------
    def onDescription(self, event):
        self.description = event.GetString()

    #------------------------------------------------------------------------------------------
    def onIP(self, event):
        self.ipadress = event.GetString()

    #------------------------------------------------------------------------------------------
    def onName(self, event):
        self.unit_name = event.GetString()

    #------------------------------------------------------------------------------------------
    def onType(self, event):
        self.type = event.GetString().lower()

    #------------------------------------------------------------------------------------------
    def onValue(self, event):
        self.value = event.GetString()

    #------------------------------------------------------------------------------------------
    def onSave(self, event):
        # Add unit to CSV
        AddUnit(self.unit_name, self.description, self.ipadress, self.type, self.value)

        # Return to front page
        self.parent.update_overview()


###############################################################################################
class AddUnit():
    def __init__(self, name, desc, ip, unit_type, value):
        # Import current list of units
        self.units = self.import_dataset_from_csv()
        try:
            self.index = self.units.index.tolist()
            self.num_rows = len(self.index)
            self.max_index = max(self.index)
            self.new_index = self.max_index + 1
        except Exception as e:
            logger.info("The dataset failed to import due to: %s" % e)

        # Add new row
        self.add_new_row(name, desc, ip, unit_type, value)

    #------------------------------------------------------------------------------------------
    def add_new_row(self, name, desc, ip_adress, unit_type, value):
        # Add a new row based on user input
        new_row = {"id":self.new_index, "name":name, "description":desc, "ip_adress":ip_adress, 
        "type":unit_type, "value":value}
        self.units = self.units.append(new_row, ignore_index = True)
        self.units.to_csv("%sunits.csv" % DATA_PATH, decimal=".", index=False)

        # Message user
        wx.MessageBox("Unit was added successfully!", "Registration complete" ,wx.OK | wx.ICON_INFORMATION)

    #------------------------------------------------------------------------------------------
    def import_dataset_from_csv(self):
        # Import unit data from csv-file
        units = pd.read_csv("%sunits.csv" % DATA_PATH, delimiter=",")
        return units


