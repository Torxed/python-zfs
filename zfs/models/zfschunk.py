import pydantic
import zlib

class ZFSChunk(pydantic.BaseModel):
	transfer_id :int # B
	frame_index :int # B
	checksum :int # I
	length :int # H
	data :bytes
	previous_checksum :int # I

	# @pydantic.validator('*')
	# def checksum(cls, value):
	# 	return value

	@property
	def id(self):
		return self.transfer_id

	def __repr__(self) -> str:
		return (
			f"ZFSChunk("
			+ f"transfer_id={self.transfer_id}"
			+ f", frame_index={self.frame_index}"
			+ f", checksum={self.checksum} ({zlib.crc32(self.data) & 0xffffffff == self.checksum})"
			+ f", length={self.length}"
			+ f", data={zlib.compress(self.data)!r}"
			+ f", previous_checksum={self.previous_checksum}"
		)
