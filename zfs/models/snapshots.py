import pydantic
import logging
import struct
import zlib
from subprocess import Popen, PIPE
from typing import Optional

from .. import log

class Namespace(pydantic.BaseModel):
	name :str

class Snapshot(pydantic.BaseModel):
	name :str
	used :Optional[str] = None
	avail :Optional[str] = None
	refer :Optional[str] = None
	mountpoint :Optional[str] = None
	worker :Optional[Popen] = None

	class Config:
		arbitrary_types_allowed = True

	def destroy(self):
		from .. import SysCommand

		log(f"Destroying snapshot {repr(self)}", fg="red", level=logging.INFO)
		SysCommand(f'zfs destroy {self.name}')

	def restore(self):
		from .. import SysCommand

		log(f"Rolling back ZFS snapshot {repr(self)}", fg="orange", level=logging.INFO)
		SysCommand(f'zfs rollback {self.name}')

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
			+ struct.pack('B', transfer_id)
			+ struct.pack('I', zlib.crc32(self.namespace) & 0xffffffff)
			+ struct.pack('B', len(self.namespace)) + self.namespace
			+ b'\x00' * (1392 - 7 - len(self.namespace))
		)

	# @abstractmethod
	# def unpack_informational_frame(frame):
	# 	print('Len info frame:', len(frame), '-', frame)
	# 	frame_type = struct.unpack('B', frame[0:1])[0] # 1 Byte
	# 	transfer_id = struct.unpack('B', frame[1:2])[0] # 1 Byte
	# 	crc32_info = struct.unpack('I', frame[2:6])[0] # 4 Bytes
	# 	namespace_length = struct.unpack('B', frame[6:7])[0] # Length of the snapshot origin name
	# 	namespace = frame[7:7 + namespace_length]
	# 	end_frame = 7 + namespace_length + 1

	# 	if len(frame[end_frame:].strip(b'\x00')):
	# 		raise ValueError(f"Received too many bytes in informational frame: {len(frame[end_frame:])} bytes too many")

	# 	if crc32_info != zlib.crc32(namespace) & 0xffffffff:
	# 		raise ValueError(f"CRC32 does not match in the Snapshot informational frame, most likely corrupt data.")

	# 	return {
	# 		"frame_type" : frame_type,
	# 		"transfer_id" : transfer_id,
	# 		"namespace" : namespace.decode('UTF-8')
	# 	}

class Volume(pydantic.BaseModel):
	name :str
	used :Optional[str] = None
	avail :Optional[str] = None
	refer :Optional[str] = None
	mountpoint :Optional[str] = None

	@property
	def last_snapshots(self):
		from ..list import last_snapshots

		for snapshot in last_snapshots(Namespace(name=self.name), n=2):
			yield snapshot

	def take_snapshot(self, index :Optional[int] = None) -> str:
		from .. import SysCommand
		from ..list import last_snapshots

		log(f"Taking snapshot {repr(self)}", fg="green", level=logging.INFO)

		if index is None:
			for snapshot in last_snapshots(Namespace(name=self.name), n=1):
				if '@' not in snapshot.name:
					raise ValueError(f"Could not reliably determain index of snapshot because it's lacking @ in the snapshot name.")

				index = int(snapshot.name.split('@', 1)[-1]) + 1

		if index is None:
			index = 0

		SysCommand(f'zfs snapshot {self.name}@{index}')

		return Snapshot(name=f"{self.name}@{index}")
