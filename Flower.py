#!/usr/bin/env python
# -*- coding: utf-8 -*-

import RPi.GPIO as gpio
import sqlite3
import threading
import time

class Flower:

	_WATER_SENSOR_PIN = 18
	_WATER_EMPTY_PIN = 18
	_WATER_25_PIN = 16
	_WATER_50_PIN = 16
	_WATER_75_PIN = 16
	_WATER_FULL_PIN = 16

	_PUMP_PIN = 18
	_LED_PIN = 18

	_TELEMETRY_TABLE = """ CREATE TABLE IF NOT EXISTS telemetry (
		id integer PRIMARY KEY,
		timestamp integer NOT NULL,
		temperature REAL,
		luminosity REAL,
		humidity REAL,
		uv REAL,
		water INTEGER
	);"""

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

		self._con = self._initDB()
		if self._con is None:
			print('Error initializing database')
			exit()

		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._watering.setDaemon(True)

		self._telemetry = threading.Thread(target=self._queryTelemetryData)
		self._telemetry.setDaemon(True)
		self._telemetry.start()


	def onStop(self):
		if self._watering.isAlive():
			self._watering.cancel()
			self._watering.join(timeout=2)

		if self._telemetry.isAlive():
			self._telemetry.join(timeout=2)


	def doWater(self):
		if self._watering.isAlive():
			return False

		self._pump()
		self._watering.start()


	@staticmethod
	def _pump(on=True):
		if on:
			gpio.output(gpio.HIGH)
		else:
			gpio.output(gpio.LOW)


	def _queryTelemetryData(self):
		self._storeTelemetryData(['temp'])
		data = []
		pass


	def _storeTelemetryData(self, data):
		try:
			data.insert(0, int(round(time.time())))
			cursor = self._con.cursor()
			sql = 'INSERT INTO telemetry (timestamp, type, data) VALUES (?, ?, ?, ?, ?, ?)'
			cursor.execute(sql, data)
		except sqlite3.Error as e:
			print(e)

		return False


	def _initDB(self):
		con = self._sqlConnection()
		if con is not None:
			self._initTables(con, self._TELEMETRY_TABLE)

		return con


	@staticmethod
	def _sqlConnection():
		try:
			con = sqlite3.connect('data.db')
			return con
		except sqlite3.Error as e:
			print(e)

		return None


	def _initTables(self, con, statement):
		try:
			cursor = con.cursor()
			cursor.execute(statement)
		except sqlite3.Error as e:
			print(e)