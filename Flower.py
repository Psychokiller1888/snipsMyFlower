#!/usr/bin/env python
# -*- coding: utf-8 -*-

import RPi.GPIO as gpio

class Flower:

	_WATER_SENSOR_PIN = 18
	_WATER_EMPTY_PIN = 18
	_WATER_25_PIN = 16
	_WATER_50_PIN = 16
	_WATER_75_PIN = 16
	_WATER_FULL_PIN = 16

	_PUMP_PIN = 18
	_LED_PIN = 18

	def __init__(self):
		gpio.setmode(gpio.BOARD)
		gpio.setwarnings(False)
		gpio.setup(self._PUMP_PIN, gpio.OUT)
		gpio.setup(self._LED_PIN, gpio.OUT)
		gpio.setup(self._WATER_SENSOR_PIN, gpio.OUT)
		gpio.setup(self._WATER_EMPTY_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_25_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_50_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_75_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(self._WATER_FULL_PIN, gpio.IN, gpio.PUD_DOWN)
		gpio.setup(16, gpio.IN, gpio.PUD_DOWN)


	def doWater(self):
		pass