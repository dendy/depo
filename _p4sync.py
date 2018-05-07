#!/usr/bin/env python3

import lib
lib.Lib.check()

import os.path
import sys
from git import Git
from repostat import Stat

s = Stat(False, False)

rev = s.git.run(['ls-remote', '--exit-code', s.remote, 'refs/remotes/p4/master']).stdout.split(maxsplit=1)[0]

remote_dir = os.path.join(s.git.dir, '.git/refs/remotes/p4')
os.makedirs(remote_dir, exist_ok=True)

open(os.path.join(remote_dir, 'HEAD'), 'w').write('ref: refs/remotes/p4/master\n')

with open(os.path.join(remote_dir, 'master'), 'w') as f:
	f.write(rev)
	f.write('\n')
