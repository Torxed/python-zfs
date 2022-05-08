import select
import struct
import zlib
from abc import abstractmethod
from subprocess import Popen, PIPE, STDOUT

from ..models import Snapshot
from .datasets import Image
from .workers import has_worker_for, setup_worker
from .delta import Delta, DeltaReader
from .image import ImageReader

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
			+b'\x00'*(1392-7-len(self.namespace))
		)

	@abstractmethod
	def unpack_informational_frame(frame):
		print('Len info frame:', len(frame), '-', frame)
		frame_type = struct.unpack('B', frame[0:1])[0] # 1 Byte
		transfer_id = struct.unpack('B', frame[1:2])[0] # 1 Byte
		crc32_info = struct.unpack('I', frame[2:6])[0] # 4 Bytes
		namespace_length = struct.unpack('B', frame[6:7])[0] # Length of the snapshot origin name
		namespace = frame[7:7+namespace_length]
		end_frame = 7+namespace_length+1

		if len(frame[end_frame:].strip(b'\x00')):
			raise ValueError(f"Received too many bytes in informational frame: {len(frame[end_frame:])} bytes too many")

		if crc32_info != zlib.crc32(namespace) & 0xffffffff:
			raise ValueError(f"CRC32 does not match in the Snapshot informational frame, most likely corrupt data.")

		return {
			"frame_type" : frame_type,
			"transfer_id" : transfer_id,
			"namespace" : namespace.decode('UTF-8')
		}