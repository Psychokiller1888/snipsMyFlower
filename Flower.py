#!/usr/bin/env python
# -*- coding: utf-8 -*-

from DHT import DHT
import json
import os
import RPi.GPIO as gpio
import sqlite3
import threading
import time
import Veml6070

class Flower:

	_WATER_SENSOR_PIN = 16
	_WATER_EMPTY_PIN = 29
	_WATER_25_PIN = 22
	_WATER_50_PIN = 24
	_WATER_75_PIN = 26
	_WATER_FULL_PIN = 36

	_PUMP_PIN = 37
	_LED_PIN = 31

	_TEMPHUMI_PIN = 18

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

		con = self._initDB()
		if con is None:
			print('Error initializing database')
			exit()

		self._plantsData = self._loadPlantsData()
		self._me = None
		self._sensor = DHT(str(11), self._TEMPHUMI_PIN)
		self._veml6070 = Veml6070.Veml6070()

		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])

		self._telemetryFlag = threading.Event()
		self._telemetry = threading.Thread(target=self._queryTelemetryData)
		self._telemetry.setDaemon(True)
		self._telemetry.start()

		self._monitoring = threading.Timer(interval=60, function=self._onMinute)
		self._monitoring.setDaemon(True)
		self._monitoring.start()

		self._waterMonitoringFlag = threading.Event()
		self._waterMonitoring = threading.Thread(target=self._waterLevelMonitoring)
		self._waterMonitoring.setDaemon(True)
		self._waterMonitoring.start()


	@staticmethod
	def _loadPlantsData():
		with open('plantsData.json', 'r') as f:
			data = f.read()
			return json.loads(data)


	def loadFlower(self):
		if os.path.isfile('me.json'):
			with open('me.json', 'w+') as f:
				data = f.read()
				self._me = json.loads(data)
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
			self._telemetryFlag.clear()
			self._telemetry.join(timeout=2)

		if self._waterMonitoring.isAlive():
			self._waterMonitoringFlag.clear()
			self._waterMonitoring.join(timeout=2)

		gpio.cleanup()


	def doWater(self):
		if self._watering.isAlive():
			return False

		self._pump()
		self._watering = threading.Timer(interval=5.0, function=self._pump, args=[False])
		self._watering.setDaemon(True)
		self._watering.start()


	def _onMinute(self):
		self._monitoring = threading.Timer(interval=60, function=self._onMinute)
		self._monitoring.setDaemon(True)
		self._monitoring.start()


	def _pump(self, on=True):
		if on:
			gpio.output(self._PUMP_PIN, gpio.HIGH)
		else:
			gpio.output(self._PUMP_PIN, gpio.LOW)


	def _queryTelemetryData(self):
		self._telemetryFlag.set()
		while self._telemetryFlag.isSet():
			humi, temp = self._sensor.read()
			print('Temperature: {:.1f}°C, humidity: {}%'.format(temp, humi))

			for i in [Veml6070.INTEGRATIONTIME_1_2T,
					  Veml6070.INTEGRATIONTIME_1T,
					  Veml6070.INTEGRATIONTIME_2T,
					  Veml6070.INTEGRATIONTIME_4T]:
				self._veml6070.set_integration_time(i)
				uv_raw = self._veml6070.get_uva_light_intensity_raw()
				uv = self._veml6070.get_uva_light_intensity()
				print("Integration Time setting %d: %f W/(m*m) from raw value %d" % (i, uv, uv_raw))

			time.sleep(5)


	def _storeTelemetryData(self, data):
		try:
			con = self._sqlConnection()
			if con is None:
				return False
			data.insert(0, int(round(time.time())))
			cursor = con.cursor()
			sql = 'INSERT INTO telemetry (timestamp, temperature, luminosity, humidity, moisture, uv, water) VALUES (?, ?, ?, ?, ?, ?, ?)'
			cursor.execute(sql, data)
		except sqlite3.Error as e:
			print(e)

		return False


	def _getTelemetryData(self):
		try:
			con = self._sqlConnection()
			if con is None:
				return None
			cursor = con.cursor()
			cursor.execute('SELECT * FROM telemetry ORDER BY timestamp DESC')
			return cursor.fetchall()
		except sqlite3.Error as e:
			print(e)
			return None


	def _waterLevelMonitoring(self):
		self._waterMonitoringFlag.set()
		while self._waterMonitoringFlag.isSet():
			gpio.output(self._WATER_SENSOR_PIN, gpio.HIGH)
			if gpio.input(self._WATER_FULL_PIN):
				print('full')
			elif gpio.input(self._WATER_75_PIN):
				print('75')
			elif gpio.input(self._WATER_50_PIN):
				print('50')
			elif gpio.input(self._WATER_25_PIN):
				print('25')
			elif gpio.input(self._WATER_EMPTY_PIN):
				print('empty')
			else:
				print('dry')

			gpio.output(self._WATER_SENSOR_PIN, gpio.LOW)
			time.sleep(5)


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