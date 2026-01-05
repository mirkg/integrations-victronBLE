#!/usr/bin/env python3

import asyncio
import inspect
import logging
import json
import subprocess
import urllib
import time
import threading
import atexit

from typing import Set
from enum import Enum

from flask import Flask, Response, jsonify
from flask_httpauth import HTTPBasicAuth

from bleak.backends.device import BLEDevice
from victron_ble.scanner import BaseScanner
from victron_ble.devices import Device, DeviceData, detect_device_type
from victron_ble.exceptions import AdvertisementKeyMissingError, UnknownDeviceError


app = Flask(__name__)
auth = HTTPBasicAuth()
users = {}

scrape_timer = threading.Timer(0, lambda x: None, ())

RUNNIG = True
DEVICES: Set[str] = set()
WAIT_FOR_DEVICS = 3
RESTART_SCANER_SECONDS = 600
DEVICES_DATA = {}
VICTRON_KEYS = {}

class DeviceDataEncoder(json.JSONEncoder):
    def default(self, obj):
        if issubclass(obj.__class__, DeviceData):
            data = {}
            for name, method in inspect.getmembers(obj, predicate=inspect.ismethod):
                if name.startswith("get_"):
                    value = method()
                    if isinstance(value, Enum):
                        value = value.name.lower()
                    if value is not None:
                        data[name[4:]] = value
            return data

class DiscoveryScanner(BaseScanner):
    def __init__(self) -> None:
        super().__init__()
        self.scanning = asyncio.Event()

    def callback(self, device: BLEDevice, advertisement: bytes):
        if device.address not in DEVICES:
            app.logger.info(f"{device}")
            DEVICES.add(device.address)
    
    async def run(self):
        await self.start()
        self.scanning.set()
        while self.scanning.is_set():
            if len(DEVICES) >= WAIT_FOR_DEVICS:
                self.scanning.clear()
            await asyncio.sleep(0.1)
        await self.stop()      
    
class Scanner(BaseScanner):
    def __init__(self, devices: Set[str] = set(), keys = {}, indent=2):
        super().__init__()
        self._scanning = asyncio.Event()
        self._devices = devices
        self._keys = keys
        self._known_devices: dict[str, Device] = {}
        self._indent = indent
        self._started = time.time()

    async def start(self):
        app.logger.info(f"Reading data for {self._devices}")
        await super().start()

    async def run(self):
        await self.start()
        self._scanning.set()
        while self._scanning.is_set():
            if self._started + RESTART_SCANER_SECONDS < time.time():
                self._scanning.clear()
            await asyncio.sleep(1)
        await self.stop()      

    def get_device(self, ble_device: BLEDevice, raw_data: bytes) -> Device:
        address = ble_device.address
        if address not in self._known_devices:
            device_klass = detect_device_type(raw_data)
            if not device_klass:
                raise UnknownDeviceError(
                    f"Could not identify device type for {ble_device}"
                )
            app.logger.info(f"get device {ble_device} {device_klass}")

            advertisement_key = self.load_key(address)
            
            self._known_devices[address] = device_klass(advertisement_key)
        return self._known_devices[address]

    def load_key(self, address: str) -> str:
        try:
            return self._keys[address]
        except KeyError:
            raise AdvertisementKeyMissingError(f"No key available for {address}")

    def callback(self, ble_device: BLEDevice, raw_data: bytes):
        app.logger.debug(f"Received data from {ble_device.address}bb {raw_data.hex()}")
        try:
            device = self.get_device(ble_device, raw_data)
        except AdvertisementKeyMissingError as e:
            app.logger.error(str(e))
            return
        except UnknownDeviceError as e:
            app.logger.error(e)
            return
        parsed = device.parse(raw_data)

        blob = {
            "name": ble_device.name,
            "address": ble_device.address,
            "payload": parsed,
        }
        app.logger.debug(json.dumps(blob, cls=DeviceDataEncoder, indent=self._indent))
        DEVICES_DATA[ble_device.name] = parsed


def discover():
    app.logger.info("discover")    
    loop = asyncio.get_event_loop()
    scanner = DiscoveryScanner()
    loop.run_until_complete(scanner.run())
    scanner = None

def read():
    app.logger.info("read") 
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while RUNNIG:
        scanner = Scanner(VICTRON_KEYS.keys(), VICTRON_KEYS, indent=None)        
        loop.run_until_complete(scanner.run())
        scanner = None

def configure():
    with open('users.txt') as file:
        for line in file:
            if line[0] != '#':
                users[line.strip().split(' ')[0]] = line.strip().split(' ')[1]
    app.logger.error(users.keys())
    app.logger.error("conf VICTRON_KEYS: " + str(VICTRON_KEYS))


@auth.verify_password
def verify_password(username, password):
    if username in users and users.get(username) == password:
        return username

@app.route("/")
def hello():
    return jsonify({'resp': 'hello :)'})

@app.route("/devices")
@auth.login_required
def getdevicesstatus():
    try:
        points = {
            'time': int(time.time()),
            "data": DEVICES_DATA
        }
        return Response(json.dumps(points, cls=DeviceDataEncoder), mimetype='application/json')
    except Exception as ex:
        app.logger.error('failed: status with output=[' + str(ex) + ']')
        exec_action('sendnotification', ['growatt_status_failed', urllib.parse.quote_plus(str(ex))])
        return jsonify({'resp': 'status failed', 'error': str(ex)})

def exec_action(action, args):
    try:
        cmd = '/home/pi/servers/victron/actions/' + action + '.sh'
        for arg in args:    
            cmd += ' ' + arg
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        app.logger.info('executed: ' + action + ' with output=[' + str(output) + ']')
    except subprocess.CalledProcessError as ex:
        app.logger.error('failed: ' + action +  ' with output=[' + str(ex.output) + ']')

def backgroud_thread_start():
    global scrape_timer
    scrape_timer = threading.Timer(1, read, ())
    scrape_timer.start()  

def on_exit():
    global scrape_timer
    RUNNIG = False
    scrape_timer.cancel()

if __name__ == "__main__":
    configure()
    #discover()
    backgroud_thread_start()
    atexit.register(on_exit)
    app.run(host='0.0.0.0')
else:
    configure()
    #discover()
    backgroud_thread_start()
    atexit.register(on_exit)
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
