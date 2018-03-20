
import sys
import os.path


kIncludeProjectsEnvVar = 'DEPO_INCLUDE_PROJECTS'
kExcludeProjectsEnvVar = 'DEPO_EXCLUDE_PROJECTS'


class Lib:
	def __init__(self):
		self.thisDir = os.path.realpath(os.getcwd())
		self.rootDir = self.__rootDir()
		self.projectName = os.path.relpath(self.thisDir, self.rootDir)

	def __rootDir(self):
		d = self.thisDir
		while not os.path.isdir(os.path.join(d, '.repo')):
			p = os.path.dirname(d)
			if p == d:
				raise ValueError('.repo not found')
			d = p
		return d

	def includeProjects(self, projects):
		os.environ[kIncludeProjectsEnvVar] = ':'.join(projects)

	def excludeProjects(self, projects):
		os.environ[kExcludeProjectsEnvVar] = ':'.join(projects)

	def check():
		Lib().__check()

	def __check(self):
		envIncludeProjects = os.environ.get(kIncludeProjectsEnvVar)
		if envIncludeProjects != None:
			projects = envIncludeProjects.split(':')
			if not self.projectName in projects:
				sys.exit()

		envExcludeProjects = os.environ.get(kExcludeProjectsEnvVar)
		if envExcludeProjects != None:
			projects = envExcludeProjects.split(':')
			if self.projectName in projects:
				sys.exit()
