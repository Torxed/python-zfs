import hashlib
import json
import logging
import os
import pty
import shlex
import subprocess
import sys
import time
import select
import re
from datetime import datetime, date
from typing import Union, List, Optional, Dict, Any, Iterator, Callable
from .storage import storage

EPOLLIN = 0
EPOLLHUP = 0
class epoll():
	""" #!if windows
	Create a epoll() implementation that simulates the epoll() behavior.
	This so that the rest of the code doesn't need to worry weither we're using select() or epoll().
	"""
	def __init__(self):
		self.sockets = {}
		self.monitoring = {}

	def unregister(self, fileno, *args, **kwargs):
		try:
			del(self.monitoring[fileno])
		except:
			pass

	def register(self, fileno, *args, **kwargs):
		self.monitoring[fileno] = True

	def poll(self, timeout=0.05, *args, **kwargs):
		try:
			return [[fileno, 1] for fileno in select.select(list(self.monitoring.keys()), [], [], timeout)[0]]
		except OSError:
			return []

class SysCallError(BaseException):
	pass


def clear_vt100_escape_codes(data :Union[bytes, str]):
	# https://stackoverflow.com/a/43627833/929999
	if type(data) == bytes:
		vt100_escape_regex = bytes(r'\x1B\[[?0-9;]*[a-zA-Z]', 'UTF-8')
	else:
		vt100_escape_regex = r'\x1B\[[?0-9;]*[a-zA-Z]'


	for match in re.findall(vt100_escape_regex, data, re.IGNORECASE):
		data = data.replace(match, '' if type(data) == str else b'')

	return data

def locate_binary(name):
	for PATH in os.environ['PATH'].split(':'):
		for root, folders, files in os.walk(PATH):
			for file in files:
				if file == name:
					return os.path.join(root, file)
			break  # Don't recurse

	raise RequirementError(f"Binary {name} does not exist.")

class SysCommandWorker:
	def __init__(self,
		cmd :Union[str, List[str]],
		callbacks :Optional[Dict[str, Any]] = None,
		peak_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		logfile :Optional[None] = None,
		working_directory :Optional[str] = './',
		remove_vt100_escape_codes_from_lines :bool = True):

		if not callbacks:
			callbacks = {}
		if not environment_vars:
			environment_vars = {}

		if type(cmd) is str:
			cmd = shlex.split(cmd)

		cmd = list(cmd) # This is to please mypy
		if cmd[0][0] != '/' and cmd[0][:2] != './':
			# "which" doesn't work as it's a builtin to bash.
			# It used to work, but for whatever reason it doesn't anymore.
			# We there for fall back on manual lookup in os.PATH
			cmd[0] = locate_binary(cmd[0])

		self.cmd = cmd
		self.callbacks = callbacks
		self.peak_output = peak_output
		# define the standard locale for command outputs. For now the C ascii one. Can be overriden
		self.environment_vars = {'LC_ALL' : storage['arguments'].locale, **environment_vars}
		self.logfile = logfile
		self.working_directory = working_directory

		self.exit_code :Optional[int] = None
		self._trace_log = b''
		self._trace_log_pos = 0
		self.poll_object = epoll()
		self.child_fd :Optional[int] = None
		self.started :Optional[float] = None
		self.ended :Optional[float] = None
		self.remove_vt100_escape_codes_from_lines :bool = remove_vt100_escape_codes_from_lines

	def __contains__(self, key: bytes) -> bool:
		"""
		Contains will also move the current buffert position forward.
		This is to avoid re-checking the same data when looking for output.
		"""
		assert type(key) == bytes

		if (contains := key in self._trace_log[self._trace_log_pos:]):
			self._trace_log_pos += self._trace_log[self._trace_log_pos:].find(key) + len(key)

		return contains

	def __iter__(self, *args :str, **kwargs :Dict[str, Any]) -> Iterator[bytes]:
		print('Iterating traceback:', self._trace_log)
		for line in self._trace_log[self._trace_log_pos:self._trace_log.rfind(b'\n')].split(b'\n'):
			if line:
				if self.remove_vt100_escape_codes_from_lines:
					line = clear_vt100_escape_codes(line)

				yield line + b'\n'

		self._trace_log_pos = self._trace_log.rfind(b'\n')

	def __repr__(self) -> str:
		self.make_sure_we_are_executing()
		return str(self._trace_log)

	def __enter__(self) -> 'SysCommandWorker':
		return self

	def __exit__(self, *args :str) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if self.child_fd:
			try:
				os.close(self.child_fd)
			except:
				pass

		if self.peak_output:
			# To make sure any peaked output didn't leave us hanging
			# on the same line we were on.
			sys.stdout.write("\n")
			sys.stdout.flush()

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.DEBUG, fg='red')

		if self.exit_code != 0:
			raise SysCallError(f"{self.cmd} exited with abnormal exit code [{self.exit_code}]: {self._trace_log[-500:]}", self.exit_code)

	def is_alive(self) -> bool:
		self.poll()

		if self.started and self.ended is None:
			return True

		return False

	def write(self, data: bytes, line_ending :bool = True) -> int:
		assert type(data) == bytes  # TODO: Maybe we can support str as well and encode it

		self.make_sure_we_are_executing()

		if self.child_fd:
			return os.write(self.child_fd, data + (b'\n' if line_ending else b''))

		return 0

	def make_sure_we_are_executing(self) -> bool:
		if not self.started:
			return self.execute()
		return True

	def tell(self) -> int:
		self.make_sure_we_are_executing()
		return self._trace_log_pos

	def seek(self, pos :int) -> None:
		self.make_sure_we_are_executing()
		# Safety check to ensure 0 < pos < len(tracelog)
		self._trace_log_pos = min(max(0, pos), len(self._trace_log))

	def peak(self, output: Union[str, bytes]) -> bool:
		if self.peak_output:
			if type(output) == bytes:
				try:
					output = output.decode('UTF-8')
				except UnicodeDecodeError:
					return False

			with open(f"{storage['arguments'].log_dir}/cmd_output.txt", "a") as peak_output_log:
				peak_output_log.write(output)

			sys.stdout.write(str(output))
			sys.stdout.flush()

		return True

	def poll(self) -> None:
		self.make_sure_we_are_executing()

		if self.child_fd:
			got_output = False
			for fileno, event in self.poll_object.poll(0.1):
				try:
					output = os.read(self.child_fd, 8192)
					got_output = True
					self.peak(output)
					self._trace_log += output
				except OSError:
					self.ended = time.time()
					break

			if self.ended or (got_output is False and pid_exists(self.pid) is False):
				self.ended = time.time()
				try:
					self.exit_code = os.waitpid(self.pid, 0)[1]
				except ChildProcessError:
					try:
						self.exit_code = os.waitpid(self.child_fd, 0)[1]
					except ChildProcessError:
						self.exit_code = 1

	def execute(self) -> bool:
		import pty

		if (old_dir := os.getcwd()) != self.working_directory:
			os.chdir(str(self.working_directory))

		# Note: If for any reason, we get a Python exception between here
		#   and until os.close(), the traceback will get locked inside
		#   stdout of the child_fd object. `os.read(self.child_fd, 8192)` is the
		#   only way to get the traceback without loosing it.

		self.pid, self.child_fd = pty.fork()
		os.chdir(old_dir)

		# https://stackoverflow.com/questions/4022600/python-pty-fork-how-does-it-work
		if not self.pid:
			try:
				try:
					with open(f"{storage['arguments'].log_dir}/cmd_history.txt", "a") as cmd_log:
						cmd_log.write(f"{' '.join(self.cmd)}\n")
				except PermissionError:
					pass

				os.execve(self.cmd[0], list(self.cmd), {**os.environ, **self.environment_vars})
				if storage['arguments'].debug:
					log(f"Executing: {self.cmd}", level=logging.DEBUG)

			except FileNotFoundError:
				log(f"{self.cmd[0]} does not exist.", level=logging.ERROR, fg="red")
				self.exit_code = 1
				return False

		self.started = time.time()
		self.poll_object.register(self.child_fd, EPOLLIN | EPOLLHUP)

		return True

	def decode(self, encoding :str = 'UTF-8') -> str:
		return self._trace_log.decode(encoding)


class SysCommand:
	def __init__(self,
		cmd :Union[str, List[str]],
		callbacks :Optional[Dict[str, Callable[[Any], Any]]] = None,
		start_callback :Optional[Callable[[Any], Any]] = None,
		peak_output :Optional[bool] = False,
		environment_vars :Optional[Dict[str, Any]] = None,
		working_directory :Optional[str] = './',
		remove_vt100_escape_codes_from_lines :bool = True):

		_callbacks = {}
		if callbacks:
			for hook, func in callbacks.items():
				_callbacks[hook] = func
		if start_callback:
			_callbacks['on_start'] = start_callback

		self.cmd = cmd
		self._callbacks = _callbacks
		self.peak_output = peak_output
		self.environment_vars = environment_vars
		self.working_directory = working_directory
		self.remove_vt100_escape_codes_from_lines = remove_vt100_escape_codes_from_lines

		self.session :Optional[SysCommandWorker] = None
		self.create_session()

	def __enter__(self) -> Optional[SysCommandWorker]:
		return self.session

	def __exit__(self, *args :str, **kwargs :Dict[str, Any]) -> None:
		# b''.join(sys_command('sync')) # No need to, since the underlying fs() object will call sync.
		# TODO: https://stackoverflow.com/questions/28157929/how-to-safely-handle-an-exception-inside-a-context-manager

		if len(args) >= 2 and args[1]:
			log(args[1], level=logging.ERROR, fg='red')

	def __iter__(self, *args :List[Any], **kwargs :Dict[str, Any]) -> Iterator[bytes]:
		if self.session:
			for line in self.session:
				yield line

	def __getitem__(self, key :slice) -> Optional[bytes]:
		if not self.session:
			raise KeyError(f"SysCommand() does not have an active session.")
		elif type(key) is slice:
			start = key.start if key.start else 0
			end = key.stop if key.stop else len(self.session._trace_log)

			return self.session._trace_log[start:end]
		else:
			raise ValueError("SysCommand() doesn't have key & value pairs, only slices, SysCommand('ls')[:10] as an example.")

	def __repr__(self, *args :List[Any], **kwargs :Dict[str, Any]) -> str:
		if self.session:
			return self.session._trace_log.decode('UTF-8')
		return ''

	def __json__(self) -> Dict[str, Union[str, bool, List[str], Dict[str, Any], Optional[bool], Optional[Dict[str, Any]]]]:
		return {
			'cmd': self.cmd,
			'callbacks': self._callbacks,
			'peak': self.peak_output,
			'environment_vars': self.environment_vars,
			'session': True if self.session else False
		}

	def create_session(self) -> bool:
		"""
		Initiates a :ref:`SysCommandWorker` session in this class ``.session``.
		It then proceeds to poll the process until it ends, after which it also
		clears any printed output if ``.peak_output=True``.
		"""
		if self.session:
			return self.session

		with SysCommandWorker(self.cmd, callbacks=self._callbacks, peak_output=self.peak_output, environment_vars=self.environment_vars, remove_vt100_escape_codes_from_lines=self.remove_vt100_escape_codes_from_lines) as session:
			if not self.session:
				self.session = session

			while self.session.ended is None:
				self.session.poll()

		if self.peak_output:
			sys.stdout.write('\n')
			sys.stdout.flush()

		return True

	def decode(self, fmt :str = 'UTF-8') -> Optional[str]:
		if self.session:
			return self.session._trace_log.decode(fmt)
		return None

	@property
	def exit_code(self) -> Optional[int]:
		if self.session:
			return self.session.exit_code
		else:
			return None

	@property
	def trace_log(self) -> Optional[bytes]:
		if self.session:
			return self.session._trace_log
		return None