#!/usr/bin/env python3


import argparse
import os.path
import subprocess


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('--command', required=True)
	parser.add_argument('--output', required=True)
	args, cli = parser.parse_known_args()

	output_dir = f'{args.output}-{args.command}'

	os.makedirs(output_dir, exist_ok=True)

	path = os.environ['REPO_PATH'].replace('/', '__')

	r = subprocess.run(cli, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

	if r.returncode != 0:
		with open(f'{output_dir}/{path}.returncode_{r.returncode}.log', 'w') as f:
			pass

	if len(r.stdout) != 0:
		with open(f'{output_dir}/{path}_stdout.log', 'w') as f:
			f.write(r.stdout)

	if len(r.stderr) != 0:
		with open(f'{output_dir}/{path}_stderr.log', 'w') as f:
			f.write(r.stderr)


if __name__ == '__main__':
	main()
