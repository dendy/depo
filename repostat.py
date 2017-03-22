
import os
from git import Git
import colorize
import subprocess

class Commit:
	def __init__(self, log):
		self.hash, self.subject = log.split(maxsplit=1)

class Stat:
	DO_NOT_MERGE_PREFIX = 'DO NOT MERGE'

	def do_not_merge_filter(c):
		return not c.subject.startswith(Stat.DO_NOT_MERGE_PREFIX)

	filters = [do_not_merge_filter]

	def __init__(self, merges=True, commits=True):
		self.git = Git()

		self.remote = os.environ['REPO_REMOTE']
		self.path = os.environ['REPO_PATH']
		self.rrev = os.environ['REPO_RREV']

		self.branch_name = None
		self.is_tracking = False

		remote_revision = self.rrev if self.rrev.startswith('refs/') else self.remote + '/' + self.rrev
		self.remote_local_revision = self.rrev if self.rrev.startswith('refs/') else 'refs/heads/' + self.rrev

		if commits:
			self.commits = [Commit(l) for l in self.git.run(['log', '--oneline'] \
					+ (['--no-merges'] if not merges else []) \
					+ ['--format=%H %s']\
					+ [remote_revision + '..HEAD'], \
					color=False) \
					.stdout.splitlines()]

			self.filtered_revs = [c.hash for c in self.commits for f in Stat.filters if not f(c)]

			self.dirty_files = self.git.run(['status', '-s'], color=True).stdout.splitlines()

			self.has_info = self.commits or self.dirty_files or self.filtered_revs

			if self.has_info:
				# resolve branch name and tracking flag
				if self.git.run(['rev-parse', '--symbolic-full-name', 'HEAD']).stdout.strip() != 'HEAD':
					self.branch_name = self.git.run(['rev-parse', '--abbrev-ref=loose', 'HEAD']).stdout.strip()

					try:
						branch_remote = self.git.run(['config', 'branch.' + self.branch_name + '.remote']).stdout.strip()
						branch_merge = self.git.run(['config', 'branch.' + self.branch_name + '.merge']).stdout.strip()
						self.is_tracking = branch_remote == self.remote and branch_merge == self.remote_local_revision
					except subprocess.CalledProcessError:
						pass
