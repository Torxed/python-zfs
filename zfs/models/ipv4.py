import pydantic
import ipaddress
import random
import struct
import typing
from .udp import UDP

class IPv4(pydantic.BaseModel):
	source :ipaddress.IPv4Address
	destination :ipaddress.IPv4Address
	payload :typing.Union[UDP]
	# Sane defaults other than source and destination:
	protocol :int = 17 # 6 = TCP, 17 = UDP
	DSC :int = 0 # Differentiated Service Codepoint, 0 = default
	ECN :int = 0 # Explicit Congestion Notification, 0 = Not ECN-Capable Transport
	identification :int = random.randint(0, 65535) # Each frame is unique anyway
	ttl :int = 64
	reserved_bit :int = 0 # Always zero
	do_not_fragment :int = 1 # We don't want to fragment

	@property
	def header_length(self):
		"""
		Not sure how IPv4 headers work in this regard.
		0100 .... = version
		.... 0101 = header length = 5, but 5 here means 20?
		"""
		return 5 # len(self.pack_headers()) +1

	@property
	def length(self):
		return 20 + len(self.payload)

	@property
	def version(self):
		# To create the 4 high bits of the version
		return 4 << 4

	@property
	def more_fragments(self):
		if self.do_not_fragment == 0:
			# TODO: Only return 1 if we have trailing fragments.a
			return 1
		else:
			return 0
	
	@property
	def fragment_offset(self):
		return 0
	
	@property
	def checksum(self):
		# Calculate...
		return 0
	
	def pack_address(self, address :ipaddress.IPv4Address):
		return b''.join([struct.pack('B', int(addr_part)) for addr_part in str(address).split('.')])

	def pack_headers(self):
		header = struct.pack('B', self.DSC << 4 | self.ECN)
		header += struct.pack('>H', self.length)
		header += struct.pack('>H', self.identification)
		header += struct.pack('>H', self.reserved_bit << 8 + 7 | self.do_not_fragment << 8 + 6 | self.more_fragments << 8 + 5 | self.fragment_offset)
		header += struct.pack('B', self.ttl)
		header += struct.pack('B', self.protocol)
		header += struct.pack('>H', self.checksum)
		header += self.pack_address(self.source)
		header += self.pack_address(self.destination)

		return header

	def pack(self):
		frame = struct.pack('B', self.version | self.header_length)
		frame += self.pack_headers()
		frame += self.payload.pack()

		return frame
