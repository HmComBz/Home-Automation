import pandas as pd

DATA_PATH = "Data\\"

def clean_consumption(dataframe):
    # Clean consumption data from bad data
    dataframe.loc[dataframe["last_period"] < 0, "last_period"] = 0
    return dataframe

def import_data():
    # Import unit consumption data from csv
    data = pd.read_csv("%sconsumption.csv" % DATA_PATH)
    return data

def save_data(data):
    # Save data
    data.to_csv("%sconsumption.csv" % DATA_PATH, decimal=".", index=False)

data = import_data()
clean_data = clean_consumption(data)
save_data(clean_data)


