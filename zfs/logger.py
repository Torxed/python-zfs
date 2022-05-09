import os
import sys
import pathlib

from .storage import storage

# Found first reference here: https://stackoverflow.com/questions/7445658/how-to-detect-if-the-console-does-support-ansi-escape-codes-in-python
# And re-used this: https://github.com/django/django/blob/master/django/core/management/color.py#L12
def supports_color():
	"""
	Return True if the running system's terminal supports color,
	and False otherwise.
	"""
	supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ

	# isatty is not always implemented, #6223.
	is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
	return supported_platform and is_a_tty

# Heavily influenced by: https://github.com/django/django/blob/ae8338daf34fd746771e0678081999b656177bae/django/utils/termcolors.py#L13
# Color options here: https://askubuntu.com/questions/528928/how-to-do-underline-bold-italic-strikethrough-color-background-and-size-i
def stylize_output(text: str, *opts :str, **kwargs) -> str:
	"""
	Adds styling to a text given a set of color arguments.
	"""
	opt_dict = {'bold': '1', 'italic': '3', 'underscore': '4', 'blink': '5', 'reverse': '7', 'conceal': '8'}
	colors = {
		'black' : '0',
		'red' : '1',
		'green' : '2',
		'yellow' : '3',
		'blue' : '4',
		'magenta' : '5',
		'cyan' : '6',
		'white' : '7',
		'orange' : '8;5;208',    # Extended 256-bit colors (not always supported)
		'darkorange' : '8;5;202',# https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html#256-colors
		'gray' : '8;5;246',
		'grey' : '8;5;246',
		'darkgray' : '8;5;240',
		'lightgray' : '8;5;256'
	}
	foreground = {key: f'3{colors[key]}' for key in colors}
	background = {key: f'4{colors[key]}' for key in colors}
	reset = '0'

	code_list = []
	if text == '' and len(opts) == 1 and opts[0] == 'reset':
		return '\x1b[%sm' % reset

	for k, v in kwargs.items():
		if k == 'fg':
			code_list.append(foreground[str(v)])
		elif k == 'bg':
			code_list.append(background[str(v)])

	for o in opts:
		if o in opt_dict:
			code_list.append(opt_dict[o])

	if 'noreset' not in opts:
		text = '%s\x1b[%sm' % (text or '', reset)

	return '%s%s' % (('\x1b[%sm' % ';'.join(code_list)), text or '')

def log(*args, **kwargs):
	string = orig_string = ' '.join([str(x) for x in args])

	# Attempt to colorize the output if supported
	# Insert default colors and override with **kwargs
	if supports_color():
		kwargs = {'fg': 'white', **kwargs}
		string = stylize_output(string, **kwargs)

	# If a logfile is defined in storage,
	# we use that one to output everything
	if filename := storage.get('LOG_FILE', None):
		absolute_logfile = os.path.join(storage.get('LOG_PATH', './'), filename)

		try:
			pathlib.Path(absolute_logfile).parents[0].mkdir(exist_ok=True, parents=True)
			with open(absolute_logfile, 'a') as log_file:
				log_file.write("")
		except PermissionError:
			# Fallback to creating the log file in the current folder
			err_string = f"Not enough permission to place log file at {absolute_logfile}, creating it in {pathlib.Path('./').absolute() / filename} instead."
			absolute_logfile = pathlib.Path('./').absolute() / filename
			absolute_logfile.parents[0].mkdir(exist_ok=True)
			absolute_logfile = str(absolute_logfile)
			storage['LOG_PATH'] = './'
			log(err_string, fg="red")

		with open(absolute_logfile, 'a') as log_file:
			log_file.write(f"{orig_string}\n")

	# If we assigned a level, try to log it to systemd's journald.
	# Unless the level is higher than we've decided to output interactively.
	# (Remember, log files still get *ALL* the output despite level restrictions)
	if 'level' in kwargs:
		if kwargs['level'] < storage['arguments'].verbosity_level and 'force' not in kwargs:
			# Level on log message was Debug, but output level is set to Info.
			# In that case, we'll drop it.
			return None

	if kwargs.get('mute_output', False) is False:
		# Finally, print the log unless we skipped it based on level.
		# We use sys.stdout.write()+flush() instead of print() to try and
		# fix issue #94
		sys.stdout.write(f"{string}\n")
		sys.stdout.flush()