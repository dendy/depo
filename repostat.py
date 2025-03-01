
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

		is_rrev_ref = self.rrev.startswith('refs/')
		is_rrev_ref_heads = is_rrev_ref and self.rrev.startswith('refs/heads/')

		self.remote_revision = self.git.valid_remote_revision(self.remote, self.rrev)
		self.remote_local_revision = self.git.remote_local_revision(self.rrev)

		if commits:
			self.no_remote_revision = False
			self.commits = None

			if self.remote_revision is None:
				# revision from manifest does not exist in local git repo
				self.no_remote_revision = True
			else:
				args = ['log', '--oneline'] \
						+ (['--no-merges'] if not merges else []) \
						+ ['--format=%H %s']\
						+ [self.remote_revision + '..HEAD']

				self.commits = [Commit(l) for l in self.git.run(args, color=False, encode=False) \
						.stdout.replace(b'\r', b'').decode() \
						.splitlines()]

			if self.commits is None:
				self.filtered_revs = None
			else:
				self.filtered_revs = [c.hash for c in self.commits for f in Stat.filters if not f(c)]

			self.dirty_files = self.git.run(['status', '-s'], color=True).stdout.splitlines()

			self.has_info = self.no_remote_revision or self.commits or self.dirty_files or self.filtered_revs

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
