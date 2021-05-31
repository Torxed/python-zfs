from subprocess import Popen, PIPE, STDOUT

class Delta:
	def __init__(self, origin, destination):
		self.origin = origin
		self.destination = destination
		self.worker = None

	def __enter__(self):
		self.worker = Popen(["zfs", "send", "-c", "-I", self.origin, self.destination], shell=False, stdout=PIPE, stderr=PIPE)
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)
			
		if self.worker:
			self.worker.stdout.close()
			self.worker.stderr.close()

	def is_alive(self):
		return self.worker.poll() is None

	def read(self, buf_len=692):
		if self.is_alive():
			return self.worker.stdout.read(buf_len)

class DeltaReader:
	def __init__(self):
		self.worker = None
		self.transfer_id = None

	def __enter__(self):
		return self

	def __exit__(self, *args):
		if args[0]:
			print(args)

		if self.worker:
			self.worker.stdout.close()
			self.worker.stdin.close()
			self.worker.stderr.close()

	def restore(self, frame):
		if not self.worker:
			self.worker = Popen(["zfs", "recv", frame['information']['destination_name']], shell=False, stdout=PIPE, stdin=PIPE, stderr=PIPE)

		print(f"Restoring: {frame['data']['data'][:50]}")
		self.worker.stdin.write(frame['data']['data'])
		self.worker.stdin.flush()