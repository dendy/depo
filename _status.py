#!/usr/bin/env python3

import lib
lib.Lib.check()

import os
import sys
import argparse

import subprocess
from git import Git
import colorize
from repostat import Stat

parser = argparse.ArgumentParser()
parser.add_argument('-d', action='store_true', default=False)
args = parser.parse_args()

s = Stat(merges=False)

if not s.has_info:
	sys.exit()

tags = []
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

if s.dirty_files:
	print('\n'.join(s.dirty_files))

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
