#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

class I18n:

	def __init__(self, defaultLang):
		self._defaultLang = defaultLang
		self._loadI18n()


	def _loadI18n(self):
		try:
			pass
		except:
			pass


	def getRandomText(self, key, lang):
		"""
		Returns a random text in the desired lang for the specified key. If not found it tries to return the english version
		:param key: string
		:param lang: string
		:return: string
		"""
		pass