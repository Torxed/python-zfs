import importlib
import sys
import pathlib
import logging
import argparse
import ipaddress

if pathlib.Path('./zfs/__init__.py').absolute().exists():
	spec = importlib.util.spec_from_file_location("zfs", "./zfs/__init__.py")
	zfs = importlib.util.module_from_spec(spec)
	sys.modules["zfs"] = zfs
	spec.loader.exec_module(sys.modules["zfs"])
else:
	import zfs


# utility = argparse.ArgumentParser(description="Parameters for the Python ZFS utility module", parents=[zfs.storage['argparse']], add_help=False)

common_parameters = argparse.ArgumentParser(parents=[zfs.storage['argparse']], description="A set of common parameters for the tooling", add_help=False)
common_parameters.add_argument("--destination-ip", nargs="?", type=ipaddress.IPv4Address, help="Which IP to send delta or a full sync.")
common_parameters.add_argument("--destination-mac", nargs="?", type=str, help="Which MAC to send delta or a full sync.")
common_parameters.add_argument("--source-ip", nargs="?", type=ipaddress.IPv4Address, help="Which IP to send as (can be an existing or a spoofed one).")
common_parameters.add_argument("--source-mac", nargs="?", type=str, help="Which MAC to send as (can be an existing or spoofed one).")
common_parameters.add_argument("--udp-port", default=1337, nargs="?", type=ipaddress.IPv4Address, help="Which UDP port to send to.")

common_parameters.add_argument("--pool", nargs="?", type=str, help="Defines which pool to perform the action on.")
common_parameters.add_argument("--delta-start", nargs="?", type=str, help="Which is the source of the delta (the starting point of the delta).")
common_parameters.add_argument("--delta-end", nargs="?", type=str, help="Which is the end of the delta.")

common_parameters.add_argument("--dummy-data", nargs="?", type=pathlib.Path, help="Enables dummy transfer using a binary blob instead.")

zfs.storage['arguments'], unknown = common_parameters.parse_known_args(namespace=zfs.storage['arguments'])

module_entrypoints = argparse.ArgumentParser(parents=[common_parameters], description="A set of common parameters for the tooling", add_help=True)
# Full Sync arguments
utility_options = module_entrypoints.add_mutually_exclusive_group(required=True)
utility_options.add_argument("--full-sync", default=False, action="store_true", help="Performs a full sync and transfer of a pool/dataset.")
utility_options.add_argument("--send-delta", default=False, action="store_true", help="Sends a delta between two snapshots of a pool/dataset.")
utility_options.add_argument("--snapshot", default=False, action="store_true", help="Takes a snapshot of a pool/dataset.")
utility_options.add_argument("--reciever", default=False, action="store_true", help="Turns on reciever mode, which is a universal tooling to recieve datasets/delta from a sender.")

zfs.storage['arguments'], unknown = module_entrypoints.parse_known_args(namespace=zfs.storage['arguments'])

args = zfs.storage['arguments']
# if not any([args.full_sync, args.send_delta, args.snapshot]):
# 	raise ValueError("Need to supply either --full-sync, --send-delta or --snapshot as a minimum.")


if args.full_sync:
	if not all([args.pool, args.destination_ip, args.source_ip, args.destination_mac, args.source_mac]):
		raise ValueError(f"--full-sync requires --pool, --destination-ip, --destination-mac, --source-ip and --source-mac to be defined, so we need to know which pool to fully sync with and which destination.")

	pool = zfs.get_volume(args.pool)

	postnord = zfs.NetNode(
		interface=args.interface,
		source=zfs.NetNodeAddress(mac_address=args.source_mac, ipv4_address=args.source_ip),
		destination=zfs.NetNodeAddress(mac_address=args.destination_mac, ipv4_address=args.destination_ip),
		udp_port=zfs.storage['arguments'].udp_port
	)

	with zfs.Image(zfs.Volume(name=args.pool)) as stream:
		zfs.networking.deliver(transfer_id=1, stream=stream, addressing=postnord)

elif args.reciever:
	with zfs.networking.Reciever(addr='', port=zfs.storage['arguments'].udp_port) as listener:
		while True:
			for zfs_recieved_obj in listener:
				if type(zfs_recieved_obj) in (zfs.ZFSSnapshotDelta, zfs.ZFSFullDataset):
					if zfs.has_worker_for(zfs_recieved_obj) is False:
						zfs.setup_worker(zfs_recieved_obj)

				elif type(zfs_recieved_obj) == zfs.ZFSChunk:
					zfs.log(f'Got a chunk: {repr(zfs_recieved_obj)}', level=logging.INFO, fg="orange")

					zfs.workers[zfs_recieved_obj.id].restore(zfs_recieved_obj)