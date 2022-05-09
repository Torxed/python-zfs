import select
import struct
import zlib
import logging
from abc import abstractmethod
from subprocess import Popen, PIPE

from typing import TYPE_CHECKING
if TYPE_CHECKING:
	from ..models import Snapshot

from ..storage import storage
from ..general import FakePopenDestination
from ..logger import log

class Delta:
	def __init__(self, origin :'Snapshot', destination :'Snapshot'):
		self.origin = origin
		self.destination = destination
		self.worker = None

	def __enter__(self):
		if storage['arguments'].dummy_data:
			self.worker = FakePopenDestination(storage['arguments'].dummy_data)
		else:
			self.worker = Popen(["zfs", "send", "-c", "-I", self.origin.name, self.destination.name], shell=False, stdout=PIPE, stderr=PIPE)
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
		origin = bytes(self.origin.name, 'UTF-8')
		destination = bytes(self.destination.name, 'UTF-8')
		return (
			struct.pack('B', 1)
			+ struct.pack('B', transfer_id)
			+ struct.pack('I', zlib.crc32(origin + destination) & 0xffffffff)
			+ struct.pack('B', len(origin)) + origin
			+ struct.pack('B', len(destination)) + destination
			+ b'\x00' * (1392 - 8 - len(origin) - len(destination))
		)

	@abstractmethod
	def unpack_informational_frame(frame):
		print('Len info frame:', len(frame), '-', frame)
		frame_type = struct.unpack('B', frame[0:1])[0] # 1 Byte
		transfer_id = struct.unpack('B', frame[1:2])[0] # 1 Byte
		crc32_info = struct.unpack('I', frame[2:6])[0] # 4 Bytes
		origin_name_length = struct.unpack('B', frame[6:7])[0] # Length of the snapshot origin name
		origin_name = frame[7:7 + origin_name_length]
		destination_name_length = struct.unpack('B', frame[7 + origin_name_length:7 + origin_name_length + 1])[0]
		destination_name = frame[7 + origin_name_length + 1:7 + origin_name_length + 1 + destination_name_length]
		end_frame = 7 + origin_name_length + 1 + destination_name_length

		if len(frame[end_frame:].strip(b'\x00')):
			raise ValueError(f"Received too many bytes in Delta informational frame: {len(frame[end_frame:])} bytes too many")

		if crc32_info != zlib.crc32(origin_name + destination_name) & 0xffffffff:
			raise ValueError(f"CRC32 does not match in the informational frame, most likely corrupt data.")

		return {
			"frame_type" : frame_type,
			"transfer_id" : transfer_id,
			"origin_name" : origin_name.decode('UTF-8'),
			"destination_name" : destination_name.decode('UTF-8')
		}

class DeltaReader:
	def __init__(self, pre_flight_frame):
		self.worker = None
		self.pre_flight_frame = pre_flight_frame

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			self.worker.stdout.close()
			self.worker.stdin.close()
			self.worker.stderr.close()

	def unpack_snapshot_frame(self, frame):
		HEADER_LENGTH = 8

		length = struct.unpack('H', frame[6:HEADER_LENGTH])[0]
		data_position = length # The header is 8 bytes
		
		return {
			"transfer_id" : struct.unpack('B', frame[0:1])[0],
			"index" : struct.unpack('B', frame[1:2])[0],
			"crc_data" : struct.unpack('I', frame[2:6])[0],
			"data_len" : length,
			"data" : frame[HEADER_LENGTH:HEADER_LENGTH + data_position],
			"previous_data" : frame[HEADER_LENGTH + data_position:]
		}


	def restore(self, frame):
		if not self.worker:
			if storage['arguments'].dummy_data:
				self.worker = FakePopenDestination(storage['arguments'].dummy_data)
			else:
				self.worker = Popen(["zfs", "recv", self.pre_flight_frame.name], shell=False, stdout=PIPE, stdin=PIPE, stderr=PIPE)

		log(f"Restoring delta data via: {repr(self.pre_flight_frame)} ({frame.data})", level=logging.INFO, fg="green")
		self.worker.stdin.write(frame.data)
		self.worker.stdin.flush()

		if not storage['arguments'].dummy_data:
			for fileno in select.select([self.worker.stdout.fileno()], [], [], 0.2)[0]:
				output = self.worker.stdout.read(1024).decode('UTF-8')
				if output:
					print(output)

			for fileno in select.select([self.worker.stderr.fileno()], [], [], 0.2)[0]:
				raise ValueError(self.worker.stderr.read(1024))