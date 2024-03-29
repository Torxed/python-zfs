# from typing import Iterator
# from ..models import Volume
from typing import Union
from ..general import SysCommandWorker
from ..storage import storage
from ..models import ZFSPool, ZFSDataset

def volumes() -> Union[ZFSPool, ZFSDataset]:
	if storage['arguments'].dummy_data:
		yield ZFSPool(
			name="testing",
			used="0.5G",
			available="1.0G",
			refer="-",
			mountpoint="-"
		)

	else:
		worker = SysCommandWorker('zfs list -H', poll_delay=0.5)
		line = b''
		while worker.is_alive() or len(line) > 0:
			for line in worker:
				name, used, avail, refer, mountpoint = line.strip(b'\r\n').decode('UTF-8').split('\t')

				if '/' in name:
					yield ZFSDataset(
						name=name.split('/')[1],
						pool=name.split('/')[0],
						used=used if used != b'-' else None,
						available=avail if avail != b'-' else None,
						refer=refer if refer != b'-' else None,
						mountpoint=mountpoint if mountpoint != b'-' else None
					)
				else:
					yield ZFSPool(
						name=name,
						used=used if used != b'-' else None,
						available=avail if avail != b'-' else None,
						refer=refer if refer != b'-' else None,
						mountpoint=mountpoint if mountpoint != b'-' else None
					)

				line = b'' # Reset for the for while loop
				
def get_volume(name :str) -> ZFSPool | ZFSDataset | None:
	for volume in volumes():
		if '/' in name:
			# Skip ZFSPools as only datasets can contain /
			if type(volume) == ZFSPool:
				continue
			
			if volume.pool.startswith(name.split('/')[0]) and volume.name.startswith(name.split('/')[1]):
				return volume
		else:
			if volume.pool.startswith(name):
				return volume

	return None
