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

common_parameters.add_argument("--delta-start", nargs="?", type=str, help="Which is the source of the delta (the starting point of the delta).")
common_parameters.add_argument("--delta-end", nargs="?", type=str, help="Which is the end of the delta.")
common_parameters.add_argument("--full-sync", default=False, action="store_true", help="Performs a full sync and transfer of a pool/dataset.")
common_parameters.add_argument("--send-delta", default=False, action="store_true", help="Sends a delta between two snapshots of a pool/dataset.")
common_parameters.add_argument("--snapshot", default=False, action="store_true", help="Takes a snapshot of a pool/dataset.")

zfs.storage['arguments'], unknown = common_parameters.parse_known_args(namespace=zfs.storage['arguments'])

type_entrypoint = argparse.ArgumentParser(parents=[common_parameters], description="A set of common parameters for the tooling", add_help=True)
type_options = type_entrypoint.add_mutually_exclusive_group(required=True)
type_options.add_argument("--pool", nargs="?", type=str, help="Defines which pool to perform the action on.")
type_options.add_argument("--dataset", nargs="?", type=str, help="Defines which dataset to perform the action on.")
type_options.add_argument("--reciever", default=False, action="store_true", help="Turns on reciever mode, which is a universal tooling to recieve datasets/delta from a sender.")
zfs.storage['arguments'], unknown = type_entrypoint.parse_known_args(namespace=zfs.storage['arguments'])

args = zfs.storage['arguments']
# if not any([args.full_sync, args.send_delta, args.snapshot]):
# 	raise ValueError("Need to supply either --full-sync, --send-delta or --snapshot as a minimum.")


if args.full_sync:
	if not all([args.destination_ip, args.source_ip, args.destination_mac, args.source_mac]):
		raise ValueError(f"--full-sync requires --pool, --destination-ip, --destination-mac, --source-ip and --source-mac to be defined, so we need to know which pool to fully sync with and which destination.")

	if any([args.pool, args.dataset]) is False:
		raise ValueError(f"--pool or --dataset must be given to initiate a full sync.")

	postnord = {
		'interface' : args.interface,
		'source' : {
			'mac_address' : args.source_mac,
			'ipv4_address' : args.source_ip
		},
		'destination' : {
			'mac_address' : args.destination_mac,
			'ipv4_address' : args.destination_ip
		},
		'udp_port' : zfs.storage['arguments'].udp_port
	}

	if args.pool and (zfsObj := zfs.get_volume(args.pool)):
		with zfs.Pool(zfsObj) as stream:
			zfs.networking.send(stream=stream, addressing=postnord)
	elif args.dataset and (zfsObj := zfs.get_volume(args.dataset)):
		with zfs.Dataset(zfsObj) as stream:
			zfs.networking.send(stream=stream, addressing=postnord)
	else:
		raise KeyError(f"Could not locate pool or dataset.")

elif args.reciever:
	with zfs.networking.Reciever(addr='', port=zfs.storage['arguments'].udp_port) as listener:
		while True:
			for zfs_recieved_obj in listener:
				# if type(zfs_recieved_obj) in (zfs.ZFSSnapshotDelta, zfs.ZFSPool):
				frame_type = zfs_recieved_obj[0]
				transfer_id = zfs_recieved_obj[1]
				if frame_type in (0, 1, 2):
					if zfs.has_worker_for(transfer_id) is False:
						zfs.setup_worker(transfer_id, zfs_recieved_obj)

				# elif type(zfs_recieved_obj) == zfs.ZFSChunk:
				elif frame_type == 3:
					# zfs.log(f'Got a chunk: {repr(zfs_recieved_obj)}', level=logging.INFO, fg="orange")

					zfs.workers[transfer_id].restore(zfs_recieved_obj)

				# elif type(zfs_recieved_obj) == zfs.ZFSEndFrame:
				elif frame_type == 4:
					zfs.workers[transfer_id].close()
