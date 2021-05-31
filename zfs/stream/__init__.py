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

def unpack_data(frame):
	length = struct.unpack('H', frame[6:8])[0]
	data_position = length+8
	return {
		"transfer_id" : struct.unpack('B', frame[0:1])[0],
		"index" : struct.unpack('B', frame[1:2])[0],
		"crc_data" : struct.unpack('I', frame[2:6])[0],
		"data_len" : length,
		"data" : frame[8:data_position],
		"previous_data" : frame[data_position:]
	}

def deliver(stream, to, on_send=None):
	assert len(to) == 2 # IP, port
	assert type(to[0]) is str and type(to[1]) is int
	assert ipaddress.ip_address(to[0])

	sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	transfer_id = 1
	frame_index = 0
	previous_data = None
	while (data := stream.read(1392)):
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

					snapshot = self.recieve_frame(data, sender)


	def recieve_frame(self, frame, sender):
		data = unpack_data(frame)
	#	"transfer_id"
	#	"index"
	#	"crc_data"
	#	"data_len"
	#	"data"
	#	"previous_data"
#		print("CRC:", zlib.crc32(data['data']) & 0xffffffff, "vs", "CRC Target:", data['crc_data'])
#		print("Length:",  data['data_len'])
#		print(frame)

		print("Recieved frame:", data['index'])
		print("CRC:", zlib.crc32(data['data']) & 0xffffffff, "vs", "CRC Target:", data['crc_data'])
		print(f"Data (20): {data['data'][:30]}...{data['data'][-30:]}")
#		print(f"Data: {data['data']}")

		if not data['transfer_id'] in self.transfers:
			self.transfers[data['transfer_id']] = []

		if zlib.crc32(data['data']) & 0xffffffff != data['crc_data']:
			raise KeyError("Broken frame!", len(data['data']), zlib.crc32(data['data']) & 0xffffffff, data['crc_data'])

		print(f"Frame {data['index']} was transferred successfully!")
		self.transfers[data['transfer_id']].append(data)

