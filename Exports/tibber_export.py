import asyncio
import os
import tibber
import pandas as pd

DATA_PATH = "C:\\Users\\Patrik\\Dropbox\\Patrik\\Home Automation\\Server\\Data\\"


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
        consumption.to_csv("%stibber_consumption.csv" % DATA_PATH, decimal=".")

    await tibber_connection.close_connection()


if __name__ ==  '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())