import ipaddress
import ctypes
import socket
import fcntl
import zlib
from ..models import Ethernet, IPv4, UDP, ZFSFrame
from ..storage import storage

# ethernet_segments = struct.unpack("!6s6s2s", data[0:14])
# mac_dest, mac_source = (binascii.hexlify(mac) for mac in ethernet_segments[:2])
# return Ethernet(
# 	source=':'.join(mac_source[i:i+2].decode('UTF-8') for i in range(0, len(mac_source), 2)),
# 	destination=':'.join(mac_dest[i:i+2].decode('UTF-8') for i in range(0, len(mac_dest), 2)),
# 	payload_type=binascii.hexlify(ethernet_segments[2])
# )

class tpacket_auxdata(ctypes.Structure):
	_fields_ = [
		("tp_status", ctypes.c_uint),
		("tp_len", ctypes.c_uint),
		("tp_snaplen", ctypes.c_uint),
		("tp_mac", ctypes.c_ushort),
		("tp_net", ctypes.c_ushort),
		("tp_vlan_tci", ctypes.c_ushort),
		("tp_padding", ctypes.c_ushort),
	]

## This is a ctype structure that matches the
## requirements to set a socket in promisc mode.
## In all honesty don't know where i found the values :)
class ifreq(ctypes.Structure):
		_fields_ = [("ifr_ifrn", ctypes.c_char * 16),
					("ifr_flags", ctypes.c_short)]

class promisc():
	IFF_PROMISC = 0x100
	SIOCGIFFLAGS = 0x8913
	SIOCSIFFLAGS = 0x8914

	def __init__(self, s, interface=b'ens33'):
		self.s = s
		self.fileno = s.fileno()
		self.interface = interface
		self.ifr = ifreq()

	def on(self):
		## -- Set up promisc mode:
		## 


		self.ifr.ifr_ifrn = self.interface

		fcntl.ioctl(self.fileno, self.SIOCGIFFLAGS, self.ifr)
		self.ifr.ifr_flags |= self.IFF_PROMISC

		fcntl.ioctl(self.fileno, self.SIOCSIFFLAGS, self.ifr)
		## ------------- DONE

	def off(self):
		## Turn promisc mode off:
		self.ifr.ifr_flags &= ~self.IFF_PROMISC
		fcntl.ioctl(self.fileno, self.SIOCSIFFLAGS, self.ifr)
		## ------------- DONE

def deliver(transfer_id, stream, addressing, on_send=None, resend_buffer=2):
	# sender = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	ETH_P_ALL = 0x0003
	SOL_PACKET = 263
	PACKET_AUXDATA = 8
	transmission_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(ETH_P_ALL))
	transmission_socket.setsockopt(SOL_PACKET, PACKET_AUXDATA, 1)
	promisciousMode = promisc(transmission_socket, bytes(storage['arguments'].interface, 'UTF-8'))
	promisciousMode.on()

	frame_index = 0
	previous_data = None

	stream_information = stream.info_struct(transfer_id)
	for resend in range(resend_buffer):
		transmission_socket.sendto(stream_information, (storage['arguments'].interface, addressing.udp_port))

	while (data := stream.read(692)):
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
				payload=UDP(destination=addressing.udp_port, payload=payload.pack())
			)
		)

		print(f'Sending frame: {repr(frame)}')

		if on_send:
			frame = on_send(frame)

		# socket.sendto(frame.pack(), addressing.destination.ipv4_address)
		# socket.sendmsg(frame.pack(), response.frame.request_frame.auxillary_data_raw, response.frame.request_frame.flags, (response.frame.request_frame.server.configuration.interface, 68))
		transmission_socket.sendmsg(frame.pack(), (storage['arguments'].interface, addressing.udp_port))
		
		previous_data = data
		frame_index += 1

	promisciousMode.off()