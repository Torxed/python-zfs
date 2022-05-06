import pathlib
import argparse
import logging
import ipaddress

from .storage import *
from .logger import log

__version__ = '0.0.1.dev1'

parser = argparse.ArgumentParser()
# General library options, that will affect anything surrounding python-zfs
parser.add_argument("--interface", type=str, nargs="?", help="Which interface should we send the ZFS stream on.")
# parser.add_argument("--src-ip", default=None, type=str, nargs="?", help="Which source IP should we be sending as (default will autodetect --interface first IP).")
parser.add_argument("--verbosity-level", default='DEBUG', type=str, nargs='?', help="Sets the lowest threashold for log messages, according to https://docs.python.org/3/library/logging.html#logging-levels")
parser.add_argument("--locale", default="C", type=str, nargs="?", help="Sets the locale of subshells executed.")
parser.add_argument("--log-dir", default=pathlib.Path("./").resolve(), type=pathlib.Path, nargs="?", help="Sets the destination of where to save logs.")
parser.add_argument("--debug", default=False, action="store_true", help="Turns on debugging output.")

# Module specific options
# TODO: Move these into __main__.py to not cause confusion
group.add_argument("--destination-ip", nargs="?", type=ipaddress.IPv4address, help="Which IP to send delta or a full sync.")
group.add_argument("--destination-mac", nargs="?", type=ipaddress.IPv4address, help="Which MAC to send delta or a full sync.")
group.add_argument("--source-ip", nargs="?", type=ipaddress.IPv4address, help="Which IP to send as (can be an existing or a spoofed one).")
group.add_argument("--source-mac", nargs="?", type=ipaddress.IPv4address, help="Which MAC to send as (can be an existing or spoofed one).")
group.add_argument("--udp-port", nargs="?", type=ipaddress.IPv4address, help="Which UDP port to send to.")

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument("--full-sync", default=False, action="store_true", help="Performs a full sync and transfer of a pool/dataset.")
group.add_argument("--send-delta", default=False, action="store_true", help="Sends a delta between two snapshots of a pool/dataset.")
group.add_argument("--snapshot", default=False, action="store_true", help="Takes a snapshot of a pool/dataset.")

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument("--pool", nargs="?", type=str, help="Defines which pool to perform the action on.")
group.add_argument("--delta-start", nargs="?", type=str, help="Which is the source of the delta (the starting point of the delta).")
group.add_argument("--delta-end", nargs="?", type=str, help="Which is the end of the delta.")


storage['arguments'], unknowns = parser.parse_known_args()
storage['version'] = __version__

match storage['arguments'].verbosity_level.lower():
	case 'critical':
		storage['arguments'].verbosity_level = logging.CRITICAL
	case 'error':
		storage['arguments'].verbosity_level = logging.ERROR
	case 'warning':
		storage['arguments'].verbosity_level = logging.WARNING
	case 'info':
		storage['arguments'].verbosity_level = logging.INFO
	case 'debug':
		storage['arguments'].verbosity_level = logging.DEBUG
	case 'noset':
		storage['arguments'].verbosity_level = logging.NOSET

from .general import *
from .zfs import *
from .models import *