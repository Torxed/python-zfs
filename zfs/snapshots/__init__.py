from subprocess import Popen, PIPE, STDOUT

class Delta:
	def __init__(self, origin, destination):
		self.origin = origin
		self.destination = destination
		self.worker = Popen(["zfs", "send", "-c", "-I", origin, destination], shell=False, stdout=PIPE, stderr=PIPE)
	
	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=692):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)

class DeltaReader:
	def __init__(self):
		self.worker = None

	def restore(self, frame):
		print('Restoring frame:', frame)