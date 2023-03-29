import typing as t
from dataclasses import dataclass
from urllib.parse import urlparse

from deploy.Windows.config import DeployConfig
from deploy.Windows.logger import logger
from deploy.Windows.utils import *


@dataclass
class DataDependency:
    name: str
    version: str

    def __post_init__(self):
        # uvicorn[standard] -> uvicorn
        self.name = re.sub(r'\[.*\]', '', self.name)
        # opencv_python -> opencv-python
        self.name = self.name.replace('_', '-').strip()
        # PyYaml -> pyyaml
        self.name = self.name.lower()
        self.version = self.version.strip()

    def __str__(self):
        return f'{self.name}=={self.version}'

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))


class PipManager(DeployConfig):
    @cached_property
    def pip(self):
        return f'"{self.python}" -m pip'

    @cached_property
    def python_site_packages(self):
        return os.path.abspath(os.path.join(self.python, '../Lib/site-packages')) \
            .replace(r"\\", "/").replace("\\", "/")

    @cached_property
    def list_installed_dependency(self) -> t.List[DataDependency]:
        data = []
        regex = re.compile(r'(.*)-(.*).dist-info')
        try:
            for name in os.listdir(self.python_site_packages):
                res = regex.search(name)
                if res:
                    dep = DataDependency(name=res.group(1), version=res.group(2))
                    data.append(dep)
        except FileNotFoundError as e:
            logger.error(e)
        return data

    @cached_property
    def list_required_dependency(self) -> t.List[DataDependency]:
        data = []
        regex = re.compile('(.*)==(.*)[ ]*#')
        file = self.filepath('./requirements.txt')
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f.readlines():
                    res = regex.search(line)
                    if res:
                        dep = DataDependency(name=res.group(1), version=res.group(2))
                        data.append(dep)
        except FileNotFoundError as e:
            logger.error(e)
        return data

    @cached_property
    def list_dependency_to_install(self) -> t.List[DataDependency]:
        """
        A poor dependency comparison, but much much faster than `pip install` and `pip list`
        """
        data = []
        for dep in self.list_required_dependency:
            if dep not in self.list_installed_dependency:
                data.append(dep)
        return data

    def pip_install(self):
        logger.hr('Update Dependencies', 0)

        if not self.InstallDependencies:
            logger.info('InstallDependencies is disabled, skip')
            return

        if not len(self.list_dependency_to_install):
            logger.info('All dependencies installed')
            return
        else:
            logger.info(f'Dependencies to install: {self.list_dependency_to_install}')

        # Install
        logger.hr('Check Python', 1)
        self.execute(f'"{self.python}" --version')

        arg = []
        if self.PypiMirror:
            mirror = self.PypiMirror
            arg += ['-i', mirror]
            # Trust http mirror or skip ssl verify
            if 'http:' in mirror or not self.SSLVerify:
                arg += ['--trusted-host', urlparse(mirror).hostname]
        elif not self.SSLVerify:
            arg += ['--trusted-host', 'pypi.org']
            arg += ['--trusted-host', 'files.pythonhosted.org']

        # Don't update pip, just leave it.
        # logger.hr('Update pip', 1)
        # self.execute(f'"{self.pip}" install --upgrade pip{arg}')
        arg += ['--disable-pip-version-check']

        logger.hr('Update Dependencies', 1)
        arg = ' ' + ' '.join(arg) if arg else ''
        self.execute(f'{self.pip} install -r {self.requirements_file}{arg}')
