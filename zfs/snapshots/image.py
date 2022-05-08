import select
import logging
from subprocess import Popen, PIPE

from ..storage import storage
from ..general import FakePopenDestination
from ..logger import log

class ImageReader:
	def __init__(self, pre_flight_frame):
		self.worker = None
		self.pre_flight_frame = pre_flight_frame

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
			if storage['arguments'].dummy_data:
				self.worker = FakePopenDestination(storage['arguments'].dummy_data)
			else:
				self.worker = Popen(["zfs", "recv", self.pre_flight_frame.name], shell=False, stdout=PIPE, stdin=PIPE, stderr=PIPE)

		log(f"Restoring full image data via: {repr(self.pre_flight_frame)} ({frame.data})", level=logging.INFO, fg="green")
		self.worker.stdin.write(frame.data)
		self.worker.stdin.flush()

		if not storage['arguments'].dummy_data:
			for fileno in select.select([self.worker.stdout.fileno()], [], [], 0.2)[0]:
				output = self.worker.stdout.read(1024).decode('UTF-8')
				if output:
					print(output)

			for fileno in select.select([self.worker.stderr.fileno()], [], [], 0.2)[0]:
				raise ValueError(self.worker.stderr.read(1024))