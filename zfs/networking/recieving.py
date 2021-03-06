import ipaddress
import select
import socket
import struct
import zlib
import binascii

from ..models import (
	ZFSChunk,
	ZFSPool,
	ZFSSnapshotDelta,
	ZFSEndFrame,
	Ethernet,
	IPv4,
	UDP
)
from ..storage import storage
from .common import promisc, ETH_P_ALL, SOL_PACKET, PACKET_AUXDATA

def ip_to_bytes(addr):
	if addr == '':
		return b''

	addr = b''
	for block in str(addr).split('.'):
		addr += struct.pack('B', block)

	return addr

class Reciever:
	def __init__(self, addr, port, buffer_size=None):
		if buffer_size is None:
			buffer_size = storage['arguments'].framesize

		self.addr = ip_to_bytes(addr)
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
	
				# for fileno, event in self.poller.poll(0.025): # Retry up to 1 second
				data, auxillary_data_raw, flags, addr = self.socket.recvmsg(self.buffer_size, socket.CMSG_LEN(self.buffer_size))
					# data, sender = self.socket.recvfrom(self.buffer_size)
				# 	data_recieved = True

				for result in self.unpack_frame(data):
					yield result

					# transfer_id = self.recieve_frame(data, sender)
					# if transfer_id:
					# 	yield {
					# 		'information' : self.transfers[transfer_id]['information'],
					# 		'data' : self.transfers[transfer_id]['data'].pop(0)
					# 	}

	def unpack_frame(self, data):
		if len(data[:42]) < 42:
			"""
			Not a valid IPv4 packet so no point in parsing.
			"""
			return None

		segments = struct.unpack("!6s6s2s12s4s4sHHHH", data[0:42])

		ethernet_segments = segments[0:3]

		# ip_source, ip_dest = [
		# 	ipaddress.ip_address(x) for x in (
		# 		socket.inet_ntoa(section) for section in segments[4:6]
		# 	)
		# ]
		ip_source, ip_dest = segments[4:6]

		# source_port, destination_port, udp_payload_len, udp_checksum = struct.unpack("!HHHH", data[34:42])
		source_port, destination_port, udp_payload_len, udp_checksum = segments[6:10]

		#ethernet_segments = struct.unpack("!6s6s2s", data[0:14])
		# mac_dest, mac_source = (binascii.hexlify(mac) for mac in ethernet_segments[:2])
		mac_dest, mac_source = ethernet_segments[:2]
		
		# frame = Ethernet(
		# 	source=':'.join(mac_source[i:i + 2].decode('UTF-8') for i in range(0, len(mac_source), 2)),
		# 	destination=':'.join(mac_dest[i:i + 2].decode('UTF-8') for i in range(0, len(mac_dest), 2)),
		# 	payload_type=binascii.hexlify(ethernet_segments[2]),
		# 	payload=IPv4(
		# 		source=ip_source,
		# 		destination=ip_dest,
		# 		payload=UDP(
		# 			source=source_port,
		# 			destination=destination_port,
		# 			length=udp_payload_len,
		# 			checksum=udp_checksum,
		# 			payload=data[42:42 + udp_payload_len]
		# 		)
		# 	)
		# )

		# if frame.payload.payload.destination == self.port and (self.addr == '' or self.addr == frame.payload.destination):
		if destination_port == self.port and (self.addr == b'' or self.addr == ip_dest):
			# data = frame.payload.payload.payload
			if any(data := data[42:42 + udp_payload_len]):

				frame_type = struct.unpack('B', data[0:1])[0]
				if frame_type == 1:
					"""
					Frame type 2 is a pre-flight frame of a full sync of a dataset.
					This frame will contain:
						* Transfer ID (a session if you will)
						* Volume/Dataset name
					"""
					transfer_id = struct.unpack('B', data[1:2])[0]
					volume_name_len = struct.unpack('B', data[2:3])[0]
					volume = data[3:3 + volume_name_len]

					yield [frame_type, transfer_id, volume.decode('UTF-8')]

					# yield ZFSPool(
					# 	transfer_id=transfer_id,
					# 	name=volume.decode('UTF-8')
					# )
				elif frame_type == 2:
					"""
					Frame type 1 is a pre-flight frame of a delta between two snapshots.
					This frame will contain:
						* Transfer ID (a session if you will)
						* Volume/Dataset name
					"""
					transfer_id = struct.unpack('B', data[1:2])[0]
					volume_name_len = struct.unpack('B', data[2:3])[0]
					volume = data[3:3 + volume_name_len]

					yield [frame_type, transfer_id, volume.decode('UTF-8')]

					# yield ZFSSnapshotDelta(
					# 	transfer_id=transfer_id,
					# 	name=volume.decode('UTF-8')
					# )
				elif frame_type == 3:
					"""
					Fram type 3 is chunk data for a given session.
					The given session is defined based on the
					pre-flight frame that was sent to initate the session.
					"""
					transfer_id = struct.unpack('B', data[1:2])[0]
					frame_index = struct.unpack('B', data[2:3])[0]
					checksum = struct.unpack('I', data[3:7])[0]
					length = struct.unpack('H', data[7:9])[0]
					recieved_data = data[9:9 + length]
					
					previous_checksum = struct.unpack('I', data[9 + length:9 + length + 4])[0]

					yield [frame_type, transfer_id, frame_index, checksum, length, recieved_data, previous_checksum]

					# yield ZFSChunk(
					# 	transfer_id=transfer_id,
					# 	frame_index=frame_index,
					# 	checksum=checksum,
					# 	length=length,
					# 	data=recieved_data,
					# 	previous_checksum=previous_checksum
					# )

				elif frame_type == 4:
					"""
					Frame type 3 is and END frame to a given transmission.
					"""
					yield [frame_type, struct.unpack('B', data[1:2])[0]]
					# yield ZFSEndFrame(
					# 	transfer_id=struct.unpack('B', data[1:2])[0]
					# )

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
