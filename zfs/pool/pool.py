import subprocess
import struct
import select
import logging
import signal
import time
import typing
import traceback
from ..list import snapshots
from ..storage import storage
from ..logger import log
from ..exceptions import SysCallError
from ..general import (
	generate_transmission_id,
	SysCommand
)

class Pool:
	def __init__(self, pool_obj, recursive :bool = True):
		if '/' in pool_obj.name:
			raise ValueError(f"Pool() does not permit / in ZFSPool() object as it indicates a dataset.")

		if '@' in pool_obj.name:
			raise ValueError(f"Pool() does not permit @ in ZFSPool() object as it indicates a snapshot.")

		self.pool_obj = pool_obj
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
			traceback.print_tb(args[2])

		if self.worker:
			self.worker.stdout.close()
			self.worker.stderr.close()

	@property
	def transfer_id(self):
		if self.pool_obj.transfer_id is None:
			self.pool_obj.transfer_id = 0
		return self.pool_obj.transfer_id

	@property
	def name(self):
		return self.pool_obj.name

	def take_master_snapshot(self):
		highest_snapshot_number = max([0, ] + [snapshot.index_id for snapshot in snapshots()]) + 1

		SysCommand(f"zfs snapshot -r {self.name}@{highest_snapshot_number}")

		return f"{self.name}@{highest_snapshot_number}"

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
		log(f'Closing Pool on: {repr(self)}', level=logging.INFO, fg="green")

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
			struct.pack('B', 1) # Frame type 1 = Full Image
			+ struct.pack('B', self.transfer_id) # Which session are we initating
			+ struct.pack('B', len(self.name)) + bytes(self.name, 'UTF-8') # The volume name
		)

	@property
	def end_frame(self):
		return (
			struct.pack('B', 4) # Frame type 4 = END frame
			+ struct.pack('B', self.pool_obj.transfer_id) # Which session are we initating
		)


class PoolRestore:
	def __init__(self, pool :typing.List[typing.Any]):
		self.worker = None
		self.pollobj = select.epoll()
		self.fileno = None
		self.pool_info = pool
		self.restored = -1
		self.started = time.time()
		self.ended = None

	@property
	def name(self):
		if storage['arguments'].pool:
			return storage['arguments'].pool

		return self.pool_info[2]

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			traceback.print_tb(args[2])

		self.close()

	def __repr__(self):
		return f"PoolRestore(pool={repr(self.pool_info)}[{self.name}], restore_index={self.restored}"

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

		if frame_index <= self.restored and frame_index != 0:
			log(f"Chunk is already restored: {repr(frame)}", level=logging.DEBUG, fg="gray")
			return

		if frame_index != (self.restored + 1) % 255:
			log(f"Chunk is not next in line, we have {self.restored}, and this was {frame_index}, we expected {(self.restored + 1) % 255} on {repr(frame)}", level=logging.WARNING, fg="red")
			return self.close()

		self.restored = frame_index

		if storage['arguments'].debug:
			log(f"Restoring Pool using {repr(self)}", level=logging.DEBUG, fg="orange")
			
		try:
			self.worker.stdin.write(frame[5])
			self.worker.stdin.flush()

			if storage['arguments'].debug:
				log(f"Restored {frame_index} on {self}", level=logging.INFO, fg="gray")
		except:
			try:
				raise ValueError(self.worker.stdout.read(1024).decode('UTF-8'))
			except ValueError:
				log(f'Worker is already closed, silently ignoring restore on frame index: {frame_index}', level=logging.INFO, fg="yellow")
				pass # Worker is already closed

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
			self.worker.stderr.close()

			log(f'Closed restore on: {repr(self)} ({self.ended - self.started}s elapsed)', level=logging.INFO, fg="green")