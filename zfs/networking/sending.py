import socket
import zlib
import logging
import random
import struct
from ..models import Ethernet, IPv4, UDP, ZFSFrame
from ..storage import storage
from ..logger import log
from .common import promisc, ETH_P_ALL	, SOL_PACKET, PACKET_AUXDATA

def send(stream, addressing, on_send=None, resend_buffer=2, chunk_length=None):
	if chunk_length is None:
		# Ethernet/IP/UDP headers are 42 byte (estimation)
		chunk_length = storage['arguments'].framesize -55

	# sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	transmission_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
	transmission_socket.setsockopt(SOL_PACKET, PACKET_AUXDATA, 1)
	promisciousMode = promisc(transmission_socket, bytes(storage['arguments'].interface, 'UTF-8'))
	promisciousMode.on()

	aux_data = [(263, 8, b'\x01\x00\x00\x00<\x00\x00\x00<\x00\x00\x00\x00\x00\x0e\x00\x00\x00\x00\x00')]
	flags = 0

	frame_index = 0
	previous_data = None

	stream_information = stream.pre_flight_info
	log(f"Telling reciever to set up {repr(stream)}, resending this {resend_buffer} time(s)", fg="gray", level=logging.INFO)
	for resend in range(resend_buffer):
		frame = Ethernet(
			source=str(addressing.source.mac_address),
			destination=str(addressing.destination.mac_address),
			payload_type=8,
			payload=IPv4(
				source=addressing.source.ipv4_address,
				destination=addressing.destination.ipv4_address,
				payload=UDP(destination=addressing.udp_port, payload=stream_information)
			)
		)
		transmission_socket.sendmsg([frame.pack()], aux_data, flags, (storage['arguments'].interface, addressing.udp_port))

	mac_destination = b''.join([struct.pack('B', int(mac_part, 16)) for mac_part in str(addressing.destination.mac_address).split(':')])
	mac_source = b''.join([struct.pack('B', int(mac_part, 16)) for mac_part in str(addressing.source.mac_address).split(':')])
	mac_frame_type = struct.pack('H', 8)

	mac_header = mac_destination + mac_source + mac_frame_type

	DSC, ECN, reserved_bit = 0, 0, 0
	do_not_fragment, more_fragments, fragment_offset = 1, 0, 0

	version_and_header_length = struct.pack('B', 4 << 4 | 5)
	DSC_ECN = struct.pack('B', DSC << 4 | ECN)
	identification = struct.pack('>H', random.randint(0, 65535))
	fragmentation = struct.pack('>H', reserved_bit << 8 + 7 | do_not_fragment << 8 + 6 | more_fragments << 8 + 5 | fragment_offset)
	ttl = struct.pack('B', 64)
	protocol = struct.pack('B', 17)
	checksum = struct.pack('>H', 0)

	ip_source = b''.join([struct.pack('B', int(addr_part)) for addr_part in str(addressing.source.ipv4_address).split('.')])
	ip_destination = b''.join([struct.pack('B', int(addr_part)) for addr_part in str(addressing.destination.ipv4_address).split('.')])

	udp_source = struct.pack('>H', random.randint(32768, 60999))
	udp_destination = struct.pack('>H', addressing.udp_port)
	udp_checksum = struct.pack('>H', 0)

	while (data := stream.read(chunk_length)):
		# transfer_id :int # B
		# frame_index :int # B
		# checksum :int # I
		# length :int # H
		# data :bytes
		# previous_checksum :int # I

		payload = struct.pack('!BB', stream.transfer_id, frame_index % 255) + data + struct.pack('I', zlib.crc32(previous_data if previous_data else b''))

		# payload = ZFSFrame(
		# 	transfer_id=stream.transfer_id,
		# 	frame_index=frame_index % 255,
		# 	data=data,
		# 	previous_checksum=zlib.crc32(previous_data if previous_data else b'')
		# )

		# log(f'Sending chunk: {repr(payload)}', level=logging.INFO, fg="orange")

		udp_length = len(payload)

		ethernet = mac_header
		ipv4 = version_and_header_length
		ipv4 += DSC_ECN
		ipv4 += struct.pack('>H', 20 + 8 + udp_length) # 20 = IP Length, 8 = UDP length, len(payload) = data
		ipv4 += identification
		ipv4 += fragmentation
		ipv4 += ttl
		ipv4 += protocol
		ipv4 += checksum
		ipv4 += ip_source
		ipv4 += ip_destination
		udp = udp_source
		udp += udp_destination
		udp += struct.pack('>H', udp_length)
		udp += udp_checksum
		udp += payload

		frame = ethernet + ipv4 + udp
		# frame = Ethernet(
		# 	source=str(addressing.source.mac_address),
		# 	destination=str(addressing.destination.mac_address),
		# 	payload_type=8,
		# 	payload=IPv4(
		# 		source=addressing.source.ipv4_address,
		# 		destination=addressing.destination.ipv4_address,
		# 		payload=UDP(destination=addressing.udp_port, payload=payload.pack())
		# 	)
		# )

		# log(f'Sending frame: {repr(frame)}', fg="green", level=logging.INFO)

		if on_send:
			frame = on_send(frame)

		# socket.sendto(frame.pack(), addressing.destination.ipv4_address)
		# socket.sendmsg(frame.pack(), response.frame.request_frame.auxillary_data_raw, response.frame.request_frame.flags, (response.frame.request_frame.server.configuration.interface, 68))

		transmission_socket.sendmsg([frame], aux_data, flags, (storage['arguments'].interface, addressing.udp_port))
		
		previous_data = data
		frame_index += 1

	log(f"Telling reciever that we are finished with {repr(stream)}, resending this {resend_buffer} time(s)", fg="green", level=logging.INFO)
	for resend in range(resend_buffer):
		frame = Ethernet(
			source=str(addressing.source.mac_address),
			destination=str(addressing.destination.mac_address),
			payload_type=8,
			payload=IPv4(
				source=addressing.source.ipv4_address,
				destination=addressing.destination.ipv4_address,
				payload=UDP(destination=addressing.udp_port, payload=stream.end_frame)
			)
		)
		transmission_socket.sendmsg([frame.pack()], aux_data, flags, (storage['arguments'].interface, addressing.udp_port))

	promisciousMode.off()
