#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import random

class I18n:

	def __init__(self, defaultLang='en'):
		self._i18n = {}
		self._defaultLang = defaultLang
		self._loadI18n()


	def _loadI18n(self):
		try:
			with open('i18n.json') as f:
				self._i18n = json.loads(f)
		except:
			print('Error loading language file')


	def getRandomText(self, text, lang=None):
		"""
		Returns a random text in the desired lang for the specified key. If not found it tries to return the english version
		:param text: string
		:param lang: string
		:return: string
		"""

		if lang is None:
			lang = self._defaultLang

		if text in self._i18n.keys():
			try:
				return random.choice(self._i18n[text][lang])
			except KeyError:
				try:
					print("Couldn't find i18n for key '{}' in {}".format(text, lang))
					return random.choice(self._i18n[text][self._defaultLang])
				except KeyError:
					print("Couldn't find i18n for key '{}'".format(text))
					return 'Answer not found'
		else:
			print('Unknown i18n key "{}"'.format(text))
			return 'Answer not found'