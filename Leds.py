#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import adafruit_dotstar
from adafruit_blinka.board import raspi_40pin as board
import threading
import time
try:
	import queue as Queue
except ImportError:
	import Queue as Queue

class Leds:
	"""
	This class runs the dotstar leds
	"""
	def __init__(self):
		self._pixels = adafruit_dotstar.DotStar(board.SCK, board.MOSI, 5, brightness=0.2)
		self._queue = Queue.Queue()
		self._active = threading.Event()
		self._animating = threading.Event()
		self._timer = None
		self._thread = threading.Thread(target=self._run)
		self._thread.setDaemon(True)
		self._thread.start()


	def onStop(self):
		"""
		Called when the program goes down. Clears the animation and stops the loop
		"""
		self._active.clear()
		self.clear()
		if self._thread.isAlive():
			self._thread.join(timeout=2)


	def _put(self, func):
		"""
		Adds an animation to the animation queue
		:param func: fonction aka animation, to add to the queue
		"""

		self._clearAnimation()
		if self._active.isSet():
			self._queue.put(func)


	def _run(self):
		"""
		This is the thread for the led animations. It loops over the queue and calls the animations enqueued
		"""
		self._active.set()
		while self._active.isSet():
			func = self._queue.get()
			func()


	def onStart(self):
		"""
		Called when the program starts
		"""
		self._put(self._startAnimation)


	def onDisplayMeter(self, percentage, color=None, brightness=1, autoAlert=False):
		"""
		Playing meter animation
		"""
		if color is None:
			color = [0, 0, 0]

		self._put(lambda: self._displayMeter(color, percentage, brightness, autoAlert))


	def onDisplayLevel(self, numleds, color=None):
		"""
		Showing water level live
		"""
		if color is None:
			color = [0, 0, 0]

		self._put(lambda: self._displayLevel(numleds, color))


	def _startAnimation(self):
		"""
		Start animation, gradually fill the pixels with blue
		"""
		self._pixels.brightness = 1.0
		i = 0
		while i < 5:
			self._pixels[i] = [0, 0, 255]
			time.sleep(0.5)
			i += 1
		time.sleep(1)
		self.clear()


	def _displayLevel(self, numLeds, color):
		"""
		Used when filling or emptying the tank
		:type color: RGB array
		:param numLeds: integer
		"""
		self.clear()

		i = 0
		while i < numLeds:
			self._pixels[i] = color
			i += 1


	def _displayMeter(self, color, percentage, brightness=1, autoAlert=False):
		"""
		Gradually fills the pixels with the given color up to the given percentage and then slowly breaths the leds for 10 seconds
		:param color: RGB array
		:param percentage: A multiple of 20 as we have 5 leds only!
		:param autoAlert: If not an automated alert but info asked by the user, the animation will stop after 10 seconds. Otherwise it will stay on
		"""
		self.clear()

		ledsToLight = int(percentage / 20)
		i = 0
		while i < ledsToLight:
			self._pixels[i] = color
			i += 1
			if autoAlert:
				time.sleep(0.1)
			else:
				time.sleep(0.25)

		if not autoAlert:
			self._timer = threading.Timer(interval=10, function=self.clear)
			self._timer.setDaemon(True)
			self._timer.start()

		bri = brightness
		self._pixels.brightness = bri
		direction = -1

		# If we want to have a constant speed on the animation whatever brightness we have, we need to calculate
		# the speed
		steps = round(bri / 0.04)
		sleep = round(2.5 / steps, 3) #If only one step, the sleep time would be 2.5 seconds

		self._animating.set()
		while self._animating.isSet():
			if bri > brightness:
				direction = -1
			elif bri < 0.2:
				direction = 1
			bri += direction * 0.04
			bri = round(bri, 2)
			self._pixels.brightness = bri
			time.sleep(sleep)


	def clear(self):
		"""
		Used to clear the leds, turn them off. Stops any running animation and sets the leds to [0, 0, 0]
		"""
		self._clearAnimation()
		self._pixels.fill(0)
		self._pixels.brightness = 1.0


	def _clearAnimation(self):
		"""
		Clears any running animation and cancels timer
		"""
		if self._timer is not None and self._timer.isAlive:
			self._timer.cancel()
		self._animating.clear()