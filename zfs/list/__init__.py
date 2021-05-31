from .. import SysCommandWorker

def snapshots():
	worker = SysCommandWorker('zfs list -H -t snapshot')
	while worker.is_alive():
		for line in worker:
			name, used, avail, refer, mountpoint = line.split(b'\t')
			yield {
				"name": name,
				"used": used,
				"avail": avail,
				"refer": refer,
				"mountpoint": mountpoint
			}

def snapshot():
	return {snap['name'].decode('UTF-8') : {**{k: v.decode('UTF-8') for k, v in snap.items()}} for snap in snapshots()}

def last_snapshots(namespace, n=2):
	return [key for key in snapshot().keys() if namespace in key][0-n:]