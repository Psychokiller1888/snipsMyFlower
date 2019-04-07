#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from Flower import Flower
from I18n import I18n
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import pytoml


class SnipsMyFlower:
	""" Snips app for My Snips Flower"""

	_INTENT_WATER = 'Psychokiller1888:water'

	def __init__(self):
		self._i18n = I18n()
		self._flower = Flower()
		self.runMqtt()

		if not self._flower.loadFlower():
			pass


	def onMessage(self, hermes, message):
		topic = message.intent.intent_name
		if topic == self._INTENT_WATER:
			self._flower.doWater()
			self.endSession(hermes, message.session_id, self._i18n.getRandomText('thankyou'))


	def onStop(self):
		self._flower.onStop()


	@staticmethod
	def endSession(hermes, sessionId, text):
		hermes.publish_end_session(sessionId, text)


	@staticmethod
	def continueSession(hermes, sessionId, text, customData, filter):
		hermes.publish_continue_session(sessionId,
										text,
										custom_data=json.dumps(customData))


	def askUser(self, hermes, text, filter):
		hermes.publish_start_session_action(None, text, filter, True, False, None)


	def say(self, hermes, text):
		hermes.publish_start_session_notification("plant", text, None)


	def runMqtt(self):
		try:
			toml = pytoml.loads('/etc/snips.toml')
			mqtt = toml['snips-common']['mqtt']
		except:
			mqtt = 'localhost:1883'

		with Hermes(mqtt) as hermes:
			hermes.subscribe_intents(self.onMessage).start()


if __name__ == "__main__":
	instance = None
	try:
		instance = SnipsMyFlower()
	except KeyboardInterrupt:
		pass
	finally:
		if instance is not None:
			instance.onStop()