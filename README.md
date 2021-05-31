# python-zfs
Python wrapper for zfs

# Example usage

On the sender side, something along the lines of:
```python
import zfs.list
import zfs.snapshots
import zfs.stream

def encrypt(data):
	return data

stream = zfs.snapshots.Delta(*zfs.list.last_snapshots(2))
zfs.stream.deliver(stream, to=('10.10.0.2', 1337), on_send=encrypt)
```

And on the reciever end, to recieve the zfs snapshot:
```python
import zfs.list
import zfs.snapshots
import zfs.stream

snapshot = zfs.snapshots.DeltaReader(delivery)

with zfs.stream.Reciever(addr='', port=1337) as stream:
	for zfs_snapshot_chunk in stream:
		snapshot.restore(zfs_snapshot_chunk)
```
