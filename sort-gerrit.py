#!/usr/bin/env python3

import sys

change_prefix = 'refs/changes/'

def keyfunc(s):
	ch = s.split('\t', maxsplit=1)[1].strip()
	if not ch.startswith(change_prefix):
		return s
	index, ps = ch[len(change_prefix) + 3:].split('/')
	return index.rjust(8, '0') + ps.rjust(4, '0')

lines = []
for line in sys.stdin:
	lines.append(line)

sorted_lines = sorted(lines, key=keyfunc)

for line in sorted_lines:
	print(line, end='')
