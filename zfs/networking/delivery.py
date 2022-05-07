import ipaddress
import socket
import zlib
from ..models import Ethernet, IPv4, UDP, ZFSFrame
from ..storage import storage
from .common import promisc, ETH_P_ALL, SOL_PACKET, PACKET_AUXDATA


def deliver(transfer_id, stream, addressing, on_send=None, resend_buffer=2, chunk_length=692):
	# sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	transmission_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
	transmission_socket.setsockopt(SOL_PACKET, PACKET_AUXDATA, 1)
	promisciousMode = promisc(transmission_socket, bytes(storage['arguments'].interface, 'UTF-8'))
	promisciousMode.on()

	aux_data = [(263, 8, b'\x01\x00\x00\x00<\x00\x00\x00<\x00\x00\x00\x00\x00\x0e\x00\x00\x00\x00\x00')]
	flags = 0

	frame_index = 0
	previous_data = None

	stream_information = stream.info_struct(transfer_id)
	for resend in range(resend_buffer):
		frame = Ethernet(
			source=str(addressing.source.mac_address),
			destination=str(addressing.destination.mac_address),
			payload_type=8,
			payload = IPv4(
				source=addressing.source.ipv4_address,
				destination=addressing.destination.ipv4_address,
				payload=UDP(destination=addressing.udp_port, payload=stream_information) #, source_addr=addressing.source.ipv4_address, dest_addr=addressing.destination.ipv4_address)
			)
		)
		transmission_socket.sendmsg([frame.pack()], aux_data, flags, (storage['arguments'].interface, addressing.udp_port))

	while (data := stream.read(chunk_length)):
		# transfer_id :int # B
		# frame_index :int # B
		# checksum :int # I
		# length :int # H
		# data :bytes
		# previous_checksum :int # I

		payload = ZFSFrame(
			transfer_id = transfer_id,
			frame_index = frame_index,
			data = data,
			previous_checksum = zlib.crc32(previous_data if previous_data else b'')
		)

		frame = Ethernet(
			source=str(addressing.source.mac_address),
			destination=str(addressing.destination.mac_address),
			payload_type=8,
			payload = IPv4(
				source=addressing.source.ipv4_address,
				destination=addressing.destination.ipv4_address,
				payload=UDP(destination=addressing.udp_port, payload=payload.pack()) #, source_addr=addressing.source.ipv4_address, dest_addr=addressing.destination.ipv4_address)
			)
		)

		print(f'Sending frame: {repr(frame)}')

		if on_send:
			frame = on_send(frame)

		# socket.sendto(frame.pack(), addressing.destination.ipv4_address)
		# socket.sendmsg(frame.pack(), response.frame.request_frame.auxillary_data_raw, response.frame.request_frame.flags, (response.frame.request_frame.server.configuration.interface, 68))

		transmission_socket.sendmsg([frame.pack()], aux_data, flags, (storage['arguments'].interface, addressing.udp_port))
		print(f"Sent: {frame.pack()}")
		
		previous_data = data
		frame_index += 1

	promisciousMode.off()