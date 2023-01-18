from dataclasses import dataclass
from typing import Union, Optional

@dataclass
class ZFSDataset():
	name: str
	pool: str
	used: Optional[str] = None
	available: Optional[str] = None
	refer: Optional[str] = None
	mountpoint: Optional[str] = None
	transfer_id: Optional[int] = None
	stream_type: int = 0