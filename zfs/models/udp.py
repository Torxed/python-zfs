# import pydantic
# import random
# import struct
# import ipaddress

# class UDP(pydantic.BaseModel):
# 	destination :int
# 	payload :bytes
# 	source :int = random.randint(32768, 60999)
# 	checksum :int = 0
# 	# source_addr :ipaddress.IPv4Address
# 	# dest_addr :ipaddress.IPv4Address

# 	@property
# 	def _checksum(self):
# 		# pseudo_header = struct.pack('!BBH', 0, socket.IPPROTO_UDP , len(self))
# 		# pseudo_header = self.pack_address(self.source_addr) + self.pack_address(self.dest_addr) + pseudo_header

# 		# udp_header = struct.pack('>H', self.source)
# 		# udp_header += struct.pack('>H', self.destination)
# 		# udp_header += struct.pack('>H', len(self))
# 		# udp_header += struct.pack('>H', 0)

# 		# data = pseudo_header + udp_header + self.payload

# 		# checksum = 0
# 		# data_len = len(data)
# 		# if (data_len % 2):
# 		# 	data_len += 1
# 		# 	data += struct.pack('!B', 0)
		
# 		# for i in range(0, data_len, 2):
# 		# 	w = (data[i] << 8) + (data[i + 1])
# 		# 	checksum += w

# 		# checksum = (checksum >> 16) + (checksum & 0xFFFF)
# 		# checksum = ~checksum & 0xFFFF
# 		# return checksum
# 		return 0

# 	def __len__(self):
# 		return 8 + len(self.payload)

# 	def pack_address(self, address :ipaddress.IPv4Address):
# 		return b''.join([struct.pack('B', int(addr_part)) for addr_part in str(address).split('.')])

# 	def pack(self):
# 		frame = struct.pack('>H', self.source)
# 		frame += struct.pack('>H', self.destination)
# 		frame += struct.pack('>H', len(self))
# 		frame += struct.pack('>H', self.checksum)
# 		frame += self.payload

# 		return frame
