class ZFSPool():
	def __init__(self, transfer_id, name):
		self.transfer_id = transfer_id
		self.name = name

	@property
	def id(self):
		return self.transfer_id
