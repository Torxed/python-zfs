# python-zfs
Python wrapper for zfs

# Example usage

## Listing all snapshots

```python
import zfs.list

for volume in zfs.list.volumes():
	if volume.name == 'pool':
		continue

	print(repr(volume))
	for snapshot in volume.snapshots:
		print(repr(snapshot))
```

## Creating and Destroying snapshots

```python
import zfs.list

pool = zfs.list.get_volume('pool/testpool')

snapshot = pool.take_snapshot()
snapshot.destroy()
```

## Sending delta between two snapshots

On the sender side, take a snapshot and send it with:
```python
import time
import zfs.list
import zfs.snapshots
import zfs.stream

def encrypt(data):
	return data

pool = zfs.list.get_volume('pool/testpool')

snapshot1 = pool.take_snapshot()

zfs.log("Writing data between snapshots..", fg="cyan")
with open('/pool/testpool/test.txt', 'w') as fh:
	fh.write(time.strftime('%Y-%m-%d %H:%M:%S\n'))

snapshot2 = pool.take_snapshot()

with zfs.snapshots.Delta(snapshot1, snapshot2) as stream:
	zfs.stream.deliver(stream, to=('192.168.1.1', 1337), on_send=encrypt)

# Roll back the test snapshots and data
snapshot1.destroy()
snapshot2.destroy()

last_snapshot = list(pool.last_snapshots)[-1]
last_snapshot.restore()
```

And on the reciever end, to recieve the zfs snapshot:
```python
import zfs.list
import zfs.snapshots
import zfs.stream

snapshot = zfs.snapshots.DeltaReader()

with zfs.stream.Reciever(addr='', port=1337) as stream:
	for zfs_snapshot_chunk in stream:
		snapshot.restore(zfs_snapshot_chunk)
```
