import pathlib
import argparse
import logging

from .storage import *
from .logger import log

__version__ = '0.0.1.dev1'

parser = argparse.ArgumentParser()
parser.add_argument("--verbosity-level", default='DEBUG', type=str, nargs='?', help="Sets the lowest threashold for log messages, according to https://docs.python.org/3/library/logging.html#logging-levels")
parser.add_argument("--locale", default="C", type=str, nargs="?", help="Sets the locale of subshells executed.")
parser.add_argument("--log-dir", default=pathlib.Path("./").resolve(), type=pathlib.Path, nargs="?", help="Sets the destination of where to save logs.")
parser.add_argument("--debug", default=False, action="store_true", help="Turns on debugging output.")

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