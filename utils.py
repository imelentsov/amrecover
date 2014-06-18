#!/usr/bin/python3.3
# -*- coding: utf-8 -*-
'''
Created on 2014-06-17 07:21
@summary: 
@author: i.melentsov
'''

class Item(object):
	def __init__(self, data):
		self._itemData = data
		self._childItems = []

	def appendChild(self, item):
		self._childItems.append(item)

	@property
	def has_children(self):
		return not not self._childItems

	@property
	def children(self):
		return self._childItems

	#<FileName>
	@property
	def data(self):
		return self._itemData
