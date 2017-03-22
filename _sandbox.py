#!/usr/bin/env python3

import argparse
from repostat import Stat
import colorize

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', dest='dry_run', action='store_true')
parser.add_argument('--remote')
parser.add_argument('branch')
args = parser.parse_args()

s = Stat()

remote = args.remote if args.remote else s.remote
remote_branch = 'refs/sandbox/' + args.branch

try:
	s.git.run(['fetch', s.remote, remote_branch], color=False)
	commits = s.git.run(['log', '--oneline', '--format=%H', 'FETCH_HEAD..HEAD'], color=False).stdout.splitlines()
except:
	commits = s.commits

number_of_commits = len(commits) - len(s.filtered_revs)

if commits:
	print(colorize.c(s.path, bright=True) + ': ', end='')
	commits_message = str(number_of_commits) + ' commit' + ('s' if number_of_commits > 1 else '')
	if args.dry_run:
		print('Would push {} into remote={} branch={}'.format(commits_message,
				remote, remote_branch))
	else:
		s.git.run(['push', remote, 'HEAD:' + remote_branch])
		print(colorize.c('Pushed ' + commits_message, color=colorize.GREEN, bright=True))
