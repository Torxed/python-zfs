import ipaddress
import select
import socket
import struct
import zlib

from .. import epoll, EPOLLIN, EPOLLHUP

def structure_data(transfer_id, index, previous_data=None, data=None):
	return (
			struct.pack('B', transfer_id)
			+struct.pack('B', index)
			+struct.pack('I', zlib.crc32(data) & 0xffffffff if data else zlib.crc32(previous_data) & 0xffffffff)
			+struct.pack('H', len(data))
			+(data if data else b'')
			+(previous_data if previous_data else b'')
	)

def unpack_snapshot_frame(frame):
	HEADER_LENGTH = 8

	length = struct.unpack('H', frame[6:HEADER_LENGTH])[0]
	data_position = length # The header is 8 bytes
	
	return {
		"transfer_id" : struct.unpack('B', frame[0:1])[0],
		"index" : struct.unpack('B', frame[1:2])[0],
		"crc_data" : struct.unpack('I', frame[2:6])[0],
		"data_len" : length,
		"data" : frame[HEADER_LENGTH:HEADER_LENGTH+data_position],
		"previous_data" : frame[HEADER_LENGTH+data_position:]
	}

def unpack_informational_frame(frame):
	frame_type = struct.unpack('B', frame[0:1])[0] # 1 Byte
	transfer_id = struct.unpack('B', frame[1:2])[0] # 1 Byte
	crc32_info = struct.unpack('I', frame[2:6])[0] # 4 Bytes
	origin_name_length = struct.unpack('B', frame[6:7])[0] # Length of the snapshot origin name
	origin_name = frame[7:7+origin_name_length]
	destination_name_length = struct.unpack('B', frame[7+origin_name_length:7+origin_name_length+1])[0]
	destination_name = frame[7+origin_name_length+1:7+origin_name_length+1+destination_name_length]
	end_frame = 7+origin_name_length+1+destination_name_length

	if len(frame[end_frame:]):
		raise ValueError(f"Recieved to many bytes in informational frame: {len(frame[end_frame:])} bytes to many")

	if crc32_info != zlib.crc32(origin_name + destination_name) & 0xffffffff:
		raise ValueError(f"CRC32 does not match in the informational frame, most likely corrupt data.")

	return {
		"frame_type" : frame_type,
		"transfer_id" : transfer_id,
		"origin_name" : origin_name,
		"destination_name" : destination_name
	}

def info_struct(frame, transfer_id):
	origin = bytes(frame.origin, 'UTF-8')
	destination = bytes(frame.destination, 'UTF-8')
	return (
		struct.pack('B', 0)
		+struct.pack('B', transfer_id)
		+struct.pack('I', zlib.crc32(origin + destination) & 0xffffffff)
		+struct.pack('B', len(origin)) + origin
		+struct.pack('B', len(destination)) + destination
	)

def deliver(stream, to, on_send=None, resend_buffer=2):
	assert len(to) == 2 # IP, port
	assert type(to[0]) is str and type(to[1]) is int
	assert ipaddress.ip_address(to[0])

	sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

	transfer_id = 1
	frame_index = 0
	previous_data = None

	stream_information = info_struct(stream, transfer_id)
	for resend in range(resend_buffer):
		sender.sendto(stream_information, to)

	while (data := stream.read(1392)):
		print(f'Sending frame length: {len(data)}')
		frame = structure_data(transfer_id, frame_index, previous_data, data)

		if on_send:
			frame = on_send(frame)

		sender.sendto(frame, to)
		
		previous_data = data
		frame_index += 1

class Reciever:
	def __init__(self, addr, port, buffer_size=1392):
		self.addr = addr
		self.port = port
		self.socket = None
		self.buffer_size = buffer_size

		self.transfers = {

		}

	def __enter__(self):
		self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		self.socket.setblocking(0)
		self.socket.bind((self.addr, self.port))
		return self

	def __exit__(self, *args):
		print(args)

	def __iter__(self):
		if self.socket:
			poller = epoll()
			poller.register(self.socket.fileno(), EPOLLIN | EPOLLHUP)

			data_recieved = None
			while data_recieved is None or data_recieved is True:
				if data_recieved:
					data_recieved = False
	
				for fileno, event in poller.poll(0.025): # Retry up to 1 second
					data, sender = self.socket.recvfrom(self.buffer_size)
					data_recieved = True

					transfer_id = self.recieve_frame(data, sender)
					if transfer_id:
						yield {
							'information' : self.transfers[transfer_id]['information'],
							'data' : self.transfers[transfer_id]['data'].pop(0)
						}

	def recieve_frame(self, frame, sender):
		if frame[0] == 0:
			# Informational frame recieved (always starts with 0)
			transfer_information = unpack_informational_frame(frame)

			if transfer_information['transfer_id'] not in self.transfers:
				self.transfers[transfer_information['transfer_id']] = {
					'information' :transfer_information,
					'data' : []
				}
		else:
			# We recieved a snapshot frame (first byte was not 0, which means it's a transfer ID)
			data = unpack_snapshot_frame(frame)

			if zlib.crc32(data['data']) & 0xffffffff != data['crc_data']:
				raise KeyError("Broken frame!", len(data['data']), zlib.crc32(data['data']) & 0xffffffff, data['crc_data'])

			if data['transfer_id'] not in self.transfers:
				raise KeyError(f"Missing transfer information for transfer: {data['transfer_id']}")

			self.transfers[data['transfer_id']]['data'].append(data)

			return data['transfer_id']

