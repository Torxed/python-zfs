import ctypes
import fcntl

ETH_P_ALL = 0x0003
SOL_PACKET = 263
PACKET_AUXDATA = 8

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

# This is a ctype structure that matches the
# requirements to set a socket in promisc mode.
# In all honesty don't know where i found the values :)
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
		# -- Set up promisc mode:

		self.ifr.ifr_ifrn = self.interface

		fcntl.ioctl(self.fileno, self.SIOCGIFFLAGS, self.ifr)
		self.ifr.ifr_flags |= self.IFF_PROMISC

		fcntl.ioctl(self.fileno, self.SIOCSIFFLAGS, self.ifr)
		# ------------- DONE

	def off(self):
		# Turn promisc mode off:
		self.ifr.ifr_flags &= ~self.IFF_PROMISC
		fcntl.ioctl(self.fileno, self.SIOCSIFFLAGS, self.ifr)
		# ------------- DONE
