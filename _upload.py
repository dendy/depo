#!/usr/bin/env python3

import os
import sys
import argparse
from git import Git
import colorize
from repostat import Stat

depo_cwd = os.environ.get('DEPO_CWD')
if depo_cwd and depo_cwd != os.getcwd():
	sys.exit()

def unhacked_head(s):
	head = s.git.run(['rev-parse', 'HEAD']).stdout.strip()
	if not s.filtered_revs:
		return head
	if not head in s.filtered_revs:
		raise RuntimeError('Found hacked commits below HEAD')
	heads = set()
	for rev in s.filtered_revs:
		for parent in s.git.run(['show', '--format=%P', '-s']).stdout.splitlines():
			if not parent in s.filtered_revs:
				heads.add(parent)
	if not heads:
		raise RuntimeError('No head found under hacked commits')
	if len(heads) != 1:
		raise RuntimeError('Too many heads found under hacked commits: ' + str(heads))
	return list(heads)[0]

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', dest='dry_run', action='store_true')
args = parser.parse_args()

s = Stat()

number_of_commits = len(s.commits) - len(s.filtered_revs)

if number_of_commits == 0:
	sys.exit()

print(colorize.c(s.path, bright=True) + ': ', end='')

try:
	rev_to_push = unhacked_head(s)
except RuntimeError as e:
	print(colorize.c(str(e), color=colorize.RED, bright=True))
	sys.exit(0)

commits_message = str(number_of_commits) + ' commit' + ('s' if number_of_commits > 1 else '')
if args.dry_run:
	print('Would push ' + commits_message)
else:
	s.git.run(['push', s.remote, rev_to_push + ':' + s.remote_local_revision])
	s.git.run(['fetch', s.remote])
	print(colorize.c('Pushed ' + commits_message, color=colorize.GREEN, bright=True))
