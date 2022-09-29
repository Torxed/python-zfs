from typing import Optional, Any

class SysCallError(BaseException):
	def __init__(self, message :str, exit_code :Optional[int] = None, worker :Optional['SysCommandWorker'] = None) -> None:
		super(SysCallError, self).__init__(message)
		self.message = message
		self.exit_code = exit_code
		self.worker = worker

class RequirementError(BaseException):
	pass

class RestoreComplete(BaseException):
	def __init__(self, session :Optional[Any] = None) -> None:
		super(RestoreComplete, self).__init__(str(session))
		self.session = session