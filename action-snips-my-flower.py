#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import sqlite3

from I18n import I18n
import json
import paho.mqtt.client as mqtt
import pytoml
from Slot import Slot
import sys
import time


class SnipsMyFlower:
	""" Snips app for My Snips Flower by Psycho """

	_INTENT_WATER = 'hermes/intent/Psychokiller1888:water'
	_INTENT_TELEMETRY = 'hermes/intent/Psychokiller1888:telemetry'
	_INTENT_ANSWER_FLOWER = 'hermes/intent/Psychokiller1888:flowerNames'

	_MQTT_GET_TELEMETRY = 'snipsmyflower/flowers/getTelemetry'
	_MQTT_TELEMETRY_REPORT = 'snipsmyflower/flowers/telemetryData'
	_MQTT_DO_WATER = 'snipsmyflower/flowers/doWater'

	_TELEMETRY_TABLE = """ CREATE TABLE IF NOT EXISTS telemetry (
		id integer PRIMARY KEY,
		siteId TEXT NOT NULL,
		timestamp integer NOT NULL,
		temperature REAL,
		luminosity REAL,
		moisture REAL,
		water INTEGER
	);"""

	def __init__(self):
		"""
		Initialize this class
		Instanciates the translation class, connects to mqtt and intializes the sqlite database connection
		"""
		self._i18n = I18n()
		self._mqtt = self._connectMqtt()
		if not self._mqtt:
			print('Cannot connect mqtt')
			sys.exit()

		if self._initDB() is None:
			print('Error initializing database')
			sys.exit()


	def _onMessage(self, client, userdata, message):
		"""
		Whenever a message we are subscribed to enter this function is called
		"""
		try:
			payload = json.loads(message.payload.decode('utf-8'))
		except:
			payload = dict()

		topic = message.topic
		siteId = 'default'
		sessionId = -1
		if 'siteId' in payload:
			siteId = payload['siteId']
		if 'sessionId' in payload:
			sessionId = payload['sessionId']

		slots = self.parseSlots(payload)

		wasIntent = ''
		if 'wasIntent' in slots:
			wasIntent = slots['wasIntent']

		if topic == self._INTENT_TELEMETRY:
			# User is asking for some data
			data = self._getTelemetryData(siteId)
			if len(data) <= 0:
				self.endDialog(sessionId=sessionId, text=self._i18n.getRandomText('noData'))
				return

			if 'when' not in slots:
				# If the user did not provide a timeframe info, return him the actual data
				self.endDialog(sessionId=sessionId, text=data[0][slots['type']])
			else:
				# User asked for a time specific data
				when = self._getSlotInfo('when', payload)[0]

				if when.value['kind'] == 'TimeInterval':
					pass
				elif when.value['kind'] == 'InstantTime':
					t = when.value['value']
					try:
						timestamp = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S %z').timestamp()
					except Exception as e:
						print(e)
						self.endDialog(sessionId=sessionId, text=self._i18n.getRandomText('error'))
						return



					return

		elif topic == self._MQTT_TELEMETRY_REPORT or len(payload.keys()) <= 0:
			# Store telemetry data reported by connected plants
			if siteId == 'default':
				return

			self._storeTelemetryData([
				payload['data']['siteId'],
				payload['data']['temperature'],
				payload['data']['luminosity'],
				payload['data']['moisture'],
				payload['data']['water']
			])
			return



		elif topic == self._INTENT_WATER:
			# User asking for the plant to activate its internal pump
			if siteId == 'default':
				return
			self.endDialog(sessionId=sessionId, text=self._i18n.getRandomText('thankyou'))
			self._mqtt.publish(topic=self._MQTT_DO_WATER, payload=json.dumps({'siteId': siteId}))


	def onStop(self):
		"""
		Called when the skill goes down, for a pi reboot per exemple
		Stops the mqtt loop and disconnects from mqtt
		"""
		self._mqtt.loop_stop(force=True)
		self._mqtt.disconnect()


	def endDialog(self, sessionId, text=None):
		"""
		End a session by speaking the provided string if any
		:param sessionId: integer
		:param text: string
		"""
		if text is not None:
			self._mqtt.publish('hermes/dialogueManager/endSession', json.dumps({
				'sessionId': sessionId,
				'text'     : text
			}))
		else:
			self._mqtt.publish('hermes/dialogueManager/endSession', json.dumps({
				'sessionId': sessionId
			}))


	def continueSession(self, sessionId, text, customData, intentFilter=None):
		"""
		Continues the given session by speaking the provided string
		:param sessionId: integer, session to continue
		:param text: string
		:param customData: dict
		:param intentFilter: list
		"""
		jsonDict = {
			'sessionId'              : sessionId,
			'text'                   : text,
			'customData'             : customData,
			'sendIntentNotRecognized': True
		}

		if intentFilter is not None:
			jsonDict['intentFilter'] = intentFilter

		self._mqtt.publish('hermes/dialogueManager/continueSession', json.dumps(jsonDict))


	def askUser(self, text, client='default', intentFilter=None, customData=None):
		"""
		Starts a new session by speaking the provided text
		:param text: string
		:param client: string, site id where to start the session
		:param intentFilter: list
		:param customData: dict
		:return:
		"""
		if ' ' in client:
			client = client.replace(' ', '_')

		if intentFilter is None:
			intentFilter = ''

		jsonDict = {
			'siteId'    : client,
			'customData': customData
		}

		initDict = {
			'type'         : 'action',
			'text'         : text,
			'canBeEnqueued': True
		}

		if intentFilter is not None:
			initDict['intentFilter'] = intentFilter

		self._mqtt.publish('hermes/dialogueManager/startSession', json.dumps(jsonDict))


	@staticmethod
	def parseSlots(payload):
		"""
		Parses slots from payload into simple key value list
		:param payload: dict
		:return: dict
		"""
		if 'slots' in payload:
			return dict((slot['slotName'], slot['rawValue']) for slot in payload['slots'])
		else:
			return {}


	@staticmethod
	def _getSlotInfo(slotName, payload):
		"""
		Parses slots from payload into objects containing all slot info. Only takes the slots corresponding to the given name
		:param slotName: string
		:param payload: dict
		:return: list
		"""
		slots = []
		if 'slots' in payload and slotName in payload['slots']:
			for slot in payload['slots']:
				if slot['slotName'] != slotName:
					continue
				slots.append(Slot(slot))
		return slots


	def _connectMqtt(self):
		"""
		Tries to connect to mqtt. Options are read from snips.toml
		:return: boolean
		"""
		try:
			toml = pytoml.loads('/etc/snips.toml')
			mqttHost = toml['snips-common']['mqtt']
		except:
			mqttHost = 'localhost:1883'

		try:
			mqttClient = mqtt.Client()
			mqttClient.on_connect = self._onConnect
			mqttClient.on_message = self._onMessage
			mqttClient.connect(mqttHost.split(':')[0], int(mqttHost.split(':')[1]))
			mqttClient.loop_start()
			return mqttClient
		except Exception as e:
			print(e)
			return False


	def _onConnect(self, client, userdata, flags, rc):
		"""
		Called whenever mqtt connects. It does subscribe our intents
		"""
		self._mqtt.subscribe([
			(self._MQTT_TELEMETRY_REPORT, 0),
			(self._INTENT_WATER, 0),
			(self._INTENT_TELEMETRY, 0),
			(self._INTENT_ANSWER_FLOWER, 0)
		])


	def _storeTelemetryData(self, data):
		"""
		Stores telemetry data from the connected flowers in internal database
		:param data: list
		:return: boolean
		"""
		try:
			con = self._sqlConnection()
			if con is None:
				return False
			data.insert(1, int(round(time.time())))
			cursor = con.cursor()
			sql = 'INSERT INTO telemetry (siteId, timestamp, temperature, luminosity, moisture, water) VALUES (?, ?, ?, ?, ?, ?)'
			cursor.execute(sql, data)
		except sqlite3.Error as e:
			print(e)

		return False


	def _getTelemetryData(self, siteId):
		"""
		Get telemetry data from database for the given site id
		:param siteId: string
		:return: list
		"""
		try:
			con = self._sqlConnection()
			if con is None:
				return None
			cursor = con.cursor()
			cursor.execute('SELECT * FROM telemetry WHERE siteId = ? ORDER BY timestamp DESC', siteId)
			return cursor.fetchall()
		except sqlite3.Error as e:
			print(e)
			return None


	def _initDB(self):
		"""
		Initializes the internal database as well as calls for table initialization
		:return: connection
		"""
		con = self._sqlConnection()
		if con is not None:
			self._initTable(con, self._TELEMETRY_TABLE)

		return con


	@staticmethod
	def _sqlConnection():
		"""
		Connects to a sqlite3 database
		:return: connection
		"""
		try:
			con = sqlite3.connect('/etc/snipsMyFlower/data.db')
			return con
		except sqlite3.Error as e:
			print(e)

		return None


	@staticmethod
	def _initTable(con, statement):
		"""
		Initializes database tables given through the statement argument
		:param con: sqlite connection object
		:param statement: string
		"""
		try:
			cursor = con.cursor()
			cursor.execute(statement)
		except sqlite3.Error as e:
			print(e)


if __name__ == "__main__":
	instance = None
	running = True
	try:
		instance = SnipsMyFlower()
		while running:
			time.sleep(0.1)
	except KeyboardInterrupt:
		pass
	finally:
		if instance is not None:
			instance.onStop()