import logging
from .snapshots.delta import DeltaReader
from .pool import PoolRestore
from .models import ZFSSnapshotDelta, ZFSPool
from .logger import log

workers = {}

def has_worker_for(obj):
	return obj.id in workers

def setup_worker(obj):
	if type(obj) == ZFSSnapshotDelta:
		log(f"Setting up a DeltaReader for {repr(obj)}", level=logging.INFO, fg="grey")
		workers[obj.id] = DeltaReader(obj)
	elif type(obj) == ZFSPool:
		log(f"Setting up a PoolReader reader for {repr(obj)}", level=logging.INFO, fg="grey")
		workers[obj.id] = PoolRestore(obj)