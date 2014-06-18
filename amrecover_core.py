#!/usr/bin/python3.3
# -*- coding: utf-8 -*-
'''
Created on 2014-06-14 20:03
@summary: 
@author: i.melentsov
'''

import os
import threading
import subprocess
import datetime

from utils import Item

class AmrecoverWrapper(object):
	"""Wrapper on amrecover"""
	def __init__(self, config):
		super(object, self).__init__()
		args = []
		if 'config' in config:
			args.append(config['config'])
		if 'index_server' in config:
			args.append('-s')
			args.append(config['index_server'])
		if 'tape_server' in config:
			args.append('-t')
			args.append(config['tape_server'])
		if 'tape_device' in config:
			args.append('-d')
			args.append(config['tape_device'])
		args.extend(config["args"])
		self._process_output_reader =  InputStreamChunker(['amrecover>', ']?'])
		self._amrecover = subprocess.Popen(['amrecover'] + args, 
			stdin = subprocess.PIPE,
			stdout = self._process_output_reader.input,
			stderr = self._process_output_reader.input,
			bufsize = 0)

		self._amrecover_stdin = self._amrecover.stdin
		self._process_output_reader.setProcess(self._amrecover)
		self._process_output_reader.start()

	def command(self, command):
		self._amrecover_stdin.write(command.encode('utf-8'))

	def getPathTree(self):
		# up to the root

		self.command("pwd\n")
		cur_path = self.getCommandRes().split("\n")[1]
		first = second = cur_path 
		while True:
			self.command("cd ..\n")
			self.getCommandRes()
			self.command("pwd\n")
			first = self.getCommandRes().split("\n")[1]
			if first == second:
				break
			second = first
		root_path = first
		root_date = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
		root = Item("/") # fictive should be removed
		self.command("history\n")
		root_children_data = self.getCommandRes().split("\n")[2:-2]
		for child_data in root_children_data:
			parts = child_data.split(" ")
			root.appendChild(Item(parts[1] + " <{}>".format(parts[2])))

		for child in root.children:
			cur_date = child.data[:19]
			self.command("setdate {}\n".format(cur_date))
			self.getCommandRes()
			child.appendChild(self._processDir(root_path, child, cur_date))

		#restore
		self.command("setdate {}\n".format(root_date))
		self.getCommandRes()
		self.command("cd {}\n".format(cur_path))
		self.getCommandRes()
		return root


	def _processDir(self,_dir, root_item, cur_date):
		self.command("cd {}\n".format(_dir))
		self.getCommandRes()

		cur = Item(_dir if _dir[-1:] != '/' else _dir[:-1])
		self.command("ls\n")
		ls = self.getCommandRes().split("\n")[1:-1]
		for entry in ls:
			file_date = entry[:19]
			file_name = entry[20:]
			if file_date != cur_date or file_name == '.':
				continue
			item = None
			if file_name[-1:] == '/':
				item = self._processDir(file_name, item, cur_date)
			else:	
				item = Item(file_name)
			cur.appendChild(item)
		self.command("cd ..\n")
		self.getCommandRes()
		item = Item(_dir)
		return cur


	def quit(self):
		self.command('quit\n')
		self._process_output_reader.join()


	def getCommandRes(self):
		return ''.join(self._process_output_reader.getResult())
		
class InputStreamChunker(threading.Thread):
	def __init__(self, delimiters = ['\n']):
		super(InputStreamChunker, self).__init__()
		self.daemon = True
		self._data_available = threading.Event()
		self._data_available.clear() # parent will .wait() on this for results.
		self._data = []
		self._data_unoccupied = threading.Event()
		self._data_unoccupied.set() # parent will set this to true when self.results is being changed from outside
		self._r, self._w = os.pipe()
		self._finished = False
		self._waiting_process = None # process for waiting for finish  

		self._delimiters = delimiters

	@property
	def data_available(self):
		return self._data_available

	@property
	def data_unoccupied(self):
		return self._data_unoccupied

	@property
	def data(self):
		return self._data

	@property
	def input(self):
		return self._w

	@property
	def delimiters(self):
		return self._delimiters

	@delimiters.setter
	def delimiters(self, delimiters):
		self._delimiters = delimiters
	

	@property
	def isFinished(self):
		""" 
		   typically will be set when run method finished. usefull for not interactive programs
		"""
		return self._finished 

	def setProcess(self, process):
		self._waiting_process = process 

	def __del__(self):
		try:
			os.close(self._w)
		except:
			pass
		try:
			os.close(self._r)
		except:
			pass
		try:
			del self._w
			del self._r
			del self._data
		except:
			pass

	def input_stream_closer(process, stdout):
		process.wait()
		try:
			os.close(stdout)
		except:
			pass
		

	def run(self):
		_buffer = ''
		if self._waiting_process != None:
			p1 = threading.Thread(target=InputStreamChunker.input_stream_closer, args=(self._waiting_process, self._w,))
			p1.daemon = True
			p1.start()
		try:
			while True:
				l = os.read(self._r, 1).decode('utf-8')
				if l == '':
					self._data_unoccupied.wait()
					if _buffer != '':
						self._data.append(_buffer)
					self._data_available.set()
					break
				_buffer += l
				for delimiter in self._delimiters:
					if len(_buffer) >= len(delimiter):
						tail = _buffer[-len(delimiter):]
						if tail == delimiter:
							self._data_unoccupied.wait()
							self._data.append(_buffer)
							_buffer = ''
							self._data_available.set()
							break
		except:
			pass
		try:	
			os.close(self._r)
		except:
			pass
		self._finished = True

	def getResult(self):
		"""
		  Synchronous call 
		"""
		answers = []
		while not self._finished:
			if self._data_available.wait(0.2):
				break
		self._data_unoccupied.clear()
		while self._data:
			answers.append(self._data.pop(0))
		self._data_available.clear(); self._data_unoccupied.set()
		return answers

def testChunker():
	ch = InputStreamChunker()

	print('starting the subprocess1\n')
	p = subprocess.Popen(
		['ls'],
		stdout = ch.input,
		bufsize = 0)

	ch.setProcess(p)
	ch.start()
	
	res = []
	while not ch.isFinished:
		res.extend(ch.getResult())
	print(res)

	if p.poll() == None: #kill process; will automatically stop thread
		p.kill()
		p.wait()
	ch.join()

	ch1 = InputStreamChunker()

	print('starting the subprocess2\n')
	p1 = subprocess.Popen(
		['cat'],
		stdin = subprocess.PIPE,
		stdout = ch1.input,
		bufsize = 0)

	ch1.setProcess(p1)
	ch1.start()

	i = p1.stdin
	i.write(bytes('line1 qwer\n', 'utf-8'))
	print(ch1.getResult())
	i.write('line2 qwer\n'.encode('utf-8'))
	print(ch1.getResult())
	i.write('line3 zxcv asdf\n'.encode('utf-8'))
	print(ch1.getResult())

	if p1.poll() == None: #kill process; will automatically stop thread
		p1.kill()
		p1.wait()
	ch1.join()

def processDir(item, nesting):
	print("  "*nesting + item.data)
	for child in item.children:
		processDir(child, nesting + 1)

def testAmrecover():
	amrecover = AmrecoverWrapper(["DailySet1"], None)
	print(amrecover.getCommandRes(), end='')
	amrecover.command("sethost localhost\n")
	print(amrecover.getCommandRes(), end='')
	amrecover.command("setdisk /home/ubuntu/amanda\n")
	print(amrecover.getCommandRes(), end='')
	while True:
		_str = input().strip()
		if(_str == 'quit'):
			amrecover.quit()
			print(amrecover.getCommandRes(), end='')
			break
		elif _str == 'getPathTree':
			root = amrecover.getPathTree()
			nesting = 1
			for child in root.children:
				processDir(child, nesting)
			continue
		amrecover.command(_str + '\n')
		print(amrecover.getCommandRes(), end='')

if __name__ == '__main__':
	# testChunker()
	testAmrecover()