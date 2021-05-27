from subprocess import Popen, PIPE, STDOUT

class Delta:
	def __init__(self, origin, destination):
		self.worker = Popen(["zfs", "send", "-c", "-I", origin, destination], shell=False, stdout=PIPE, stderr=PIPE)
	
	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=1024):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)