import subprocess
import struct
import select
import logging
import signal
import time
import typing
from ..list import snapshots
from ..storage import storage
from ..logger import log
from ..exceptions import SysCallError
from ..general import (
	generate_transmission_id,
	SysCommand
)

class Dataset:
	def __init__(self, dataset_obj, recursive :bool = True):
		if '/' not in dataset_obj.name:
			raise ValueError(f"Dataset() requires / in ZFSDataset() object as it indicates a dataset.")

		if '@' in dataset_obj.name:
			raise ValueError(f"Dataset() does not permit @ in ZFSDataset() object as it indicates a snapshot.")

		self.dataset = dataset_obj
		self.recursive = "-R" if recursive else ""
		self.worker = None
		self.pollobj = select.epoll()

	def __enter__(self):
		if storage['arguments'].dummy_data:
			from ..general import FakePopen
			self.worker = FakePopen(storage['arguments'].dummy_data)
		else:
			state_snapshot = self.take_master_snapshot()

			self.worker = subprocess.Popen(["zfs", "send", "-c", self.recursive, state_snapshot], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			self.pollobj.register(self.worker.stdout.fileno(), select.EPOLLIN|select.EPOLLHUP)

		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			self.worker.stdout.close()
			self.worker.stderr.close()

	@property
	def transfer_id(self):
		if self.dataset.transfer_id is None:
			self.dataset.transfer_id = 0
		return self.dataset.transfer_id

	@property
	def name(self):
		return self.dataset.name

	@property
	def stream_type(self):
		return self.dataset.stream_type
	

	def take_master_snapshot(self):
		if snaps := list(snapshots()):
			print(snaps)
			highest_snapshot_number = max([snapshot['index_id'] for snapshot in snaps]) + 1
		else:
			highest_snapshot_number = 1

		SysCommand(f"zfs snapshot -r {self.name}@{highest_snapshot_number}")

		return f"{self.name}@{highest_snapshot_number}"

	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=692):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)

		if self.pollobj.poll():
			return self.worker.stdout.read(buf_len)

	def close(self):
		log(f'Closing Dataset on: {repr(self)}', level=logging.INFO, fg="green")

		if self.worker:
			try:
				self.pollobj.unregister(self.worker.stdout.fileno())
			except:
				# No idea why this happens
				pass
			self.worker.stdout.close()
			self.worker.stdin.close()

	@property
	def pre_flight_info(self):
		return (
			struct.pack('B', 0) # Frame type 1 = Full Image
			+ struct.pack('B', self.transfer_id) # Which session are we initating
			+ struct.pack('B', len(self.name)) + bytes(self.name, 'UTF-8') # The volume name
		)

	@property
	def end_frame(self):
		return (
			struct.pack('B', 4) # Frame type 4 = END frame
			+ struct.pack('B', self.transfer_id) # Which session are we initating
		)


class DatasetRestore:
	def __init__(self, dataset :typing.List[typing.Any]):
		self.worker = None
		self.pollobj = select.epoll()
		self.fileno = None
		self.dataset_info = dataset
		self.restored = [-1]
		self.started = time.time()
		self.ended = None

	@property
	def name(self):
		if storage['arguments'].dataset:
			return storage['arguments'].dataset

		return self.dataset[2]

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		self.close()

	def __repr__(self):
		return f"DatasetRestore(dataset={repr(self.dataset)}[{self.name}], restore_index={self.restored[-1]}"

	def restore(self, frame):
		if not self.worker:
			if storage['arguments'].dummy_data:
				from ..general import FakePopenDestination
				self.worker = FakePopenDestination(storage['arguments'].dummy_data)
			else:
				self.worker = subprocess.Popen(
					["zfs", "recv", "-F", self.name],
					shell=False,
					stdout=subprocess.PIPE,
					stdin=subprocess.PIPE,
					stderr=subprocess.STDOUT
				)
				self.fileno = self.worker.stdout.fileno()
				if not storage['arguments'].dummy_data:
					self.pollobj.register(self.fileno, select.EPOLLIN|select.EPOLLHUP)

		frame_index = frame[2]

		if frame_index in self.restored:
			log(f"Chunk is already restored: {repr(frame)}", level=logging.INFO, fg="red")
			return self.close()

		if frame_index != (self.restored[-1] + 1) % 255:
			log(f"Chunk is not next in line, we have {self.restored}, and this was {frame_index}, we expected {(self.restored[-1] + 1) % 255} on {repr(frame)}", level=logging.WARNING, fg="red")
			return self.close()

		self.restored = self.restored[-4:] + [frame_index]

		if storage['arguments'].debug:
			log(f"Restoring Dataset using {repr(self)}", level=logging.DEBUG, fg="orange")
			
		try:
			self.worker.stdin.write(frame[5])
			self.worker.stdin.flush()
		except:
			raise ValueError(self.worker.stdout.read(1024).decode('UTF-8'))

		# if not storage['arguments'].dummy_data:
		# 	if self.pollobj.poll(0):
		# 		raise ValueError(self.worker.stdout.read(1024).decode('UTF-8'))


	def close(self):
		self.ended = time.time()

		if self.worker:
			if self.fileno:
				try:
					self.pollobj.unregister(self.worker.stdout.fileno())
				except:
					# No idea why this happens
					pass
			self.worker.send_signal(signal.SIGTERM)
			self.worker.stdout.close()
			self.worker.stdin.close()

		log(f'Closing restore on: {repr(self)} ({self.ended - self.started}s elapsed)', level=logging.INFO, fg="green")
		exit(1)