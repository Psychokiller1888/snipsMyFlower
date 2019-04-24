#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class Plant(object):
	def __init__(self, name, data):
		self._name = name
		self._scientificName = data['scientific_name']
		self._moistureMin = data['moisture_min']
		self._moistureMax = data['moisture_max']
		self._temperatureMin = data['temperature_min']
		self._temperatureMax = data['temperature_max']
		self._humidityMax = data['humidity_max']
		self._humidityMin = data['humidity_min']
		self._luminosityMin = data['luminosity_min']
		self._luminosityMax = data['luminosity_max']


	@property
	def name(self):
		return self._name


	@property
	def scientificName(self):
		return self._scientificName


	@property
	def moistureMin(self):
		return self._moistureMin


	@property
	def moistureMax(self):
		return self._moistureMax


	@property
	def temperatureMin(self):
		return self._temperatureMin


	@property
	def temperatureMax(self):
		return self._temperatureMax


	@property
	def humidityMin(self):
		return self._humidityMin


	@property
	def humidityMax(self):
		return self._humidityMax


	@property
	def luminosityMin(self):
		return self._luminosityMin


	@property
	def luminosityMax(self):
		return self._luminosityMax