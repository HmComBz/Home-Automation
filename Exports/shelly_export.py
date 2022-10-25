# importing the requests library
import logging
import requests

# Documentation: https://shelly-api-docs.shelly.cloud/gen1/?shell#shelly-plug-plugs-meter-0

# Create loggers for code
logger = logging.getLogger("Shelly")
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
  
  
class Shelly():
    def __init__(self, ip):
        self.ip = ip

    def get_data(self, url):
        # Get data from HTML GET request
        try:
            r = requests.get(url = url, headers={"content-type":"application/x-www-form-urlencoded"}, timeout=5)
            return r
        except requests.exceptions.HTTPError as errh:
            logger.error("GET Request for %s failed: %s" % (self.ip, errh))
            return None
        except requests.exceptions.ConnectionError as errc:
            logger.error("GET Request for %s failed: %s" % (self.ip, errc))
            return None
        except requests.exceptions.Timeout as errt:
            logger.error("GET Request for %s failed: %s" % (self.ip, errt))
            return None
        except requests.exceptions.RequestException as err:
            logger.error("GET Request for %s failed: %s" % (self.ip, err))
            return None

    def get_settings_plug(self):
        # Get settings from smart plug s
        url = "http://%s/relay/0" % self.ip
        d = self.get_data(url)
        return d.json()

    def get_status_plug(self):
        # Get status from smart plug s
        url = "http://%s/meter/0" % self.ip
        d = self.get_data(url)
        return d.json()

    def post_data(self, url, parameters):
        # Post data from HTML POST request
        r = requests.post(url = url, params = parameters, headers={"content-type":"application/x-www-form-urlencoded"}, timeout=5)
        return r    

    def turn_plug_off(self):
        # Turn smart plug s off
        url = "http://%s/relay/0" % self.ip
        self.post_data(url, {"turn":"off"})

    def turn_plug_on(self):
        # Turn smart plug s on
        url = "http://%s/relay/0" % self.ip
        self.post_data(url, {"turn":"on"})

    
    
