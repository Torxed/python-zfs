import select
import struct
import zlib
import pathlib
from abc import abstractmethod
from subprocess import Popen, PIPE, STDOUT

from ..models import Snapshot, Volume
# from ..general import FakePopen
from ..storage import storage

class FakePopen:
	def __init__(self, fake_data :pathlib.Path):
		import os
		import io
		self.index_pos = 0
		self.stdout = fake_data.open('rb')
		self.stderr = io.StringIO()
		self.stdout.seek(-1, os.SEEK_END)
		self.length = self.stdout.tell()
		self.stdout.seek(0)

	def poll(self):
		return None if self.index_pos < self.length else 0

class Image:
	def __init__(self, volume :Volume, recursive :bool = True):
		self.volume = volume
		self.recursive = "-R" if recursive else ""
		self.worker = None

	def __enter__(self):
		if storage['arguments'].dummy_data:
			self.worker = FakePopen(storage['arguments'].dummy_data)
		else:
			self.worker = Popen(["zfs", "send", "-c", self.recursive, self.volume], shell=False, stdout=PIPE, stderr=PIPE)
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			self.worker.stdout.close()
			self.worker.stderr.close()

	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=692):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)

	def info_struct(self, transfer_id):
		volume = bytes(self.volume.name, 'UTF-8')

		return (
			struct.pack('B', 2) # Frame type
			+struct.pack('B', transfer_id) # Which session are we initating
			+struct.pack('B', len(volume)) + volume # The volume name
		)