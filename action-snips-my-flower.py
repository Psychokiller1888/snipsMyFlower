#!/usr/bin/env python
# -*- coding: utf-8 -*-

from I18n import I18n
import json
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import pytoml


class SnipsMyFlower:
	""" Snips app for My Snips Flower"""

	_INTENT_WATER = 'Psychokiller1888:water'

	def __init__(self):
		self._i18n = I18n("en")
		self.runMqtt()


	def onMessage(self, hermes, message):
		topic = message.intent.intent_name
		if topic == self._INTENT_WATER:
			pass


	def runMqtt(self):
		try:
			toml = pytoml.loads('/etc/snips.toml')
			mqtt = toml['snips-common']['mqtt']
		except:
			mqtt = 'localhost:1883'

		with Hermes(mqtt) as hermes:
			hermes.subscribe_intents(self.onMessage).start()

if __name__ == "__main__":
	Snipsflower()