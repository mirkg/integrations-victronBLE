# Victron BLE

## Overview

**victronBLE** exposes API to get config and values exposed via Victron devices supporting BLE.

As hardware I use RaspberryPi Zero2W and connect to Victron devices via Bluetooth.

Http server is implemented in python using Flask and accessing inverter via victron BLE module.

### Tested devices

  - Victron Smart Battery Protect
  - Vixtron Smart Solar

## Run

### Fetching Keys

1. Install the VictronConnect app
2. Open the app and pair with your device
3. Locate the device that you want to monitor in the list shown by the app and click on it.
4. Click on the gear icon to open the Settings for that device.
5. Open the menu and select Product Info.
6. Scroll down to Instant Readout via Bluetooth and enable the feature if it is not already enabled.
7. Click the Show button next to Instant Readout Details to display the encryption keys.
8. Copy the MAC address and advertisement key

### Prepare

Install python libraries: 
```
pip install wheel gunicorn flask flask_httpauth bleak click pycryptodome
```

Pair your devices:
```
bluetoothctl

scan on
devices
pair
exit
```

Add victron_ble folder to your python libraries.
  
Add your paired devices to 'VICTRON_KEYS' in this format
```
VICTRON_KEYS = {'XX:XX:XX:XX:XX:XX': '00000000000000000000000000000000'}
```

Create **actions** folder with **sendnotification.sh** script to handle errors form server.
Example for Domoticz:
```
/usr/bin/curl -H 'Authorization: Basic XXX' "http://192.168.1.100/json.htm?type=command&param=sendnotification&subject=$1&body=$2"
```

Example to run with gunicorn:

wsgi.py
```
from victron import app

if __name__ == "__main__":
    app.run()
```

gunicorn.conf.py
```
bind = '0.0.0.0:${SERVER_PORT}'
workers = 1
loglevel = 'debug'
accesslog = './logs/access.log'
errorlog = './logs/error.log'
capture_output = True
```

### Run
Test run with 
```
gunicorn wsgi:app
```

## API Reference

| method | path | Description | payload |
|----------|------------|------------|------------|
| GET | /devices | Get devices data |  |

Example output
```
{
  "time": 1767598857,
  "data": {
    "SmartSolar HQ2134QCUXH": {
      "battery_charging_current": 10.8,
      "battery_voltage": 12.67,
      "charge_state": "bulk",
      "charger_error": "no_error",
      "model_name": "SmartSolar Charger MPPT 100/50",
      "solar_power": 143,
      "yield_today": 70
    },
    "BatteryProtect HQ21297H6KM": {
      "alarm_reason": "no_alarm",
      "device_state": "active",
      "error_code": "no_error",
      "input_voltage": 12.57,
      "model_name": "Smart BatteryProtect 12/24V-100A",
      "off_reason": "no_reason",
      "output_state": "on",
      "output_voltage": 12.57,
      "warning_reason": "no_alarm"
    },
    "BatteryProtect HQ2140XMYRA": {
      "alarm_reason": "no_alarm",
      "device_state": "active",
      "error_code": "no_error",
      "input_voltage": 13.25,
      "model_name": "Smart BatteryProtect 12/24V-65A",
      "off_reason": "no_reason",
      "output_state": "on",
      "output_voltage": 13.25,
      "warning_reason": "no_alarm"
    }
  }
}
```

## License

This project is licensed under the **MIT License**. Feel free to use it and modify it on your own fork.

## Contributing

Pull requests with fixes are welcome! New functionalities and extensions will be not discussed in this repository.
