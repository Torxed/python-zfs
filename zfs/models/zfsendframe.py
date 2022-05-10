import pydantic

class ZFSEndFrame(pydantic.BaseModel):
	transfer_id :int # B

	@property
	def id(self):
		return self.transfer_id
