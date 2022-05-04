import ipaddress
import select
import socket
import struct
import zlib

from .. import epoll, EPOLLIN, EPOLLHUP
from ..models import ZFSFrame, ZFSSnapshotChunk

# def structure_data(transfer_id, index, previous_data=None, data=None):
# 	return (
# 			struct.pack('B', transfer_id)
# 			+struct.pack('B', index)
# 			+struct.pack('I', zlib.crc32(data) & 0xffffffff if data else zlib.crc32(previous_data) & 0xffffffff)
# 			+struct.pack('H', len(data))
# 			+(data if data else b'')
# 			+(previous_data if previous_data else b'')
# 	)

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

def deliver(stream, to, on_send=None, resend_buffer=2):
	assert len(to) == 2 # IP, port
	assert type(to[0]) is str and type(to[1]) is int
	assert ipaddress.ip_address(to[0])

	sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

	transfer_id = 1
	frame_index = 0
	previous_data = None

	stream_information = stream.info_struct(transfer_id)
	for resend in range(resend_buffer):
		sender.sendto(stream_information, to)

	while (data := stream.read(692)):
		transfer_id :int # B
		frame_index :int # B
		checksum :int # I
		length :int # H
		data :bytes
		previous_checksum :int # I

		frame = ZFSFrame(
			transfer_id = transfer_id,
			frame_index = frame_index,
			data = data,
			previous_checksum = zlib.crc32(previous_data if previous_data else b'')
		)
		#frame = structure_data(transfer_id, frame_index, previous_data, data)
		print(f'Sending frame: {repr(frame)}')

		if on_send:
			frame = on_send(frame)

		sender.sendto(frame.pack(), to)
		
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

					frame = self.unpack_frame(data)

					# transfer_id = self.recieve_frame(data, sender)
					# if transfer_id:
					# 	yield {
					# 		'information' : self.transfers[transfer_id]['information'],
					# 		'data' : self.transfers[transfer_id]['data'].pop(0)
					# 	}

	def unpack_frame(self, data):

		transfer_id = struct.unpack('B', data[0:1])[0]
		frame_index = struct.unpack('B', data[1:2])[0]
		checksum = struct.unpack('I', data[2:6])[0]
		length = struct.unpack('H', data[6:8])[0]
		recieved_data = data[8:8+length]
		
		print(len(data), data)
		print(data[0:1], transfer_id)
		print(data[1:2], frame_index)
		print(data[2:6], checksum)
		print(data[6:8], length)
		print('DATA:', data[8:8+length])
		print(data[8+length:8+length+4])

		previous_checksum = struct.unpack('I', data[8+length:8+length+4])[0]

		return ZFSSnapshotChunk(
			transfer_id = transfer_id,
			frame_index = frame_index,
			checksum = checksum,
			length = length,
			data = recieved_data,
			previous_checksum = previous_checksum
		)

	def recieve_frame(self, frame, sender):
		if frame[0] == 0:
			# Informational frame for a snapshot (not delta) recieved (always starts with 0)
			from ..snapshots import Snapshot
			transfer_information = Snapshot.unpack_informational_frame(frame)

			if transfer_information['transfer_id'] not in self.transfers:
				self.transfers[transfer_information['transfer_id']] = {
					'information' :transfer_information,
					'snapshot' : 'origin',
					'data' : []
				}
		elif frame[0] == 1:
			from ..snapshots import Delta
			# Informational frame for a snapshot delta recieved (always starts with 1)
			transfer_information = Delta.unpack_informational_frame(frame)

			if transfer_information['transfer_id'] not in self.transfers:
				self.transfers[transfer_information['transfer_id']] = {
					'information' :transfer_information,
					'snapshot' : 'delta',
					'data' : []
				}

		elif frame[0] == 2:
			# We recieved a snapshot stream frame (first byte was 2)
			data = unpack_snapshot_frame(frame)

			if zlib.crc32(data['data']) & 0xffffffff != data['crc_data']:
				raise KeyError("Broken frame!", len(data['data']), zlib.crc32(data['data']) & 0xffffffff, data['crc_data'])

			if data['transfer_id'] not in self.transfers:
				raise KeyError(f"Missing transfer information for transfer: {data['transfer_id']}")

			self.transfers[data['transfer_id']]['data'].append(data)

			return data['transfer_id']