# python-zfs
Python wrapper for zfs

![speed-test](https://img.shields.io/badge/speed%20test-5.983%20Gibps-brightgreen)

![speed](https://user-images.githubusercontent.com/861439/167684174-e7bcea49-9275-4727-b878-4ea98cf323af.gif)



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

# Running testscenario without zfs

## Creating isolated networking *(veth interface pair)*:
```bash
# Create veth pair
ip link add dev testif-in type veth peer name testif-out
# Set IP addresses
ip addr add 192.168.1.1 dev testif-in    # Make sure it doesn't collide
ip addr add 192.168.1.2 dev testif-out   # with existing setups on your network.
# Set MAC addresses
ip link set dev testif-in address '46:dc:e7:58:d0:a2'
ip link set dev testif-out address 'e2:ff:48:6e:a9:fe'
# Bring it all up
ip link set dev testif-in up
ip link set dev testif-out up

```

## Creating payload *(a known payload)*:
```
dd if=/dev/urandom of=./small.img bs=1M count=1
```

## Start reciever

```
$ python -m zfs --reciever --interface testif-out --dummy-data ./small_recv.img
```

## Starting sender

```
$ python -m zfs --interface testif-in --full-sync --dummy-data ~/snall.img --pool testing --destination-ip 192.168.1.2 --destination-mac 'e2:ff:48:6e:a9:fe' --source-ip '192.168.1.1' --source-mac '46:dc:e7:58:d0:a2'
```

## Debugging

Running wireshark on `testif-in` *(and `-out`)* should show traffic, which should have correct IP/UDP headers, with a payload matching the defined structure found in this readme *(TBD)*.