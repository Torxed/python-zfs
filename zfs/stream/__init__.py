import ipaddress
import select
import socket
import struct
import zlib

def structure_data(transfer_id, data, index):
	return (
			struct.pack('B', transfer_id)
			+struct.pack('B', index)
			+struct.pack('I', zlib.crc32(data) & 0xffffffff)
			+struct.pack('H', len(data))
			+data
	)

def deliver(stream, to):
	assert len(to) == 2 # IP, port
	assert type(to[0]) is str and type(to[1]) is int
	assert ipaddress.ip_address(to[0])

	sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	transfer_id = 1
	frame_index = 0
	while (data := stream.read(1024)):
		sender.sendto(structure_data(transfer_id, data, frame_index), to)
		sender.sendto(structure_data(transfer_id, data, frame_index), to)
		frame_index += 1