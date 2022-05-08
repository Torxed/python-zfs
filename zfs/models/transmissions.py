import struct
import zlib
import pydantic
from typing import Optional

class ZFSFrame(pydantic.BaseModel):
	transfer_id :int # B
	frame_index :int # B
	# checksum :int # I
	# length :int # H
	data :bytes
	previous_checksum :Optional[int] = 0 # I

	@property
	def id(self):
		return self.transfer_id

	def pack(self):
		return (
			struct.pack('B', 3) # We are a data chunk
			+struct.pack('B', self.transfer_id)
			+struct.pack('B', self.frame_index)
			+struct.pack('I', self.checksum)
			+struct.pack('H', self.length)
			+self.data
			+struct.pack('I', self.previous_checksum if self.previous_checksum else 0)
		)

	def __repr__(self) -> str:
		return (
			f"ZFSFrame("
			+f"transfer_id={self.transfer_id}|{struct.pack('B', self.transfer_id)}"
			+f", frame_index={self.frame_index}|{struct.pack('B', self.frame_index)}"
			+f", .checksum={self.checksum}|{struct.pack('I', self.checksum)}"
			+f", .length={self.length}|{struct.pack('H', self.length)}"
			+f", data={self.data!r}"
			+f", previous_checksum={self.previous_checksum}|{struct.pack('I', self.previous_checksum if self.previous_checksum else 0)})"
		)

	@property
	def length(self):
		return len(self.data)
	
	@property
	def checksum(self):
		return zlib.crc32(self.data) & 0xffffffff

class ZFSChunk(pydantic.BaseModel):
	transfer_id :int # B
	frame_index :int # B
	checksum :int # I
	length :int # H
	data :bytes
	previous_checksum :int # I

	@pydantic.validator('*')
	def checksum(cls, value):
		return value

	@property
	def id(self):
		return self.transfer_id

class ZFSFullDataset(pydantic.BaseModel):
	transfer_id :int # B
	name :str

	@property
	def id(self):
		return self.transfer_id

class ZFSSnapshotDelta(pydantic.BaseModel):
	transfer_id :int
	name :str

	@property
	def id(self):
		return self.transfer_id