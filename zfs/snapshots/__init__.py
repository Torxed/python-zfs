import select
import struct
import zlib
from subprocess import Popen, PIPE, STDOUT

class Snapshot:
	def __init__(self, namespace):
		self.namespace = namespace
		self.worker = None

	def __enter__(self):
		self.worker = Popen(["zfs", "send", "-c", self.namespace], shell=False, stdout=PIPE, stderr=PIPE)
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
		self.namespace = bytes(self.namespace, 'UTF-8')
		return (
			struct.pack('B', 0)
			+struct.pack('B', transfer_id)
			+struct.pack('I', zlib.crc32(self.namespace) & 0xffffffff)
			+struct.pack('B', len(self.namespace)) + self.namespace
		)

class Delta:
	def __init__(self, origin, destination):
		self.origin = origin
		self.destination = destination
		self.worker = None

	def __enter__(self):
		self.worker = Popen(["zfs", "send", "-c", "-I", self.origin, self.destination], shell=False, stdout=PIPE, stderr=PIPE)
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
		origin = bytes(self.origin, 'UTF-8')
		destination = bytes(self.destination, 'UTF-8')
		return (
			struct.pack('B', 1)
			+struct.pack('B', transfer_id)
			+struct.pack('I', zlib.crc32(origin + destination) & 0xffffffff)
			+struct.pack('B', len(origin)) + origin
			+struct.pack('B', len(destination)) + destination
		)

class DeltaReader:
	def __init__(self):
		self.worker = None
		self.transfer_id = None

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
			self.worker = Popen(["zfs", "recv", frame['information']['destination_name']], shell=False, stdout=PIPE, stdin=PIPE, stderr=PIPE)

		print(f"Restoring: {frame['data']['data'][:50]}")
		self.worker.stdin.write(frame['data']['data'])
		self.worker.stdin.flush()

		for fileno in select.select([self.worker.stdout.fileno()], [], [], 0.2)[0]:
			output = self.worker.stdout.read(1024).decode('UTF-8')
			if output:
				print(output)

		for fileno in select.select([self.worker.stderr.fileno()], [], [], 0.2)[0]:
			raise ValueError(self.worker.stderr.read(1024))