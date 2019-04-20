#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from Chirp import Chirp
from enum import Enum
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
	_MQTT_ALERT_USER = 'snipsmyflower/flowers/alertUser'

	def __init__(self):
		"""
		Initiliazes the flower instance
		Tries to connect to master mqtt, gets its site id, loads itself and starts the 5 minute monitoring thread
		It also tells the master device that it is connected
		"""
		self._logger = logging.getLogger('SnipsMyFlower')
		self._state = State.BOOTING
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
                    min_moist=217,
                    max_moist=626,
                    temp_scale='celsius',
                    temp_offset=-0.5)
		self._leds = Leds()
		self._leds.onStart()
		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._monitoring = None
		self._refilling = None
		self._emptying = None
		self._onFiveMinute()
		self._state = State.READY


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
			if self._state == State.FILLING or self._state == State.EMPTYING or self._state == State.WATERING:
				self._doWater()

		elif topic == self._MQTT_PLANT_ALERT:
			telemetry = payload['telemetry']
			limit = payload['limit']
			if telemetry == 'temperature':
				if limit == 'min':
					if self._state != State.COLD:
						self._state = State.COLD
						self._alertUser(telemetry, limit)
				else:
					if self._state != State.HOT:
						self._state = State.HOT
						self._alertUser(telemetry, limit)
			elif telemetry == 'moisture':
				if limit == 'min':
					if self._state != State.THIRSTY:
						self._state = State.THIRSTY
						#self._alertUser(telemetry, limit)
						self._doWater()
				else:
					if self._state != State.DRAWNED:
						self._state = State.DRAWNED
						self._alertUser(telemetry, limit)
			elif telemetry == 'luminosity':
				if limit == 'min':
					if self._state != State.TOO_DARK:
						self._state = State.TOO_DARK
						self._alertUser(telemetry, limit)
				else:
					if self._state != State.TOO_BRIGHT:
						self._state = State.TOO_BRIGHT
						self._alertUser(telemetry, limit)
			elif telemetry == 'water':
				if self._state != State.OUT_OF_WATER:
					self._state = State.OUT_OF_WATER
					self._alertUser(telemetry, limit)
			else:
				self._state = State.OK
				self._leds.clear()

			self._onAlert(telemetry, limit)

		elif topic == self._MQTT_REFILL_MODE:
			if self._state == State.FILLING or self._state == State.EMPTYING or self._state == State.WATERING:
				self._mqtt.publish(topic=self._MQTT_REFUSED, payload=json.dumps({'siteId': self._siteId}))
				return

			self._refilling = threading.Thread(target=self._refillingMode)
			self._refilling.setDaemon(True)
			self._refilling.start()

		elif topic == self._MQTT_EMPTY_WATER:
			if self._state == State.FILLING or self._state == State.EMPTYING or self._state == State.WATERING:
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


	def _alertUser(self, telemetry, limit):
		"""
		Sends a message to main unit for it to alert the user
		:param telemetry: string
		:param limit: string
		"""
		self._mqtt.publish(topic=self._MQTT_ALERT_USER, payload=json.dumps({'siteId': self._siteId, 'telemetry': telemetry, 'limit': limit}))


	def _refillingMode(self):
		"""
		User asked for tank refilling. We need to update the led indicator according to water level
		and to alert the user when the level is full which will stop the refilling mode
		"""
		self._leds.clear()
		gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
		self._state = State.FILLING
		was = 0
		while self._state == State.FILLING:
			if gpio.input(self._WATER_FULL_PIN):
				if was != 100:
					was = 100
					self._leds.onDisplayLevel(5, [0, 0, 255])
					self._mqtt.publish(topic=self._MQTT_REFILL_FULL, payload=json.dumps({'siteId': self._siteId}))
					self._onFiveMinute() # Manually trigger onFiveMinutes to send data to the main unit
					time.sleep(5)
					self._leds.clear()
					self._state = State.OK
			elif gpio.input(self._WATER_75_PIN):
				if was != 75:
					was = 75
					self._leds.onDisplayLevel(4, [0, 0, 255])
			elif gpio.input(self._WATER_50_PIN):
				if was != 50:
					was = 50
					self._leds.onDisplayLevel(3, [0, 0, 255])
			elif gpio.input(self._WATER_25_PIN):
				if was != 25:
					was = 25
					self._leds.onDisplayLevel(2, [0, 0, 255])
			elif gpio.input(self._WATER_EMPTY_PIN):
				if was != 0:
					was = 0
					self._leds.onDisplayLevel(1, [0, 0, 255])
			else:
				if was != -1:
					was = -1
					self._leds.onDisplayLevel(0, [0, 0, 255])

			time.sleep(0.25)

		gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)


	def _emptyingMode(self):
		"""
		User asked to empty the tank. Let's run the pump for as long as the sensor returns not -1
		"""
		self._leds.clear()
		gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
		self._pump()
		self._state = State.EMPTYING
		was = 0
		while self._state == State.EMPTYING:
			if gpio.input(self._WATER_FULL_PIN):
				if was != 100:
					was = 100
					self._leds.onDisplayLevel(5, [0, 0, 255])
			elif gpio.input(self._WATER_75_PIN):
				if was != 75:
					was = 75
					self._leds.onDisplayLevel(4, [0, 0, 255])
			elif gpio.input(self._WATER_50_PIN):
				if was != 50:
					was = 50
					self._leds.onDisplayLevel(3, [0, 0, 255])
			elif gpio.input(self._WATER_25_PIN):
				if was != 25:
					was = 25
					self._leds.onDisplayLevel(2, [0, 0, 255])
			elif gpio.input(self._WATER_EMPTY_PIN):
				if was != 0:
					was = 0
					self._leds.onDisplayLevel(1, [0, 0, 255])
			else:
				if was != -1:
					was = -1
					self._leds.onDisplayLevel(1, [0, 0, 255])
					time.sleep(5)
					self._leds.onDisplayLevel(0, [0, 0, 255])
					time.sleep(10)
					self._mqtt.publish(topic=self._MQTT_WATER_EMPTIED, payload=json.dumps({'siteId': self._siteId}))
					self._onFiveMinute()  # Manually trigger onFiveMinutes to send data to the main unit
					self._pump(False)
					self._state = State.OK

			time.sleep(0.25)

		gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)


	def _onFiveMinute(self):
		"""
		Called every 5 minutes, this method does ask for the latest sensor data and sends them to the main unit
		It also runs checks on the data to alert the user if needed
		"""
		#self._monitoring = threading.Timer(interval=300, function=self._onFiveMinute)
		if self._monitoring is not None and self._monitoring.isAlive():
			self._monitoring.cancel()

		self._monitoring = threading.Timer(interval=30, function=self._onFiveMinute) #TODO remove me!!
		self._monitoring.setDaemon(True)
		self._monitoring.start()
		self._sendData()


	def _sendData(self):
		"""
		Sends telemetry data to main unit
		"""
		data = self._queryTelemetryData()
		self._mqtt.publish(topic=self._MQTT_TELEMETRY_REPORT, payload=json.dumps({
			'siteId': self._siteId,
			'plant': self._me['type'],
			'data': data
		}))


	def _onAlert(self, sensor, limit):
		if sensor == 'water':
			self._leds.onDisplayMeter(percentage=20, color=[0, 0, 255], autoAlert=True)
		elif sensor == 'temperature':
			if limit == 'min':
				self._leds.onDisplayMeter(percentage=100, color=[77, 255, 255], autoAlert=True)
			else:
				self._leds.onDisplayMeter(percentage=100, color=[255, 0, 0], autoAlert=True)
		elif sensor == 'luminosity':
			if limit == 'min':
				self._leds.onDisplayMeter(percentage=100, color=[0, 51, 51], autoAlert=True)
			else:
				self._leds.onDisplayMeter(percentage=100, color=[204, 255, 255], autoAlert=True)
		elif sensor == 'moisture':
			if limit == 'min':
				self._leds.onDisplayMeter(percentage=100, color=[255, 255, 0], autoAlert=True)
			else:
				self._leds.onDisplayMeter(percentage=100, color=[0, 25, 0], autoAlert=True)


	def _pump(self, on=True):
		"""
		Turn pump on or off
		:param on: boolean
		"""
		if on:
			self._state = State.WATERING
			gpio.output(self._PUMP_PIN, gpio.HIGH)
		else:
			self._state = State.OK
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
				light = round((100 / 65535) * light, 2) # 65535 is dark, 0 is bright, turn this to percentage before sending
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


class State(Enum):
	BOOTING = 0
	READY = 1
	OK = 2
	HOT = 3
	COLD = 4
	DRAWNED = 5
	THIRSTY = 6
	TOO_DARK = 7
	TOO_BRIGHT = 8
	OUT_OF_WATER = 9
	WATERING = 10
	EMPTYING = 11
	FILLING = 12
