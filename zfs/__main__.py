import importlib
import sys
import pathlib
import logging

if pathlib.Path('./zfs/__init__.py').absolute().exists():
	spec = importlib.util.spec_from_file_location("zfs", "./zfs/__init__.py")
	zfs = importlib.util.module_from_spec(spec)
	sys.modules["zfs"] = zfs
	spec.loader.exec_module(sys.modules["zfs"])
else:
	import zfs

args = zfs.storage['arguments']
if not any([args.full_sync, args.send_delta, args.snapshot]):
	raise ValueError("Need to supply either --full-sync, --send-delta or --snapshot as a minimum.")

group.add_argument("--pool", nargs="?", type=str, help="Defines which pool to perform the action on.")
group.add_argument("--delta-start", nargs="?", type=str, help="Which is the source of the delta (the starting point of the delta).")
group.add_argument("--delta-end", nargs="?", type=str, help="Which is the end of the delta.")

group.add_argument("--destination-ip", nargs="?", type=ipaddress.IPv4address, help="Which IP to send delta or a full sync.")
group.add_argument("--destination-mac", nargs="?", type=ipaddress.IPv4address, help="Which MAC to send delta or a full sync.")
group.add_argument("--source-ip", nargs="?", type=ipaddress.IPv4address, help="Which IP to send as (can be an existing or a spoofed one).")
group.add_argument("--source-mac", nargs="?", type=ipaddress.IPv4address, help="Which MAC to send as (can be an existing or spoofed one).")
group.add_argument("--udp-port", nargs="?", type=ipaddress.IPv4address, help="Which UDP port to send to.")

if args.full_sync:
	if not all(args.pool, args.destination_ip, args.source_ip, args.destination_mac, args.source_mac):
		raise ValueError(f"--full-sync requires --pool, --destination-ip, --destination-mac, --source-ip and --source-mac to be defined, so we need to know which pool to fully sync with and which destination.")

	pool = zfs.list.get_volume(args.pool)

	postnord = zfs.NetNode(
		interface=args.interface,
		source=zfs.NetNodeAddress(mac_address=args.source_mac, ipv4_address=args.source_ip),
		destination=zfs.NetNodeAddress(mac_address=args.destination_mac, ipv4_address=args.destination_ip),
		udp_port=1337
	)

	with zfs.snapshots.Delta(snapshot1, snapshot2) as stream:
		zfs.networking.deliver(transfer_id=1, stream=stream, addressing=postnord, on_send=encrypt)

	snapshot1.destroy()
	snapshot2.destroy()

	last_snapshot = list(pool.last_snapshots)[-1]
	last_snapshot.restore()