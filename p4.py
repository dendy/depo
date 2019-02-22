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

from git import Git


kDebugTasks = True


class Project:
	def __init__(self, project, tree):
		tokens = project.split('|')

		self.name = tokens[0]
		self.binary = False
		self.sync = 10
		self.map = None
		self.tree = tree
		self.client = None
		self.enabled = True

		for token in tokens[1:]:
			key, value = Project.__parseToken(token)
			if key == 'b':
				self.binary = True
			elif key == 's':
				self.sync = 0 if value == None else int(value)
			elif key == 'm':
				self.map = value
			elif key == 'client':
				self.client = value
			elif key == '-':
				self.enabled = False
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
		if self.client:
			return treePath
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

		clients = tree.get('clients')
		if clients:
			for client in clients:
				p = Project

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
	def __init__(self, config, project, tryCount, error):
		self.config = config
		self.project = project
		self.tryCount = tryCount
		self.lastError = error

		self.process = None

		self.path = self.project.localPath()
		self.prefix = ('project: ' + self.path).ljust(40, '.')

		self.completed = False
		self.ok = False
		self.report = False

		self.status = None

	def dprint(self, *args):
		if kDebugTasks:
			print(self.path, *args)

	def isCompleted(self):
		return not self.process or self.process.returncode != None

	def __thread(self):
		for line in self.process.stdout:
			self.q.put(line)

	def __collectErrorStatus(self, proc):
		return f'error (out={proc.stdout}\n\n err={proc.stderr}\n\n)'

	def run(self):
		self.git = Git(os.path.abspath(self.path + '.git'))
		self.importedCount = 0

		self.isCloning = not os.path.exists(self.git.dir)
		print(self.git.dir, 'cloning:', self.isCloning)

		self.status = 'starting'

		try:
			if self.isCloning:
				os.makedirs(self.git.dir)

				self.git.run(['init', '--bare'])
				self.git.run(['config', 'git-p4.user', self.config['user']])
				self.git.run(['config', 'git-p4.port', self.config['port']])

				if self.project.client:
					self.git.run(['config', 'git-p4.client', self.project.client])

				depotPath = self.project.remotePath()

				if not self.project.binary:
					depotPath += '@all'

				clientArgs = ['--use-client-spec'] if self.project.client else []

				self.dprint(f'doing p4 sync: clientArgs={clientArgs} depotPath={depotPath}')
				self.process = subprocess.Popen(['git', '-C', self.git.dir, 'p4', 'sync'] + clientArgs + [depotPath],
						stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
			else:
				self.fetchBegin = self.git.commitId('refs/remotes/p4/master')

				self.process = subprocess.Popen(['git', '-C', self.git.dir, 'p4', 'sync'],
						stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
		except subprocess.CalledProcessError as e:
			self.lastError = self.__collectErrorStatus(e)
			self.dprint('lastError:', self.lastError)
			self.completed = True

			if self.isCloning and os.path.exists(self.git.dir):
				shutil.rmtree(self.git.dir)

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
		if self.lastError:
			op += f' error={self.lastError}';
		return op

	def update(self):
		try:
			self.dprint('waiting for...', self.project.localPath())
			self.process.wait(timeout=1)
			self.dprint('waiting for...', self.project.localPath(), 'done', self.process.returncode)

			if self.process.returncode != None:
				if self.process.returncode != 0:
					self.lastError = self.__collectErrorStatus(self.process)
					self.completed = True
				else:
					# move the master branch to p4/master
					p4MasterCommitId = self.git.commitId('refs/remotes/p4/master')
					with open(os.path.join(self.git.dir, 'refs/heads/master'), 'w') as f:
						print(p4MasterCommitId, file=f)

					self.status = self.operationName() + '... DONE'

					if self.isCloning:
						self.report = True
					else:
						fetchCount = len(self.git.run(['log', '--oneline',
								self.fetchBegin + '..refs/remotes/p4/master'])
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
		parser.add_argument('--download', required=False, action='store_true')
		parser.add_argument('--upload', required=False, action='store_true')
		parser.add_argument('-j', required=False, type=int, default=Main.kMaxTasks)
		parser.add_argument('projects', nargs='*')
		self.args = parser.parse_args()

		useDefaultSyncFlags = not self.args.download and not self.args.upload
		self.doDownload = True if useDefaultSyncFlags else self.args.download
		self.doUpload = True if useDefaultSyncFlags else self.args.upload

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
					task = Task(self.config, task.project, task.tryCount + 1, task.lastError)
					task.run()
					self.tasks.insert(taskIndex, task)
				else:
					self.tasks.remove(task)
					completedTasks.append(task)
				needUpdate = True
			else:
				needUpdate |= task.status != oldStatus

		for i in range(len(self.tasks), self.args.j):
			if not self.remainingProjects:
				break

			task = Task(self.config, self.remainingProjects.pop(), 0, None)

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

	def upload(self):
		with open('p4-upload.json', 'r') as f:
			config = json.loads(f.read())
			host = config['host']
			subdir = config['subdir']
			fromdir = config['fromdir']
			branch = config['branch']

		def gexec(command, *args):
			nonlocal host
			return subprocess.run(['ssh', host, 'gerrit', command, *args], \
					stdout=subprocess.PIPE,
					universal_newlines=True,
					check=True).stdout

		# get list of all projects
		allGerritProjects = gexec('ls-projects').splitlines()

		subdirPrefix = '' if not subdir else subdir + '/'
		fromDir = '.' if not fromdir else fromdir
		uploadGerritProjects = [p[len(subdirPrefix):] for p in allGerritProjects if p.startswith(subdirPrefix)]

		for project in list(self.projectForPath.values()):
			path = project.localPath()

			if path.startswith(fromDir + '/'):
				path = path[len(fromDir) + 1:]

			exists = path in uploadGerritProjects

			print('project:', project.localPath(), exists)

			# create project on gerrit if it is not exist
			if not exists:
				gexec('create-project',
					'--parent', 'roku-settings',
					subdirPrefix + path
				)

			gitUrl = 'ssh://' + host + '/' + subdirPrefix + path

			# fetch changes from remote repository
			git = Git(os.path.abspath(project.localPath() + '.git'))
			localId = git.commitId('refs/remotes/p4/master')

			try:
				remoteId = git.run(['ls-remote', '--exit-code', gitUrl, branch]).stdout.split(maxsplit=1)[0]
				if remoteId == localId:
					# nothing to upload, skip
					continue
			except subprocess.CalledProcessError as e:
				# no remote id, this is ok, create a new branch
				pass

			git.run(['push', '-o', 'skip-validation', gitUrl, localId + ':' + branch])


	def download(self):
		self.remainingProjects = [p for p in list(self.projectForPath.values()) if p.enabled]
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

	def exec(self):
		if self.doDownload:
			self.download()
		if self.doUpload:
			self.upload()

if __name__ == '__main__':
	try:
		Main().exec()
	except subprocess.CalledProcessError as e:
		print(f'Subcommand failed (exit code: {e.returncode}):', e.cmd, file=sys.stderr)
		print('Output:', e.output, file=sys.stderr)
		print('Error:', e.stderr if type(e.stderr) == str else e.stderr.read(), file=sys.stderr)
		sys.stderr.flush()
		sys.exit(1)
