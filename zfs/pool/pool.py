import subprocess
import struct
import select
import logging
from ..models import ZFSPool
from ..storage import storage
from ..logger import log
from ..general import (
	generate_transmission_id,
	SysCommand
)

class Pool:
	def __init__(self, pool_obj :ZFSPool, recursive :bool = True):
		self.pool_obj = pool_obj
		self.recursive = "-R" if recursive else ""
		self.worker = None

	def __enter__(self):
		if storage['arguments'].dummy_data:
			from ..general import FakePopen
			self.worker = FakePopen(storage['arguments'].dummy_data)
		else:
			SysCommand(f"zfs unmount {self.pool_obj.name}")
			self.worker = subprocess.Popen(["zfs", "send", "-c", self.pool_obj.name], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			SysCommand(f"zfs mount {self.pool_obj.name}")

			self.worker.stdout.close()
			self.worker.stderr.close()

	@property
	def transfer_id(self):
		return self.pool_obj.transfer_id

	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=692):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)

	@property
	def pre_flight_info(self):
		return (
			struct.pack('B', 1) # Frame type 1 = Full Image
			+ struct.pack('B', self.pool_obj.transfer_id) # Which session are we initating
			+ struct.pack('B', len(self.pool_obj.name)) + bytes(self.pool_obj.name, 'UTF-8') # The volume name
		)


class PoolRestore:
	def __init__(self, pool :ZFSPool):
		self.worker = None
		self.pool = pool
		self.restored = []

	@property
	def name(self):
		if storage['arguments'].pool:
			return storage['arguments'].pool

		return self.pool.name

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			self.worker.stdout.close()
			self.worker.stdin.close()
			self.worker.stderr.close()

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
					stderr=subprocess.PIPE
				)

		if frame.frame_index in self.restored:
			log(f"Chunk is already restored: {frame}", level=logging.INFO, fg="red")
			return None

		self.restored = self.restored[-4:] + [frame.frame_index]

		log(f"Restoring Pool using {repr(self.pool)}[{self.name}]", level=logging.INFO, fg="green")
		self.worker.stdin.write(frame.data)
		self.worker.stdin.flush()

		if not storage['arguments'].dummy_data:
			for fileno in select.select([self.worker.stdout.fileno()], [], [], 0.2)[0]:
				output = self.worker.stdout.read(1024).decode('UTF-8')
				if output:
					print(output)

			for fileno in select.select([self.worker.stderr.fileno()], [], [], 0.2)[0]:
				raise ValueError(self.worker.stderr.read(1024))
