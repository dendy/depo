#!/usr/bin/env python3

import json
import os.path
import subprocess
import argparse
import io
import sys
import enum
import queue
import threading


kDebugTasks = False


class Project:
	def __init__(self, project, tree):
		tokens = project.split('|')

		self.name = tokens[0]
		self.binary = False
		self.sync = 10
		self.map = None
		self.tree = tree

		for token in tokens[1:]:
			key, value = Project.__parseToken(token)
			if key == 'b':
				self.binary = True
			elif key == 's':
				self.sync = 0 if value == None else int(value)
			elif key == 'm':
				self.map = value
			else:
				raise ValueError('Invalid token key:', key)

	def __parseToken(token):
		index = token.find('=')
		if index == 0:
			raise ValueError('Invalid token:', token)
		return (token, None) if index == -1 else (token[:index], token[index+1:])

	def localPath(self):
		treePath = self.tree.localPath()
		selfPath = self.map if self.map else self.name
		return os.path.normpath(os.path.join(treePath, selfPath) if treePath else selfPath)

	def remotePath(self):
		treePath = self.tree.remotePath()
		selfPath = self.name
		return os.path.join(treePath, selfPath) if treePath else selfPath


class Tree:
	def __init__(self, root, name, parent):
		tree = root['tree-' + name]

		self.name = name
		self.parent = parent
		self.path = tree.get('path')
		self.map = tree.get('map')
		self.projectForName = dict()
		self.treeForName = dict()

		projects = tree.get('projects')
		if projects:
			for project in projects:
				p = Project(project, self)
				self.projectForName[p.name] = p

		trees = tree.get('trees')
		if trees:
			for name in trees:
				t = Tree(tree, name, self)
				self.treeForName[t.name] = t

	def localPath(self):
		if not self.parent:
			return None
		parentPath = self.parent.localPath()
		selfPath = self.map if self.map else self.name
		return os.path.normpath(os.path.join(parentPath, selfPath) if parentPath else selfPath)

	def remotePath(self):
		if not self.parent:
			return self.path
		parentPath = self.parent.remotePath()
		return os.path.join(parentPath, self.name) if parentPath else self.name

	def load(config):
		projectForName = dict()
		Tree.__parseTrees([Tree(config, 'root', None)], projectForName)
		return projectForName

	def __parseTrees(trees, projectForName):
		if not trees:
			return

		tree = trees.pop()

		for p in tree.projectForName.values():
			path = p.localPath()
			if path in projectForName:
				raise ValueError('Duplicated project path:', path)
			for ep in projectForName.keys():
				if not os.path.relpath(ep, path).startswith('..') or \
						not os.path.relpath(path, ep).startswith('..'):
					raise ValueError('Conflicting project paths:', ep, path)
			projectForName[path] = p

		Tree.__parseTrees(trees + list(tree.treeForName.values()), projectForName)


class Task:
	def __init__(self, config, project, tryCount):
		self.config = config
		self.project = project
		self.tryCount = tryCount

		self.process = None

		self.path = self.project.localPath()
		self.prefix = ('project: ' + self.path).ljust(40, '.')

		self.completed = False
		self.ok = False
		self.report = False

		self.status = None

	def dprint(self, *args):
		if kDebugTasks:
			print(*args)

	def isCompleted(self):
		return not self.process or self.process.returncode != None

	def __thread(self):
		for line in self.process.stdout:
			self.q.put(line)

	def __collectErrorStatus(self, proc):
		return f'error (out={proc.stdout.read()}\n\n err={proc.stderr.read()}\n\n)'

	def run(self):
		self.gitDir = os.path.abspath(self.path + '.git')
		self.importedCount = 0

		self.isCloning = not os.path.exists(self.gitDir)

		self.status = 'starting'

		try:
			if self.isCloning:
				os.makedirs(self.gitDir)

				subprocess.run(['git', '-C', self.gitDir, 'init', '--bare'], check=True)
				subprocess.run(['git', '-C', self.gitDir, 'config', 'git-p4.user', self.config['user']],
						check=True)
				subprocess.run(['git', '-C', self.gitDir, 'config', 'git-p4.port', self.config['port']],
						check=True)

				depotPath = self.project.remotePath()

				if not self.project.binary:
					depotPath += '@all'

				self.process = subprocess.Popen(['git', '-C', self.gitDir, 'p4', 'sync', depotPath],
						stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
			else:
				self.fetchBegin = subprocess.run(['git', '-C', self.gitDir, 'rev-parse',
						'refs/remotes/p4/master'], check=True, stdout=subprocess.PIPE,
						universal_newlines=True).stdout.strip()

				self.process = subprocess.Popen(['git', '-C', self.gitDir, 'p4', 'sync'],
						stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		except subprocess.CalledProcessError as e:
			self.status = self.__collectErrorStatus(e)
			self.completed = True

			if self.isCloning and os.path.exists(self.gitDir):
				shutil.rmtree(self.gitDir)

			return

		self.q = queue.Queue()
		self.thread = threading.Thread(target=Task.__thread, args=(self,))
		self.thread.daemon = True
		self.thread.start()

		self.status = self.operationName() + '...'

	def operationName(self):
		op = 'cloning' if self.isCloning else 'fetching'
		if self.tryCount != 0:
			op += f' (tries={self.tryCount})'
		return op

	def update(self):
		try:
			self.dprint('waiting for...', self.project.localPath())
			self.process.wait(timeout=0.1)
			self.dprint('waiting for...', self.project.localPath(), 'done', self.process.returncode)

			if self.process.returncode != None:
				if self.process.returncode != 0:
					self.status = self.__collectErrorStatus(self.process)
					self.completed = True
				else:
					# move the master branch to p4/master
					subprocess.run(['git', '-C', self.gitDir, 'branch', '-f', 'master',
							'refs/remotes/p4/master'], check=True)

					self.status = self.operationName() + '... DONE'

					if self.isCloning:
						self.report = True
					else:
						fetchCount = len(subprocess.run(['git', '-C', self.gitDir, 'log',
								'--oneline', self.fetchBegin + '..refs/remotes/p4/master'],
								check=True, stdout=subprocess.PIPE, universal_newlines=True)
								.stdout.splitlines())

						if fetchCount != 0:
							self.status += f' ({fetchCount})'
							self.report = True

					self.ok = True
					self.completed = True
		except subprocess.TimeoutExpired:
			self.dprint('waiting for...', self.project.localPath(), 'timeout', self.process.stdout)
			self.dprint('reading...')

			try:
				while True:
					line = self.q.get_nowait() # or q.get(timeout=.1)
					self.dprint('line:', line)
					if line.startswith('Importing revision'):
						self.importedCount += 1
						self.status = self.operationName() + '... ' + line.rstrip()
			except queue.Empty:
				self.dprint('no output yet')

			self.dprint('waiting for...', self.project.localPath(), 'timeout done')


class Main:
	kMaxTasks = 8

	def __init__(self):
		parser = argparse.ArgumentParser()
		parser.add_argument('projects', nargs='*')
		self.args = parser.parse_args()

		with open('config.json', 'r') as configFile:
			self.config = json.loads(configFile.read())

		self.projectForPath = Tree.load(self.config)

		unknownProjectNames = [p for p in self.args.projects if p not in self.projectForPath]
		if unknownProjectNames:
			raise ValueError("Unknown projects:", unknownProjectNames)

	def printTask(self, task):
		print(f'{task.prefix} {task.status}')
		sys.stdout.flush()

	def updateTasks(self):
		needUpdate = False

		completedTasks = []

		for task in self.tasks[:]:
			oldStatus = task.status
			task.update()

			if task.completed:
				if not task.ok:
					taskIndex = self.tasks.index(task)
					self.tasks.remove(task)
					task = Task(self.config, task.project, task.tryCount + 1)
					task.run()
					self.tasks.insert(taskIndex, task)
				else:
					self.tasks.remove(task)
					completedTasks.append(task)
				needUpdate = True
			else:
				needUpdate |= task.status != oldStatus

		for i in range(len(self.tasks), Main.kMaxTasks):
			if not self.remainingProjects:
				break

			task = Task(self.config, self.remainingProjects.pop(), 0)

			if self.args.projects and task.project.localPath() not in self.args.projects:
				completedTasks.append(task)
			else:
				self.tasks.append(task)
				task.run()

			needUpdate = True

		return needUpdate, completedTasks

	def eraseTaskLog(self):
		if kDebugTasks:
			print('-' * 40)
		else:
			for _ in range(self.grandLineCount + len(self.visibleTasks)):
				sys.stdout.write('\x1b[1A')
				sys.stdout.write('\x1b[2K')

		self.visibleTasks = []
		self.grandLineCount = 0

	def completeTasks(self, tasks):
		self.grandLineCount = 4
		self.completedTasks += tasks

		for task in tasks:
			if (task.completed and not task.ok) or task.report:
				self.printTask(task)
			if task.completed:
				self.processedTaskCount += 1

		print()
		print('-' * 40)
		print(f'Working: {self.processedTaskCount}/{self.totalTaskCount}')
		print()

	def printTaskLog(self):
		for task in self.tasks:
			self.printTask(task)
			self.visibleTasks.append(task)

	def exec(self):
		self.remainingProjects = list(self.projectForPath.values())
		self.completedTasks = []
		self.processedTaskCount = 0
		self.totalTaskCount = len(self.args.projects) if self.args.projects else len(self.remainingProjects)
		self.visibleTasks = []
		self.grandLineCount = 0
		self.tasks = []

		print('-' * 40)

		while self.tasks or self.remainingProjects:
			needUpdate, completedTasks = self.updateTasks()

			if needUpdate:
				self.eraseTaskLog()
				self.completeTasks(completedTasks)
				self.printTaskLog()

if __name__ == '__main__':
	try:
		Main().exec()
	except subprocess.CalledProcessError as e:
		print(f'Subcommand failed (exit code: {e.returncode}):', e.cmd, file=sys.stderr)
		print('Output:', e.output, file=sys.stderr)
		print('Error:', e.stderr.read(), file=sys.stderr)
		sys.stderr.flush()
		sys.exit(1)
