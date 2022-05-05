import pydantic
import ipaddress
import random
import struct
import socket
from typing import Union, Type

class Ethernet_IPv4:
	pass

class Ethernet_Unknown:
	def __len__(self):
		return -1

class NetNodeAddress(pydantic.BaseModel):
	mac_address :pydantic.constr(to_lower=True, min_length=17, max_length=17)
	ipv4_address :ipaddress.IPv4Address

	class Config:
		arbitrary_types_allowed = True

class NetNode(pydantic.BaseModel):
	interface: pydantic.constr(to_lower=True, min_length=1, max_length=17)
	source: NetNodeAddress
	destination: NetNodeAddress
	udp_port: int

	class Config:
		arbitrary_types_allowed = True
	
class UDP(pydantic.BaseModel):
	destination :int
	payload :bytes
	source :int = random.randint(32768, 60999)
	checksum :int = 0
	# source_addr :ipaddress.IPv4Address
	# dest_addr :ipaddress.IPv4Address

	@property
	def _checksum(self):
		# pseudo_header = struct.pack('!BBH', 0, socket.IPPROTO_UDP , len(self))
		# pseudo_header = self.pack_address(self.source_addr) + self.pack_address(self.dest_addr) + pseudo_header

		# udp_header = struct.pack('>H', self.source)
		# udp_header += struct.pack('>H', self.destination)
		# udp_header += struct.pack('>H', len(self))
		# udp_header += struct.pack('>H', 0)

		# data = pseudo_header + udp_header + self.payload

		# checksum = 0
		# data_len = len(data)
		# if (data_len % 2):
		# 	data_len += 1
		# 	data += struct.pack('!B', 0)
		
		# for i in range(0, data_len, 2):
		# 	w = (data[i] << 8) + (data[i + 1])
		# 	checksum += w

		# checksum = (checksum >> 16) + (checksum & 0xFFFF)
		# checksum = ~checksum & 0xFFFF
		# return checksum
		return 0

	def __len__(self):
		return 8 + len(self.payload)

	def pack_address(self, address :ipaddress.IPv4Address):
		return b''.join([struct.pack('B', int(addr_part)) for addr_part in str(address).split('.')])

	def pack(self):
		frame = struct.pack('>H', self.source)
		frame += struct.pack('>H', self.destination)
		frame += struct.pack('>H', len(self))
		frame += struct.pack('>H', self.checksum)
		frame += self.payload

		return frame	

class IPv4(pydantic.BaseModel):
	source :ipaddress.IPv4Address
	destination :ipaddress.IPv4Address
	payload :Union[UDP]
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
		header += struct.pack('>H', self.reserved_bit << 8+7 | self.do_not_fragment << 8+6 | self.more_fragments << 8+5 | self.fragment_offset)
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

class Ethernet(pydantic.BaseModel):
	source: pydantic.constr(to_lower=True, min_length=17, max_length=17)
	destination: pydantic.constr(to_lower=True, min_length=17, max_length=17)
	payload: Union[IPv4]

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
