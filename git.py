
import os
import subprocess

class Git:
	def __init__(self, dir=os.getcwd()):
		self.dir = dir

	def run(self, args, check=True, color=False, encode=True):
		return subprocess.run(['git', '-C', self.dir, '--no-pager']
				+ (['-c', 'color.ui=always'] if color else []) + args,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE, universal_newlines=encode,
				check=check)
