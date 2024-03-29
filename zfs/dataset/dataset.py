import subprocess
import struct
import select
import logging
import signal
import time
import typing
import traceback
from ..list import snapshots, get_volume
from ..storage import storage
from ..logger import log
from ..exceptions import SysCallError, RestoreComplete
from ..general import (
	generate_transmission_id,
	SysCommand
)


class Dataset:
	def __init__(self, dataset_obj, recursive :bool = True):
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

			self.worker = subprocess.Popen(["zfs", "send", "-c", self.recursive, state_snapshot.name], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			self.pollobj.register(self.worker.stdout.fileno(), select.EPOLLIN|select.EPOLLHUP)

		return self

	def __exit__(self, *args):
		if args[0]:
			traceback.print_tb(args[2])

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
	def pool(self):
		return self.dataset.pool

	@property
	def stream_type(self):
		return self.dataset.stream_type
	
	@property
	def last_snapshots(self):
		from ..list import last_snapshots
		from ..models import Namespace

		for snapshot in last_snapshots(Namespace(name=f"{self.pool}/{self.name}"), n=2):
			yield snapshot

	def take_master_snapshot(self):
		from ..models.snapshots import Snapshot
		highest_snapshot_number = max([0, ] + [snapshot.index_id for snapshot in snapshots()]) + 1

		SysCommand(f"zfs snapshot -r {self.pool}/{self.name}@{highest_snapshot_number}")

		return Snapshot(f"{self.pool}/{self.name}@{highest_snapshot_number}", index_id=highest_snapshot_number)

	def take_snapshot(self):
		return self.take_master_snapshot()

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
			+ struct.pack('B', len(f"{self.pool}/{self.name}")) + bytes(f"{self.pool}/{self.name}", 'UTF-8') # The volume name
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
		self.restored = -1
		self.started = time.time()
		self.ended = None

		if get_volume(self.pool) is None:
			raise ValueError(f"Dataset '{self.pool}/{self.name}' does not exist, can not perform Dataset Restore!")

		log(f"Setting up {self}", level=logging.INFO, fg="orange")

	@property
	def name(self):
		if storage['arguments'].dataset:
			return storage['arguments'].dataset

		return self.dataset_info[2].split('/', 1)[1]

	@property
	def pool(self):
		if storage['arguments'].pool:
			return storage['arguments'].pool

		return self.dataset_info[2].split('/', 1)[0]

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			traceback.print_tb(args[2])

		self.close()

	def __repr__(self):
		return f"DatasetRestore(dataset={self.pool}/{self.name}, restore_index={self.restored}"

	def restore(self, frame):
		if not self.worker:
			if storage['arguments'].dummy_data:
				from ..general import FakePopenDestination
				self.worker = FakePopenDestination(storage['arguments'].dummy_data)
			else:
				self.worker = subprocess.Popen(
					["zfs", "recv", "-F", f"{self.pool}/{self.name}"],
					shell=False,
					stdout=subprocess.PIPE,
					stdin=subprocess.PIPE,
					stderr=subprocess.STDOUT
				)
				self.fileno = self.worker.stdout.fileno()
				if not storage['arguments'].dummy_data:
					self.pollobj.register(self.fileno, select.EPOLLIN|select.EPOLLHUP)

		frame_index = frame[2]

		if frame_index <= self.restored and frame_index != 0:
			log(f"Chunk is already restored: {repr(frame)}", level=logging.DEBUG, fg="gray")
			return None

		if frame_index != (self.restored + 1) % 255:
			log(f"Chunk is not next in line, we have {self.restored}, and this was {frame_index}, we expected {(self.restored + 1) % 255} on {repr(frame)}", level=logging.WARNING, fg="red")
			return self.close()

		self.restored = frame_index

		if storage['arguments'].debug:
			log(f"Restoring Dataset using {repr(self)}", level=logging.DEBUG, fg="orange")
			
		try:
			self.worker.stdin.write(frame[5])
			self.worker.stdin.flush()

			if storage['arguments'].debug:
				log(f"Restored {frame_index} on {self}", level=logging.INFO, fg="gray")
		except:
			raise ValueError(self.worker.stdout.read(1024).decode('UTF-8'))

		# if not storage['arguments'].dummy_data:
		# 	if self.pollobj.poll(0):
		# 		raise ValueError(self.worker.stdout.read(1024).decode('UTF-8'))


	def close(self):
		self.ended = time.time()

		self.worker.stdin.flush()
		if (rest_data := self.worker.stdout.read()) != b'':
			log(f"Restore might not have completed: {rest_data}", level=logging.WARNING, fg="orange")

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
		raise RestoreComplete(session=self)