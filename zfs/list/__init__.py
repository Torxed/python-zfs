from typing import Iterator

from .. import SysCommandWorker
from ..models import (
	Namespace,
	Snapshot,
	Volume
)
from .volumes import (
	volumes,
	get_volume
)

def snapshots():
	worker = SysCommandWorker('zfs list -H -t snapshot')
	while worker.is_alive():
		for line in worker:
			name, used, avail, refer, mountpoint = line.strip(b'\r\n').decode('UTF-8').split('\t')
			yield Snapshot(**{
				"name": name,
				"used": used if used != b'-' else None,
				"avail": avail if avail != b'-' else None,
				"refer": refer if refer != b'-' else None,
				"mountpoint": mountpoint if mountpoint != b'-' else None
			})

def last_snapshots(namespace :Namespace, n :int = 2):
	"""
	Slightly slower function to iterate snapshots() because
	it will reverse the order of the snapshots, and since it's
	a line-fed list we have to iterate over each line.
	"""
	if type(namespace) != Namespace:
		raise AssertionError(f"last_snapshots(namespace, [n=2]) requires a zfs.Namespace() models to be given as first parameter.")
	
	all_snapshots = list(reversed([snapshot for snapshot in snapshots() if snapshot.name.startswith(namespace.name)]))

	return all_snapshots[:n]