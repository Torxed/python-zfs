import pydantic
import struct
import typing
from .ipv4 import IPv4

class Ethernet(pydantic.BaseModel):
	source: pydantic.constr(to_lower=True, min_length=17, max_length=17)
	destination: pydantic.constr(to_lower=True, min_length=17, max_length=17)
	payload: typing.Union[IPv4]

	class Config:
		arbitrary_types_allowed = True
		smart_union = True

	@property
	def payload_type(self):
		if type(self.payload) == IPv4:
			return 8

	def pack(self):
		frame = b''.join([struct.pack('B', int(mac_part, 16)) for mac_part in self.destination.split(':')])
		frame += b''.join([struct.pack('B', int(mac_part, 16)) for mac_part in self.source.split(':')])
		frame += struct.pack('H', self.payload_type)
		frame += self.payload.pack()

		return frame