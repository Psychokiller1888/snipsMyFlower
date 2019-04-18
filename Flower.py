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
	_WATER_50_PIN = 27 #13
	_WATER_75_PIN = 22 #15
	_WATER_FULL_PIN = 16 #36

	_PUMP_PIN = 26 #37

	_MQTT_DO_WATER = 'snipsmyflower/flowers/doWater'
	_MQTT_GET_TELEMETRY = 'snipsmyflower/flowers/getTelemetry'
	_MQTT_TELEMETRY_REPORT = 'snipsmyflower/flowers/telemetryData'
	_MQTT_PLANT_ALERT = 'snipsmyflower/flowers/alert'
	_MQTT_REFILL_MODE = 'snipsmyflower/flowers/refillMode'
	_MQTT_REFILL_FULL = 'snipsmyflower/flowers/refillFull'
	_MQTT_EMPTY_WATER = 'snipsmyflower/flowers/emptyWater'
	_MQTT_WATER_EMPTIED = 'snipsmyflower/flowers/waterEmptied'

	_MQTT_REFUSED = 'snipsmyflower/flowers/refused'

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
                    temp_offset=-0.5)
		self._leds = Leds()
		self._leds.onStart()
		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._monitoring = None
		self._refilling = None
		self._emptying = None
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

		if self._refilling is not None and self._refilling.isAlive():
			self._refilling.join(timeout=2)

		if self._emptying is not None and self._emptying.isAlive():
			self._emptying.join(timeout=2)

		self._leds.onStop()
		gpio.cleanup()


	def _onConnect(self, client, userdata, flags, rc):
		"""
		Called when mqtt connects. Does subscribe to all our intents
		"""
		self._mqtt.subscribe([
			(self._MQTT_GET_TELEMETRY, 0),
			(self._MQTT_DO_WATER, 0),
			(self._MQTT_PLANT_ALERT, 0),
			(self._MQTT_REFILL_MODE, 0),
			(self._MQTT_EMPTY_WATER, 0)
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
			self._doWater()
		elif topic == self._MQTT_PLANT_ALERT:
			#print('alert of type: {} on {}'.format(payload['telemetry'], payload['limit']))
			self._onAlert(payload['telemetry'], payload['limit'])
		elif topic == self._MQTT_REFILL_MODE:
			if self._emptying is not None and self._emptying.isAlive() or self._watering.isAlive():
				self._mqtt.publish(topic=self._MQTT_REFUSED, payload=json.dumps({'siteId': self._siteId}))
				return

			self._refilling = threading.Thread(target=self._refillingMode)
			self._refilling.setDaemon(True)
			self._refilling.start()
		elif topic == self._MQTT_EMPTY_WATER:
			if self._refilling is not None and self._refilling.isAlive() or self._watering.isAlive():
				self._mqtt.publish(topic=self._MQTT_REFUSED, payload=json.dumps({'siteId': self._siteId}))
				return

			self._emptying = threading.Thread(target=self._emptyingMode)
			self._emptying.setDaemon(True)
			self._emptying.start()


	def _doWater(self):
		"""
		Turns the internal pump on and starts a 5 second timer to turn it off again
		"""
		if self._watering.isAlive():
			return

		self._pump()
		self._watering = threading.Timer(interval=3.0, function=self._pump, args=[False])
		self._watering.setDaemon(True)
		self._watering.start()


	def _refillingMode(self):
		"""
		User asked for tank refilling. We need to update the led indicator according to water level
		and to alert the user when the level is full which will stop the refilling mode
		"""
		self._leds.clear()
		gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
		refilling = True
		was = 0
		while refilling:
			if gpio.input(self._WATER_FULL_PIN):
				if was != 100:
					print(100)
					was = 100
					self._leds.onDisplayLevel(5, [0, 0, 255])
					self._mqtt.publish(topic=self._MQTT_REFILL_FULL, payload=json.dumps({'siteId': self._siteId}))
					time.sleep(5)
					self._leds.clear()
					refilling = False
			elif gpio.input(self._WATER_75_PIN):
				if was != 75:
					print(75)
					was = 75
					self._leds.onDisplayLevel(4, [0, 0, 255])
			elif gpio.input(self._WATER_50_PIN):
				if was != 50:
					print(50)
					was = 50
					self._leds.onDisplayLevel(3, [0, 0, 255])
			elif gpio.input(self._WATER_25_PIN):
				if was != 25:
					print(25)
					was = 25
					self._leds.onDisplayLevel(2, [0, 0, 255])
			elif gpio.input(self._WATER_EMPTY_PIN):
				if was != 0:
					print(0)
					was = 0
					self._leds.onDisplayLevel(1, [0, 0, 255])
			else:
				if was != -1:
					print(-1)
					was = -1
					self._leds.onDisplayLevel(0, [0, 0, 255])

			time.sleep(0.25)

		gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)


	def _emptyingMode(self):
		"""
		User asked to empty the tank. Let's run the pump for as long as the sensor returns not -1
		"""
		print('here')
		self._leds.clear()
		gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
		self._pump()
		was = 0
		emptying = True
		while emptying:
			if gpio.input(self._WATER_FULL_PIN):
				if was != 100:
					print(100)
					was = 100
					self._leds.onDisplayLevel(5, [0, 0, 255])
			elif gpio.input(self._WATER_75_PIN):
				if was != 75:
					print(75)
					was = 75
					self._leds.onDisplayLevel(4, [0, 0, 255])
			elif gpio.input(self._WATER_50_PIN):
				if was != 50:
					print(50)
					was = 50
					self._leds.onDisplayLevel(3, [0, 0, 255])
			elif gpio.input(self._WATER_25_PIN):
				if was != 25:
					print(25)
					was = 25
					self._leds.onDisplayLevel(2, [0, 0, 255])
			elif gpio.input(self._WATER_EMPTY_PIN):
				if was != 0:
					print(0)
					was = 0
					self._leds.onDisplayLevel(1, [0, 0, 255])
			else:
				if was != -1:
					print(-1)
					was = -1
					self._leds.onDisplayLevel(1, [0, 0, 255])
					time.sleep(5)
					self._leds.onDisplayLevel(0, [0, 0, 255])
					time.sleep(10)
					self._mqtt.publish(topic=self._MQTT_WATER_EMPTIED, payload=json.dumps({'siteId': self._siteId}))
					self._pump(False)
					emptying=False

			time.sleep(0.25)

		gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)


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


	def _onAlert(self, sensor, limit):
		if sensor == 'water':
			if limit == 'min':
				self._leds.onDisplayMeter(percentage=20, color=[255, 0, 0], autoAlert=True)
			else:
				self._leds.onDisplayMeter(percentage=100, color=[255, 0, 0], autoAlert=True)


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
		data = dict({'siteId': self._siteId})
		try: # Chirp sometimes crashes, in which case we simply recall the telemetry query
			self._moistureSensor.wake_up()
			self._moistureSensor.trigger()
			time.sleep(1)
			moisture = self._moistureSensor.moist_percent
			light = self._moistureSensor.light
			temperature = self._moistureSensor.temp
			self._moistureSensor.sleep()
			# moisture = 15
			# temperature = 20
			# light = 2356
			if moisture > 100 or moisture < 0 or temperature > 100:
				raise Exception('Impossible chirp sensor values')
			else:
				data['temperature'] = temperature
				data['luminosity'] = light
				data['moisture'] = moisture
		except Exception as e:
			self._logger.error(e)
			return self._queryTelemetryData()

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

		print('Moisture: {}% temperature: {:.1f}°C light: {} lux water: {}'.format(moisture, temperature, light, data['water']))
		return data
