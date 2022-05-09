import pydantic

class ZFSPool(pydantic.BaseModel):
	transfer_id :int # B
	name :str

	@property
	def id(self):
		return self.transfer_id
