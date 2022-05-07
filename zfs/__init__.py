import pathlib
import argparse
import logging
import ipaddress

from .storage import *
from .logger import log

__version__ = '0.0.1.dev1'

parent = argparse.ArgumentParser(description="A ZFS utility and library to manage snapshots and send ZFS snapshots and deltas over a UDP stream.", add_help=False)

# General library options, that will affect anything surrounding python-zfs
parent.add_argument("--interface", type=str, nargs="?", help="Which interface should we send the ZFS stream on.")
# parser.add_argument("--src-ip", default=None, type=str, nargs="?", help="Which source IP should we be sending as (default will autodetect --interface first IP).")
parent.add_argument("--verbosity-level", default='DEBUG', type=str, nargs='?', help="Sets the lowest threashold for log messages, according to https://docs.python.org/3/library/logging.html#logging-levels")
parent.add_argument("--locale", default="C", type=str, nargs="?", help="Sets the locale of subshells executed.")
parent.add_argument("--log-dir", default=pathlib.Path("./").resolve(), type=pathlib.Path, nargs="?", help="Sets the destination of where to save logs.")
parent.add_argument("--debug", default=False, action="store_true", help="Turns on debugging output.")

storage['argparse'] = parent
storage['arguments'], unknowns = parent.parse_known_args()
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

from .general import SysCommandWorker, SysCommand 
from .models import (
	Snapshot,
	Namespace,
	Volume,
	ZFSFrame,
	ZFSSnapshotChunk,
	Ethernet_IPv4,
	Ethernet_Unknown,
	NetNodeAddress,
	NetNode,
	Ethernet,
	UDP,
	IPv4
)
from .snapshots import (
	Delta,
	DeltaReader,
	Snapshot,
	Image
)
from .list import (
	volumes,
	get_volume,
	snapshots,
	last_snapshots
)
from . import networking