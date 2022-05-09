import pydantic

class ZFSSnapshotDelta(pydantic.BaseModel):
	transfer_id :int
	name :str

	@property
	def id(self):
		return self.transfer_id