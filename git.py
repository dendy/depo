
import subprocess

class Git:
	kRefsHeads = 'refs/heads/'
	kRefsTags = 'refs/tags/'

	def __init__(self, dir=None):
		self.dir = dir

	def run(self, args, check=True, color=False, encode=True):
		local_args = ['-C', self.dir] if self.dir != None else []
		color_args = ['-c', f'color.ui={"always" if color else "never"}']

		return subprocess.run(['git'] + local_args + ['--no-pager']
				+ color_args + args,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE, universal_newlines=encode,
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

	def get_commit_id_rev(self, rev):
		try:
			commit_id = self.run(['rev-parse', rev]).stdout.strip()
			if commit_id.startswith(rev):
				return commit_id
		except subprocess.CalledProcessError:
			pass

	def valid_remote_revision(self, remote, rev):
		# if this is a commit id or short commit id then return it as is
		commit_id = self.get_commit_id_rev(rev)
		if not commit_id is None:
			return commit_id

		# if this is a tag then return it as is
		if rev.startswith(Git.kRefsTags):
			# validate it exists
			self.run(['rev-parse', rev])
			return rev

		# if this is a short tag
		maybe_full_tag = f'{Git.kRefsTags}{rev}'
		if self.exists(maybe_full_tag):
			return maybe_full_tag

		# if this is a full branch name
		if rev.startswith(Git.kRefsHeads):
			short_branch_name = rev[len(Git.kRefsHeads):]
		else:
			# should be a short branch name then
			short_branch_name = rev
		remote_rev = f'{remote}/{short_branch_name}'
		# check it exists
		if self.exists(remote_rev):
			return remote_rev

	def optional_remote_revision(self, remote, rev):
		if rev.startswith(Git.kRefsHeads):
			return rev.replace(Git.kRefsHeads, remote + '/', 1)
		if rev.startswith('refs/'):
			return rev
		return remote + '/' + rev

	def remote_local_revision(self, rev):
		# if this is a commit id or short commit id then return it as is
		commit_id = self.get_commit_id_rev(rev)
		if not commit_id is None:
			return commit_id
		if rev.startswith('refs/'):
			return rev
		else:
			return Git.kRefsHeads + rev

	def branchForName(rev):
		return rev.replace(Git.kRefsHeads, '') if rev.startswith(Git.kRefsHeads) else rev
