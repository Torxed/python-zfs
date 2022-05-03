import pydantic
import logging
from typing import Optional
from .. import log

class Namespace(pydantic.BaseModel):
	name :str

class Snapshot(pydantic.BaseModel):
	name :str
	used :Optional[str] = None
	avail :Optional[str] = None
	refer :Optional[str] = None
	mountpoint :Optional[str] = None

	def destroy(self):
		from .. import SysCommand

		log(f"Destroying snapshot {repr(self)}", fg="red", level=logging.INFO)
		SysCommand(f'zfs destroy {self.name}')

	def restore(self):
		from .. import SysCommand

		log(f"Rolling back ZFS snapshot {repr(self)}", fg="orange", level=logging.INFO)
		SysCommand(f'zfs rollback {self.name}')

class Volume(pydantic.BaseModel):
	name :str
	used :Optional[str] = None
	avail :Optional[str] = None
	refer :Optional[str] = None
	mountpoint :Optional[str] = None

	@property
	def last_snapshots(self):
		from ..list import last_snapshots

		for snapshot in last_snapshots(Namespace(name=self.name), n=2):
			yield snapshot

	def take_snapshot(self, index :Optional[int] = None) -> str:
		from .. import SysCommand
		from ..list import last_snapshots

		log(f"Taking snapshot {repr(self)}", fg="green", level=logging.INFO)

		if index is None:
			for snapshot in last_snapshots(Namespace(name=self.name), n=1):
				if not '@' in snapshot.name:
					raise ValueError(f"Could not reliably determain index of snapshot because it's lacking @ in the snapshot name.")

				index = int(snapshot.name.split('@', 1)[-1])+1

		if index is None:
			index = 0

		SysCommand(f'zfs snapshot {self.name}@{index}')

		return Snapshot(name=f"{self.name}@{index}")