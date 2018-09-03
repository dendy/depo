
import subprocess

class Git:
	kRefsHeads = 'refs/heads/'

	def __init__(self, dir=None):
		self.dir = dir

	def run(self, args, check=True, color=False):
		local_args = ['-C', self.dir] if self.dir != None else []
		color_args = ['-c', 'color.ui=always'] if color else []

		return subprocess.run(['git'] + local_args + ['--no-pager']
				+ color_args + args,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE, universal_newlines=True,
				check=check)

	def mergeBase(self, a, b):
		return self.run(['merge-base', a, b]).stdout.strip()

	def commitId(self, rev):
		return self.run(['rev-parse', rev]).stdout.strip()

	def isFf(self, source, target):
		base = self.mergeBase(source, target)
		return base == self.commitId(target)

	def exists(self, rev):
		try:
			self.run(['rev-parse', rev])
			return True
		except subprocess.CalledProcessError:
			return False

	def headRev(self):
		rev = self.run(['rev-parse', '--symbolic-full-name', 'HEAD']).stdout.strip()
		return rev if rev != 'HEAD' else self.run(['rev-parse', 'HEAD']).stdout.strip()

	def remoteRevision(remote, rev):
		is_ref = rev.startswith('refs/')
		is_heads = is_ref and rev.startswith(Git.kRefsHeads)

		if is_heads:
			return rev.replace(Git.kRefsHeads, remote + '/', 1)
		if is_ref:
			return rev
		return remote + '/' + rev

	def remoteLocalRevision(rev):
		return rev if rev.startswith('refs/') else Git.kRefsHeads + rev

	def branchForName(rev):
		return rev.replace(Git.kRefsHeads, '') if rev.startswith(Git.kRefsHeads) else rev
