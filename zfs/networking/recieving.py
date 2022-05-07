import ipaddress
import select
import socket
import struct
import zlib
import binascii

from ..models import ZFSFrame, ZFSSnapshotChunk, Ethernet, IPv4, UDP
from ..storage import storage
from .common import promisc, ETH_P_ALL, SOL_PACKET, PACKET_AUXDATA

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

class Reciever:
	def __init__(self, addr, port, buffer_size=1392):
		self.addr = addr
		self.port = port
		self.socket = None
		self.buffer_size = buffer_size

		self.transfers = {

		}

	def __enter__(self):
		self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
		self.socket.setsockopt(SOL_PACKET, PACKET_AUXDATA, 1)
		promisciousMode = promisc(self.socket, bytes(storage['arguments'].interface, 'UTF-8'))
		promisciousMode.on()

		self.poller = select.epoll()
		self.poller.register(self.socket.fileno(), select.EPOLLIN | select.EPOLLHUP)

		# self.socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
		# self.socket.setblocking(0)
		# self.socket.bind((self.addr, self.port))
		return self

	def __exit__(self, *args):
		if args[1]:
			print(args)

	def __iter__(self):
		if self.socket:

			data_recieved = None
			while data_recieved is None or data_recieved is True:
				if data_recieved:
					data_recieved = False
	
				for fileno, event in self.poller.poll(0.025): # Retry up to 1 second
					data, auxillary_data_raw, flags, addr = self.socket.recvmsg(65535, socket.CMSG_LEN(4096))
					print(addr, data)
					# data, sender = self.socket.recvfrom(self.buffer_size)
					data_recieved = True

					for result in self.unpack_frame(data):
						yield result

					# transfer_id = self.recieve_frame(data, sender)
					# if transfer_id:
					# 	yield {
					# 		'information' : self.transfers[transfer_id]['information'],
					# 		'data' : self.transfers[transfer_id]['data'].pop(0)
					# 	}

	def unpack_frame(self, data):
		print(data)
		ip_segments = struct.unpack("!12s4s4s", data[14:34])

		ip_source, ip_dest = [
			ipaddress.ip_address(x) for x in (
				socket.inet_ntoa(section) for section in ip_segments[1:3]
			)
		]

		source_port, destination_port, udp_payload_len, udp_checksum = struct.unpack("!HHHH", data[34:42])

		ethernet_segments = struct.unpack("!6s6s2s", data[0:14])
		mac_dest, mac_source = (binascii.hexlify(mac) for mac in ethernet_segments[:2])
		
		frame = Ethernet(
			source=':'.join(mac_source[i:i+2].decode('UTF-8') for i in range(0, len(mac_source), 2)),
			destination=':'.join(mac_dest[i:i+2].decode('UTF-8') for i in range(0, len(mac_dest), 2)),
			payload_type=binascii.hexlify(ethernet_segments[2]),
			payload=IPv4(
				source=ip_source,
				destination=ip_dest,
				payload=UDP(
					source=source_port,
					destination=destination_port,
					length=udp_payload_len,
					checksum=udp_checksum,
					payload=data[42:42+udp_payload_len]
				)
			)
		)

		if frame.payload.payload.destination == self.port and (self.addr == '' or self.addr == frame.payload.destination):
			data = frame.payload.payload.payload

			transfer_id = struct.unpack('B', data[0:1])[0]
			frame_index = struct.unpack('B', data[1:2])[0]
			checksum = struct.unpack('I', data[2:6])[0]
			length = struct.unpack('H', data[6:8])[0]
			recieved_data = data[8:8+length]
			
			# print(len(data), data)
			# print(data[0:1], transfer_id)
			# print(data[1:2], frame_index)
			# print(data[2:6], checksum)
			# print(data[6:8], length)
			# print('DATA:', data[8:8+length])
			# print(data[8+length:8+length+4])

			previous_checksum = struct.unpack('I', data[8+length:8+length+4])[0]

			yield ZFSSnapshotChunk(
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