#import pytest
import urllib.request
import pathlib
import grp
import pwd
import os
import shutil
import time
import logging
import tarfile

pool_name = 'testpool_python_zfs'

def test_sending_full_image():
	import zfs

	# print(zfs.SysCommand('/usr/bin/zfs --help').decode('UTF-8'))


	# build_root = pathlib.Path('/usr/aur-builds/').resolve()
	# build_root.mkdir(parents=True, exist_ok=True)

	# try:
	# 	zfs.SysCommand(f"zpool destroy {pool_name}")
	# except (zfs.exceptions.SysCallError, zfs.exceptions.RequirementError):
	# 	"""
	# 	Either we have never installed zfs-linux before,
	# 	or the pool didn't exist.
	# 	"""
	# 	pass

	# try:
	# 	zfs.SysCommand('id -u builduser')
	# except zfs.exceptions.SysCallError:
	# 	# Create builduser if not exists, no password.
	# 	zfs.SysCommand('useradd -m -G wheel -s /bin/bash builduser')

	# if (sudoers_existed := pathlib.Path('/etc/sudoers.d/01_builduser').exists()) is False:
	# 	with open('/etc/sudoers.d/01_builduser', 'w') as fh:
	# 		fh.write("builduser ALL=(ALL:ALL) NOPASSWD: ALL\n")

	# uid = pwd.getpwnam("builduser").pw_uid
	# gid = grp.getgrnam("wheel").gr_gid

	# zfs.SysCommand(f"git clone https://aur.archlinux.org/yay-bin.git {build_root}/yay-bin")

	# os.chown(str(build_root), uid, gid)

	# for root, dirs, files in os.walk(f"{build_root}/yay-bin"):
	# 	os.chown(root, uid, gid)
	# 	for obj in files:
	# 		os.chown(os.path.join(root, obj), uid, gid)

	# zfs.SysCommand(f"su - builduser -c 'cd {build_root}/yay-bin/; makepkg -si --noconfirm'", peak_output=True)

	# urllib.request.urlretrieve("https://aur.archlinux.org/cgit/aur.git/snapshot/zfs-utils.tar.gz", "zfs-utils.tar.gz")
	# urllib.request.urlretrieve("https://aur.archlinux.org/cgit/aur.git/snapshot/zfs-linux.tar.gz", "zfs-linux.tar.gz")

	# with tarfile.open('zfs-utils.tar.gz') as file:
	# 	file.extractall(f"{build_root}/")

	# with tarfile.open('zfs-linux.tar.gz') as file:
	# 	file.extractall(f"{build_root}/")

	# # We need to ensure that the temporary builduser has access
	# # to both the root of the build directory, and the newly downloaded archive.
	# os.chown(str(build_root), uid, gid)

	# pathlib.Path('/home/builduser/.gnupg/').mkdir(parents=True, exist_ok=True)
	# with open('/home/builduser/.gnupg/gpg.conf', 'w') as fh:
	# 	fh.write('keyserver-options auto-key-retrieve\n')
	# 	fh.write('auto-key-locate hkp://pool.sks-keyservers.net\n')

	# os.chmod('/home/builduser/.gnupg', 0o700)
	# os.chown('/home/builduser/.gnupg', uid, uid)
	# os.chmod('/home/builduser/.gnupg/gpg.conf', 0o600)
	# os.chown('/home/builduser/.gnupg/gpg.conf', uid, uid)

	# print(zfs.SysCommand(f"ls -la /home/builduser/.gnupg/").decode('UTF-8'))

	# # Not sure why this is there.
	# pathlib.Path('/usr/bin/zfs').unlink()

	# for package in ['zfs-utils', 'zfs-linux']:
	# 	for root, dirs, files in os.walk(f"{build_root}/{package}"):
	# 		os.chown(root, uid, gid)
	# 		for obj in files:
	# 			os.chown(os.path.join(root, obj), uid, gid)

	# 	zfs.log(f"Building {package}, this might take time..", fg="orange", level=logging.WARNING)
	# 	zfs.SysCommand(f"su - builduser -c 'cd {build_root}/{package}/; gpg --recv-keys 6AD860EED4598027; makepkg -si -f --noconfirm'", working_directory=f"{build_root}/zfs-linux/", peak_output=True)

	# if sudoers_existed is False:
	# 	pathlib.Path('/etc/sudoers.d/01_builduser').unlink()

	zfs.SysCommand(f"/sbin/modprobe zfs")
	zfs.SysCommand(f"truncate -s 100M /testimage.img")
	zfs.SysCommand(f"zpool create -f {pool_name} /testimage.img")
	zfs.SysCommand(f"zfs create {pool_name}/testsync")

	pool = zfs.list.get_volume(f'{pool_name}/testsync')

	snapshot1 = pool.take_snapshot()

	zfs.log("Writing data between snapshots..", fg="cyan")
	with open(f'/{pool_name}/testsync/test.txt', 'w') as fh:
		fh.write(time.strftime('%Y-%m-%d %H:%M:%S\n'))
		
	snapshot2 = pool.take_snapshot()
	snapshot2.destroy()

	last_snapshot = list(pool.last_snapshots)[-1]
	last_snapshot.restore()

	if pathlib.Path(f'/{pool_name}/testsync/test.txt').exists():
		raise AssertionError(f"Could not restore snapshot {snapshot1} on {pool}")

	try:
		zfs.SysCommand(f"zpool destroy {pool_name}")
	except zfs.exceptions.SysCallError:
		pass

