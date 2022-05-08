import logging
from .delta import DeltaReader
from .image import ImageReader
from ..models import ZFSSnapshotDelta, ZFSFullDataset
from ..logger import log

workers = {}

def has_worker_for(obj):
	return obj.id in workers

def setup_worker(obj):
	if type(obj) == ZFSSnapshotDelta:
		log(f"Setting up a Delta reader for {repr(obj)}", level=logging.INFO, fg="grey")
		workers[obj.id] = DeltaReader(obj)
	elif type(obj) == ZFSFullDataset:
		log(f"Setting up a Image reader for {repr(obj)}", level=logging.INFO, fg="grey")
		workers[obj.id] = ImageReader(obj)