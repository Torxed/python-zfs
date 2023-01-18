from dataclasses import dataclass
from typing import Union, Optional

@dataclass
class ZFSPool():
	name: str
	used: Optional[str] = None
	available: Optional[str] = None
	refer: Optional[str] = None
	mountpoint: Optional[str] = None
	transfer_id: Optional[int] = None
	stream_type: int = 1

	@property
	def pool(self):
		return self.name