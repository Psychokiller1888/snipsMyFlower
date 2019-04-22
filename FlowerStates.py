#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum

class State(Enum):
	BOOTING = 0
	READY = 1
	OK = 2
	HOT = 3
	COLD = 4
	DRAWNED = 5
	THIRSTY = 6
	TOO_DARK = 7
	TOO_BRIGHT = 8
	OUT_OF_WATER = 9
	WATERING = 10
	EMPTYING = 11
	FILLING = 12