#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os

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
		moisture REAL,
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

		self._con = self._initDB()
		if self._con is None:
			print('Error initializing database')
			exit()

		self._plantsData = self._loadPlantsData()
		self._me = None

		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._watering.setDaemon(True)

		self._telemetry = threading.Thread(target=self._queryTelemetryData)
		self._telemetry.setDaemon(True)
		self._telemetry.start()

		self._monitoring = threading.Timer(interval=60, function=self._onMinute)
		self._monitoring.setDaemon(True)
		self._monitoring.start()


	@staticmethod
	def _loadPlantsData():
		with open('plantsData.json') as f:
			return json.loads(f)


	def loadFlower(self):
		if os.path.isfile('me.json'):
			with open('me.json', 'w+') as f:
				self._me = json.loads(f)
			return True
		else:
			return False


	def onStop(self):
		if self._watering.isAlive():
			self._watering.cancel()
			self._watering.join(timeout=2)

		if self._monitoring.isAlive():
			self._monitoring.cancel()
			self._monitoring.join(timeout=2)

		if self._telemetry.isAlive():
			self._telemetry.join(timeout=2)


	def doWater(self):
		if self._watering.isAlive():
			return False

		self._pump()
		self._watering.start()


	def _onMinute(self):
		self._monitoring.start()


	@staticmethod
	def _pump(on=True):
		if on:
			gpio.output(gpio.HIGH)
		else:
			gpio.output(gpio.LOW)


	def _queryTelemetryData(self):
		self._storeTelemetryData(['temp'])


	def _storeTelemetryData(self, data):
		try:
			data.insert(0, int(round(time.time())))
			cursor = self._con.cursor()
			sql = 'INSERT INTO telemetry (timestamp, temperature, luminosity, humidity, moisture, uv, water) VALUES (?, ?, ?, ?, ?, ?, ?)'
			cursor.execute(sql, data)
		except sqlite3.Error as e:
			print(e)

		return False


	def _getTelemetryData(self):
		try:
			cursor = self._con.cursor()
			cursor.execute('SELECT * FROM telemetry ORDER BY timestamp DESC')
			return cursor.fetchall()
		except sqlite3.Error as e:
			print(e)
			return None



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