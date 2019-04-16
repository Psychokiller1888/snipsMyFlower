#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from Chirp import Chirp
import json
from Leds import Leds
import logging
import os
import paho.mqtt.client as mqtt
import pytoml
import RPi.GPIO as gpio
import sys
import threading
import time

class Flower:

	""" gpio.BCM #gpio.Board pin numbers"""
	_WATER_SENSOR_PIN = 23 #16
	_WATER_EMPTY_PIN = 5 #29
	_WATER_25_PIN = 25 #22
	_WATER_50_PIN = 8 #24
	_WATER_75_PIN = 7 #26
	_WATER_FULL_PIN = 16 #36

	_PUMP_PIN = 26 #37

	_MQTT_DO_WATER = 'snipsmyflower/flowers/doWater'
	_MQTT_GET_TELEMETRY = 'snipsmyflower/flowers/getTelemetry'
	_MQTT_TELEMETRY_REPORT = 'snipsmyflower/flowers/telemetryData'
	_MQTT_PLANT_ALERT = 'snipsmyflower/flowers/alert'

	def __init__(self):
		"""
		Initiliazes the flower instance
		Tries to connect to master mqtt, gets its site id, loads itself and starts the 5 minute monitoring thread
		It also tells the master device that it is connected
		"""
		self._logger = logging.getLogger('SnipsMyFlower')
		gpio.setmode(gpio.BCM)
		gpio.setwarnings(False)
		gpio.setup(self._PUMP_PIN, gpio.OUT)
		gpio.setup(self._WATER_SENSOR_PIN, gpio.OUT)
		gpio.setup(self._WATER_EMPTY_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_25_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_50_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_75_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_FULL_PIN, gpio.IN, gpio.PUD_DOWN)

		self._mqtt = None
		self._snipsConf = self._loadSnipsConfiguration()
		if self._snipsConf is None:
			self._logger.error('snips-audio-server not installed, stopping')
			sys.exit()

		if 'snips-common' not in self._snipsConf or 'mqtt' not in self._snipsConf['snips-common']:
			self._logger.error("Snips satellite is not configured. Please edit /etc/snips.toml and configure ['snips-common']['mqtt'] and try to start me again")
			sys.exit()
		else:
			self._mqtt = self._connectMqtt()
			if not self._mqtt:
				self._logger.error("Couldn't connect to mqtt broker")
				sys.exit()

		self._siteId = self._getSiteId()
		if not self._siteId:
			self._logger.error("Couldnt' get my site id, please edit /etc/snips.toml and configure ['snips-audio-server']['bind']")
			sys.exit()

		self._me = {'type': 'cactus'}
		self._moistureSensor = Chirp(address=0x20,
                  read_moist=True,
                  read_temp=True,
                  read_light=True,
                  min_moist=214,
                  max_moist=625,
                  temp_scale='celsius',
                  temp_offset=-5.5)
		self._leds = Leds()
		self._leds.onStart()
		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._monitoring = None
		self._onFiveMinute()


	def _connectMqtt(self):
		"""
		Connects to master mqtt as defined in snips.toml
		:return:
		"""
		try:
			mqttClient = mqtt.Client()
			mqttClient.on_connect = self._onConnect
			mqttClient.on_message = self._onMessage
			mqttClient.connect(self._snipsConf['snips-common']['mqtt'].split(':')[0], int(self._snipsConf['snips-common']['mqtt'].split(':')[1]))
			mqttClient.loop_start()
			return mqttClient
		except:
			return False


	def _loadSnipsConfiguration(self):
		"""
		Loads snips configuration file
		:return:
		"""
		self._logger.info('Loading configurations')

		if os.path.isfile('/etc/snips.toml'):
			with open('/etc/snips.toml') as confFile:
				return pytoml.load(confFile)
		else:
			return None


	def _getSiteId(self):
		"""
		Gets the site id as defined in snips.toml
		:return: string
		"""
		if 'bind' in self._snipsConf['snips-audio-server']:
			if ':' in self._snipsConf['snips-audio-server']['bind']:
				return self._snipsConf['snips-audio-server']['bind'].split(':')[0]
			elif '@' in self._snipsConf['snips-audio-server']['bind']:
				return self._snipsConf['snips-audio-server']['bind'].split('@')[0]
		return False


	def _loadFlower(self):
		"""
		Loads the flower informations
		:return: boolean
		"""
		if os.path.isfile('me.json'):
			with open('me.json', 'w+') as f:
				data = f.read()
				self._me = json.loads(data)
			return True
		else:
			return False


	def onStop(self):
		"""
		Called when the program goes down. Joins the threads and cleans up the gpios
		:return:
		"""
		if self._watering.isAlive():
			self._watering.cancel()
			self._watering.join(timeout=2)

		if self._monitoring.isAlive():
			self._monitoring.cancel()
			self._monitoring.join(timeout=2)

		self._leds.onStop()
		gpio.cleanup()


	def _onConnect(self, client, userdata, flags, rc):
		"""
		Called when mqtt connects. Does subscribe to all our intents
		"""
		self._mqtt.subscribe([
			(self._MQTT_GET_TELEMETRY, 0),
			(self._MQTT_DO_WATER, 0),
			(self._MQTT_PLANT_ALERT, 0)
		])


	def _onMessage(self, client, userdata, message):
		"""
		Called whenever a message we are subscribed to enters
		"""
		try:
			payload = json.loads(message.payload.decode('utf-8'))
		except:
			payload = dict()

		if 'siteId' not in payload or payload['siteId'] != self._siteId:
			return

		topic = message.topic

		if topic == self._MQTT_DO_WATER:
			self.doWater()
		elif topic == self._MQTT_PLANT_ALERT:
			print('alert')


	def doWater(self):
		"""
		Turns the internal pump on and starts a 5 second timer to turn it off again
		"""
		if self._watering.isAlive():
			return

		self._pump()
		self._watering = threading.Timer(interval=3.0, function=self._pump, args=[False])
		self._watering.setDaemon(True)
		self._watering.start()


	def _onFiveMinute(self):
		"""
		Called every 5 minutes, this method does ask for the latest sensor data and sends them to the main unit
		It also runs checks on the data to alert the user if needed
		"""
		self._monitoring = threading.Timer(interval=300, function=self._onFiveMinute)
		self._monitoring.setDaemon(True)
		self._monitoring.start()

		data = self._queryTelemetryData()
		self._mqtt.publish(topic=self._MQTT_TELEMETRY_REPORT, payload=json.dumps({
			'siteId': self._siteId,
			'plant': self._me['type'],
			'data': data
		}))


	def _pump(self, on=True):
		"""
		Turn pump on or off
		:param on: boolean
		"""
		if on:
			gpio.output(self._PUMP_PIN, gpio.HIGH)
		else:
			gpio.output(self._PUMP_PIN, gpio.LOW)


	def _queryTelemetryData(self):
		"""
		Gets and returns all sensors data
		:return: dict
		"""
		data = dict()
		try: # Chirp sometimes crashes, in which case we simply recall the telemetry query
			self._moistureSensor.wake_up()
			self._moistureSensor.trigger()
			time.sleep(1)
			moisture = self._moistureSensor.moist_percent
			light = self._moistureSensor.light
			temperature = self._moistureSensor.temp
			self._moistureSensor.sleep()
			print('Moisture: {}% temperature: {:.1f}°C light: {} lux'.format(moisture, temperature, light))
			if moisture > 100 or moisture < 0 or temperature > 100:
				raise Exception('Impossible chirp sensor values')
			else:
				data['temperature'] = temperature
				data['luminosity'] = light
				data['moisture'] = moisture
		except Exception as e:
			self._logger.error(e)
			self._queryTelemetryData()

		gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
		if gpio.input(self._WATER_FULL_PIN):
			data['water'] = 100
		elif gpio.input(self._WATER_75_PIN):
			data['water'] = 75
		elif gpio.input(self._WATER_50_PIN):
			data['water'] = 50
		elif gpio.input(self._WATER_25_PIN):
			data['water'] = 25
		elif gpio.input(self._WATER_EMPTY_PIN):
			data['water'] = 0
		else:
			data['water'] = -1
		gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)
		return data
