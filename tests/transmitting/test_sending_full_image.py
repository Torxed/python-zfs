import pytest

def test_sending_full_image():
	import zfs
	import pathlib

	postnord = {
		'interface' : "lo",
		'source' : {
			'mac_address' : "00:00:00:00:00:00",
			'ipv4_address' : "127.0.0.1"
		},
		'destination' : {
			'mac_address' : "FF:FF:FF:FF:FF:FF",
			'ipv4_address' : "127.0.0.1"
		},
		'udp_port' : 1337
	}

	args = zfs.storage['arguments']
	args.dummy_data = pathlib.Path('./small.img')
	args.pool = 'testing'
	args.interface = 'lo'

	if args.pool and (zfsObj := zfs.get_volume(args.pool)):
		with zfs.Pool(zfsObj) as stream:
			zfs.networking.send(stream=stream, addressing=postnord, rate_limit=args.rate_limit)
	#elif args.dataset and (zfsObj := zfs.get_volume(args.dataset)):
	#	with zfs.Dataset(zfsObj) as stream:
	#		zfs.networking.send(stream=stream, addressing=postnord, rate_limit=args.rate_limit)
	#else:
	#	raise KeyError(f"Could not locate pool {args.pool} or dataset {args.dataset}.")