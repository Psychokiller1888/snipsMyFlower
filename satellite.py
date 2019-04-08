#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime 			import datetime
import logging.handlers
import signal
import time
from Flower import Flower

formatter = logging.Formatter('%(asctime)s [%(threadName)s] - [%(levelname)s] - %(message)s')

_logger = logging.getLogger('SnipsMyFlower')
_logger.setLevel(logging.INFO)

date = int(datetime.now().strftime('%Y%m%d'))

handler = logging.FileHandler(filename='logs.log', mode='w+')
rotatingHandler = logging.handlers.RotatingFileHandler(filename='./logs/{}-logs.log'.format(date), mode='a', maxBytes=100000, backupCount=20)
streamHandler = logging.StreamHandler()

handler.setFormatter(formatter)
rotatingHandler.setFormatter(formatter)

_logger.addHandler(handler)
_logger.addHandler(rotatingHandler)
_logger.addHandler(streamHandler)


def stopHandler(signum, frame):
	global RUNNING
	RUNNING = False

def main():
	global RUNNING

	signal.signal(signal.SIGINT, stopHandler)
	signal.signal(signal.SIGTERM, stopHandler)

	flower = Flower()
	try:
		while RUNNING:
			time.sleep(0.1)
	except KeyboardInterrupt:
		pass
	finally:
		flower.onStop()
		_logger.info('Stopping Snips My Flower')

RUNNING = False

if __name__ == '__main__':
	RUNNING = True
	main()
