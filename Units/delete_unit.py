import pandas as pd

class DeleteUnit():
    def __init__(self):
        self.units = import_dataset_from_csv()

    #------------------------------------------------------------------------------------------
    def delete_row(self, id):
        pass  

    #------------------------------------------------------------------------------------------
    def import_dataset_from_csv(self):
        # Import unit data from csv-file
        self.units = pd.read_csv("Data\\units.csv")