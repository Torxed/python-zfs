# from typing import Iterator
# from ..models import Volume
from ..general import SysCommandWorker
from ..storage import storage

def volumes():
	if storage['arguments'].dummy_data:
		yield {
			"name": "dummy",
			"used": "1.0G",
			"avail": "2.0G",
			"refer": "-",
			"mountpoint": "-"
		}

	else:
		worker = SysCommandWorker('zfs list -H')
		while worker.is_alive():
			for line in worker:
				name, used, avail, refer, mountpoint = line.strip(b'\r\n').decode('UTF-8').split('\t')
				
				yield {
					"name": name,
					"used": used if used != b'-' else None,
					"avail": avail if avail != b'-' else None,
					"refer": refer if refer != b'-' else None,
					"mountpoint": mountpoint if mountpoint != b'-' else None
				}

def get_volume(name :str):
	for volume in volumes():
		if volume['name'].startswith(name):
			return volume
