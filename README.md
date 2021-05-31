# python-zfs
Python wrapper for zfs

# Example usage
```python
import zfs.list
import zfs.snapshots
import zfs.stream

def encrypt(data):
	return data

stream = zfs.snapshots.Delta(*zfs.list.last_snapshots(2))
zfs.stream.deliver(stream, to=('10.10.0.2', 1337), on_send=encrypt)
```
