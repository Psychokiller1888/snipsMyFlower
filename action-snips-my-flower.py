#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from I18n import I18n
import paho.mqtt.client as mqtt
import pytoml
import sys
import time


class SnipsMyFlower:
	""" Snips app for My Snips Flower by Psycho """

	_INTENT_WATER = 'hermes/intent/Psychokiller1888:water'
	_INTENT_TELEMETRY = 'hermes/intent/Psychokiller1888:telemetry'
	_INTENT_ANSWER_FLOWER = 'hermes/intent/Psychokiller1888:flowerNames'

	_MQTT_GET_TELEMETRY = 'snipsmyflower/flowers/getTelemetry'
	_MQTT_ANSWER_TELEMETRY = 'snipsmyflower/flowers/telemetryData'
	_MQTT_DO_WATER = 'snipsmyflower/flowers/doWater'

	def __init__(self):
		self._i18n = I18n()
		self._mqtt = self._connectMqtt()
		if not self._mqtt:
			print('Cannot connect mqtt')
			sys.exit()

		self._telemetryData = dict()


	def _onMessage(self, client, userdata, message):
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

		if topic == self._INTENT_TELEMETRY or wasIntent == self._INTENT_TELEMETRY:
			if 'flower' not in slots:
				self.askUser(text=self._i18n.getRandomText('whatFlower'), client=siteId, intentFilter=[self._INTENT_ANSWER_FLOWER], customData={'wasIntent': self._INTENT_TELEMETRY})
				return

			if slots['flower'] in self._telemetryData.keys() and 'type' in slots:
				self.endDialog(sessionId=sessionId, text=self._telemetryData[slots['flower']][slots['type']])

		elif topic == self._MQTT_ANSWER_TELEMETRY:
			self._telemetryData[siteId] = payload['data']
			return

		elif topic == self._INTENT_WATER:
			if siteId == 'default':
				return
			self.endDialog(sessionId=sessionId, text=self._i18n.getRandomText('thankyou'))
			self._mqtt.publish(topic=self._MQTT_DO_WATER, payload=json.dumps({'siteId': siteId}))


	def onStop(self):
		self._mqtt.loop_stop(force=True)
		self._mqtt.disconnect()


	def endDialog(self, sessionId, text=None):
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


	def say(self, hermes, text):
		hermes.publish_start_session_notification("plant", text, None)


	@staticmethod
	def parseSlots(payload):
		if 'slots' in payload:
			return dict((slot['slotName'], slot['rawValue']) for slot in payload['slots'])
		else:
			return {}


	def _connectMqtt(self):
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
		self._mqtt.subscribe([
			(self._MQTT_ANSWER_TELEMETRY, 0),
			(self._INTENT_WATER, 0),
			(self._INTENT_TELEMETRY, 0),
			(self._INTENT_ANSWER_FLOWER, 0)
		])


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