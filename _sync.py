#!/usr/bin/env python3

import lib
lib.Lib.check()

import sys
import os.path
import argparse
import subprocess

from git import Git
from repostat import Stat
import colorize


parser = argparse.ArgumentParser()
action_group = parser.add_mutually_exclusive_group()
action_group.add_argument('--abort', required=False)
action_group.add_argument('--prepare', required=False)
action_group.add_argument('--complete', required=False)
action_group.add_argument('--upload', required=False)
args = parser.parse_args()


s = Stat()

print(colorize.c(s.path, bright=True))

branch = args.abort or args.prepare or args.upload or args.complete
kPrepareRevision = 'refs/prepare/' + branch


def create_prepare_branch(rev):
	oldrev = s.git.headRev()

	print('Creating prepare branch...')
	s.git.run(['branch', kPrepareRevision, rev])
	s.git.run(['config', 'branch.' + kPrepareRevision + '.oldrev', oldrev])


def do_checkout_old():
	oldrev = s.git.run(['config', 'branch.' + kPrepareRevision + '.oldrev']).stdout.strip()
	print(f'Switching to old rev: {oldrev}')
	s.git.run(['checkout', Git.branchForName(oldrev)])


def checkout_old(force):
	if not s.git.exists(kPrepareRevision):
		print('Prepare branch does not exist')
		return

	if force:
		do_checkout_old()
		return

	if s.git.headRev() != kPrepareRevision:
		print(colorize.c('Prepare branch exists but not current', color=colorize.RED), file=sys.stderr)
		exit(1)


def delete_prepare_branch():
	if s.git.exists(kPrepareRevision):
		s.git.run(['branch', '-D', kPrepareRevision])


if args.prepare:
	if os.path.isdir(os.path.join(s.git.dir, 'rebase-merge')):
		print(colorize.c('Git project is in the middle of something, aborting', color=colorize.RED), file=sys.stderr)
		sys.exit(1)

	if s.git.exists(kPrepareRevision):
		if s.git.isFf(kPrepareRevision, s.remote_revision):
			print('Already prepared')
			sys.exit(0)

		print(colorize.c('Prepared branch outdated', color=colorize.RED), file=sys.stderr)
		sys.exit(1)

	target_rev = s.git.optional_remote_revision(s.remote, branch)
	target_rev_exists = s.git.exists(target_rev)

	if target_rev_exists:
		if s.git.isFf(target_rev, s.remote_revision):
			print('Already up-to-date')
			sys.exit(0)

	create_prepare_branch(target_rev)

	print('Prepared branch diverged, rebasing...')
	s.git.run(['rebase', '--onto', s.remote_revision, s.remote_revision, kPrepareRevision])


if args.complete:
	checkout_old(True)
	delete_prepare_branch()


if args.upload:
	if not s.git.exists(kPrepareRevision):
		print('No prepare branch, skipping')
	else:
		print('Pushing prepare branch...')
		s.git.run(['push', '-f', s.remote, kPrepareRevision + ':' + branch])


if args.abort:
	checkout_old(True)
	delete_prepare_branch()


print()
