#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import adafruit_dotstar
import board
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
		self._pixels = adafruit_dotstar.DotStar(board.APA102_SCK, board.APA102_MOSI, 5)
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
		self._clearAnimation()
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


	def _startAnimation(self):
		"""
		Start animation, gradually fill the pixels with blue
		"""
		i = 0
		while i < 5:
			self._pixels[i] = [0, 0, 255]
			time.sleep(0.5)
		time.sleep(1)
		self._clear()


	def _displayMeter(self, color, percentage, autoAlert=False):
		"""
		Gradually fills the pixels with the given color up to the given percentage and then slowly breaths the leds for 10 seconds
		:param color: RGB array
		:param percentage: A multiple of 20 as we have 5 leds only!
		:param autoAlert: If not an automated alert but info asked by the user, the animation will stop after 10 seconds. Otherwise it will stay on
		"""
		ledsToLight = int(percentage / 20)
		i = 0
		while i < ledsToLight:
			self._pixels[i] = color
			time.sleep(0.5)

		self._timer = threading.Timer(interval=10, function=self._clear)
		self._timer.setDaemon(True)
		self._timer.start()

		self._animating.set()
		bri = 1.0
		while self._animating.isSet():
			if bri > 0.1:
				bri -= 0.1
			else:
				bri += 0.1
				if bri > 1.0:
					bri = 1.0
			self._pixels.brightness = bri
			time.sleep(0.1)


	def _clear(self):
		"""
		Used to clear the leds, turn them off. Stops any running animation and sets the leds to [0, 0, 0]
		"""
		self._clearAnimation()
		self._pixels.fill([0, 0, 0])


	def _clearAnimation(self):
		"""
		Clears any running animation and cancels timer
		"""
		if self._timer is not None and self._timer.isAlive:
			self._timer.cancel()
		self._animating.clear()