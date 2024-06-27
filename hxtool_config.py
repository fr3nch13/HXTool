#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
from os import path
import sys, logging, logging.handlers, socket

import hxtool_logging
from hxtool_util import combine_app_path

logger = hxtool_logging.getLogger(__name__)

class hxtool_config:
	"""
	Default hard coded config
	"""
	DEFAULT_CONFIG = {
		'log_handlers' : {
			'rotating_file_handler' : {
				'file' : 'log/hxtool.log',
				'max_bytes' : 5000000,
				'backup_count' : 5,
				'level' : 'info',
				'format' : '[%(asctime)s] {%(module)s} {%(threadName)s} %(levelname)s - %(message)s'
			}
		},
		'network' : {
			'ssl' : 'enabled',
			'port' : 8080,
			'listen_address' : '0.0.0.0',
			'session_timeout' : 30,
			'url_prefix' : '',
		},
		'ssl' : {
			'cert' : 'hxtool.crt',
			'key' : 'hxtool.key'
		},
		'scheduler' : {
			'thread_count' : None,
			'defer_interval' : 30
		},
		'headers' : {
		},
		'cookies' : {
		}
	}

	LOG_LEVELS = {
			'debug' : logging.DEBUG,
			'info' : logging.INFO,
			'warning' : logging.WARNING,
			'error' : logging.ERROR,
			'critical' : logging.CRITICAL
		}
	
	def __init__(self, config_file):
		
		logger.info('Reading configuration file %s', config_file)
		if path.isfile(config_file):
			with open(config_file, 'r') as config_file_handle:
				self._config = json.load(config_file_handle)
				logger.info('Checking configuration file %s', config_file)
				if not {'log_handlers', 'network', 'ssl', 'scheduler'} <= set(self._config.keys()):
					raise ValueError('Configuration file is missing key elements!')
				else:
					logger.info('Configuration file %s is OK.', config_file)
				
				if 'proxies' in self._config['network']:
					if len(list(filter(lambda x: x == 'http' or x == 'https' or x == 'use_pac' or x == 'pac_url', self._config['network']['proxies']))) == 0:
						logger.warning("Ignoring invalid proxy configuration! Please see http://docs.python-requests.org/en/master/user/advanced/")
						del self._config['network']['proxies']
		else:
			logger.warning('Unable to open config file: %s, loading default config.', config_file)
			self._config = self.DEFAULT_CONFIG
			
	def __getitem__(self, key, default = None):
		v = self._config.get(key)
		if not v:
			v = default
		return v
		
	def get_child_item(self, parent_key, child_key, default = None):
		try:
			if self[parent_key] is not None:
				return self[parent_key].get(child_key, default)
		except TypeError:
			return default
			
	def get_config(self):
		return self._config
			
	def log_handlers(self):
		for handler_name in self._config['log_handlers']:
			if handler_name == 'rotating_file_handler':
				handler_config = self._config['log_handlers'][handler_name]
				if 'file' in handler_config:
					h = logging.handlers.RotatingFileHandler(combine_app_path(handler_config['file']))
					
					if 'max_bytes' in handler_config:
						h.maxBytes = handler_config['max_bytes']
					if 'backup_count' in handler_config:
						h.backupCount = handler_config['backup_count']
					
					self._set_level_and_format(handler_config, h)
					yield(h)
					
			elif handler_name == 'syslog_handler':
				handler_config = self._config['log_handlers'][handler_name]

				syslog_address = '127.0.0.1'
				syslog_port = logging.handlers.SYSLOG_UDP_PORT
				if 'address' in handler_config:
					syslog_address = handler_config['address']
				if 'port' in handler_config and 0 < handler_config['port'] < 65535:
					syslog_port = handler_config['port']	

				facility = logging.handlers.SysLogHandler.LOG_USER
				if 'facility' in handler_config:
					facility = logging.handlers.SysLogHandler.facility_names.get(handler_config['facility'])
				
				socket_type = socket.SOCK_DGRAM
				if 'protocol' in handler_config and handler_config['protocol'].lower() == 'tcp':
					socket_type = socket.SOCK_STREAM
					
				h = logging.handlers.SysLogHandler(address = (syslog_address, syslog_port), facility = facility, socktype = socket_type)
				
				self._set_level_and_format(handler_config, h)
				yield(h)
	
	def _set_level_and_format(self, handler_config, handler):
		level = logging.WARNING
		if 'level' in handler_config:
			level = self.LOG_LEVELS.get(handler_config['level'].lower())
		
		handler.setLevel(level)
		
		if 'format' in handler_config:
			handler.setFormatter(logging.Formatter(handler_config['format']))
