import logging
from .snapshots.delta import DeltaReader
from .pool import PoolRestore
from .dataset import DatasetRestore
from .logger import log

workers = {}

def has_worker_for(transfer_id):
	return transfer_id in workers

def setup_worker(transfer_id, information):
	if information[0] == 2:
		log(f"Setting up a DeltaReader for {information}", level=logging.INFO, fg="grey")
		workers[transfer_id] = DeltaReader(information)
	elif information[0] == 1:
		log(f"Setting up a PoolRestore reader for {information}", level=logging.INFO, fg="grey")
		workers[transfer_id] = PoolRestore(information)
	elif information[0] == 0:
		log(f"Setting up a DatasetRestore reader for {information}", level=logging.INFO, fg="grey")
		workers[transfer_id] = DatasetRestore(information)
