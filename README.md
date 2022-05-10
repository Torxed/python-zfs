# python-zfs
Python wrapper for zfs

# Tooling usage

## Starting the reciever

```
$ python -m zfs --reciever --interface testif-out [--dummy-data ./testdata_recv.bin]
```

## Sending a full dataset

```
$ python -m zfs --interface testif-in --full-sync [--dummy-data ~/testdata.bin] --pool testing --destination-ip 192.168.1.2 --destination-mac 'e2:ff:48:6e:a9:fe' --source-ip '192.168.1.1' --source-mac '46:dc:e7:58:d0:a2'
```

:note: This will send from `46:dc:e7:58:d0:a2 (192.168.1.1)` to `e2:ff:48:6e:a9:fe (192.168.2.2)`.
python-zfs sends in promiscious mode so the IP and MAC source doesn't actually have to existing.
In theory, neither does the sender, but if there's any network equipment between the sender and reciever,
the destination must be known by the network before hand.

:note: Also note that `--dummy-data` is used to simluate the pool `testing` and can contain anything.
It can also be used to send a file instead, but functionality cannot be guaranteed and is for testing mainly.

## Sending delta between two snapshots

```
$ python -m zfs --interface testif-in --send-delta --delta-start pool/testync@0 --delta-end pool/testsync@1 [--dummy-data ~/testdata.bin] --pool testing --destination-ip 192.168.1.2 --destination-mac 'e2:ff:48:6e:a9:fe' --source-ip '192.168.1.1' --source-mac '46:dc:e7:58:d0:a2'
```

# Library usage

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

## Visualize bottlenecks
```
$ viztracer python -m zfs --reciever --interface eth0 --framesize 9000
```
Load `result.json` into https://ui.perfetto.dev/ and dig in.
