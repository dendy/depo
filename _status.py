#!/usr/bin/env python3

import lib
lib.Lib.check()

import os
import sys
import argparse

import subprocess
import colorize
from repostat import Stat


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('-d', action='store_true', default=False)
	args = parser.parse_args()

	s = Stat(merges=False)

	if not s.has_info:
		sys.exit()

	tags = []
	if s.no_remote_revision:
		tags.append('MISSING_RREV')
	if s.dirty_files:
		tags.append('DIRTY')
	if not s.branch_name:
		tags.append('DETACHED')
	elif not s.is_tracking:
		tags.append('UNTRACKED')
	if s.filtered_revs:
		tags.append('HACKED')

	print(colorize.c(s.path, bright=True), end='')
	if s.branch_name:
		print(' ' + colorize.c('({})'.format(s.branch_name), color=colorize.GREEN), end='')
	if tags:
		print(' ' + ' '.join(colorize.c('[{}]'.format(tag), color=colorize.RED, bright=True) for tag in tags), end='')
	print()

	if s.no_remote_revision:
		print(f'ERROR: Missing manifest revision: rmeote: {s.remote} revision: {s.rrev}')

	if s.dirty_files:
		for dirty_file in s.dirty_files:
			print(dirty_file)

	if not s.commits is None:
		for c in s.commits:
			if not Stat.do_not_merge_filter(c):
				if not args.d:
					continue
				subject = colorize.c(Stat.DO_NOT_MERGE_PREFIX, color=colorize.RED, bright=True) \
					+ c.subject[len(Stat.DO_NOT_MERGE_PREFIX):]
			else:
				subject = c.subject
			print('{} {}'.format(colorize.c(c.hash[:7], color=colorize.YELLOW), subject))

	print()


if __name__ == '__main__':
	main()
