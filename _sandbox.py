#!/usr/bin/env python3

import argparse
from repostat import Stat
import colorize
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', dest='dry_run', action='store_true')
parser.add_argument('--remote')
parser.add_argument('command', choices=['push', 'pull'])
parser.add_argument('branch')
args = parser.parse_args()

s = Stat()

remote = args.remote if args.remote else s.remote
remote_branch = 'refs/sandbox/' + args.branch

try:
	s.git.run(['fetch', s.remote, remote_branch], color=False)
	has_fetch = True
except:
	has_fetch = False

if args.command == 'push':
	commits = s.git.run(['log', '--oneline', '--format=%H', 'FETCH_HEAD..HEAD'], color=False) \
		.stdout.splitlines() if has_fetch else s.commits

	number_of_commits = len(commits)

	if commits:
		print(colorize.c(s.path, bright=True) + ': ', end='')
		commits_message = str(number_of_commits) + ' commit' + ('s' if number_of_commits > 1 else '')
		if args.dry_run:
			print('Would push {} into remote={} branch={}'.format(commits_message,
					remote, remote_branch))
		else:
			s.git.run(['push', remote, 'HEAD:' + remote_branch])
			print(colorize.c('Pushed ' + commits_message, color=colorize.GREEN, bright=True))
elif args.command == 'pull':
	if has_fetch:
		commits = s.git.run(['log', '--oneline', '--format=%H', 'HEAD..FETCH_HEAD'], color=False).stdout.splitlines()

		if commits:
			print(colorize.c(s.path, bright=True) + ': ', end='')
			if s.commits and (s.dirty_files or not s.branch_name):
				print('Cannot switch to sandbox branch because project is dirty')
				sys.exit(1)

			if args.dry_run:
				print('Would checkout')
			else:
				s.git.run(['checkout', 'FETCH_HEAD'], color=False)
				print('DONE')
