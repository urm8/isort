"""test"""
import errno
import os
from concurrent.futures import ProcessPoolExecutor
from os.path import abspath
from pathlib import Path
from typing import List

from isort import Config, files
from isort.api import sort_file


class DaemonAlreadyRunning(Exception):
    ...


class isortd:
    _fifo = '.isortd.fifo'
    _fin = f'{_fifo}.in'
    _fout = f'{_fifo}.out'

    def __init__(self, config: Config, ext_format=None):
        self.ext_format = ext_format
        self.config = config
        self.loop = None

    def __enter__(self):
        try:
            os.mkfifo(self._fin)
            self.executor = ProcessPoolExecutor()
        except OSError as oe:
            if oe.errno == errno.EEXIST:
                raise DaemonAlreadyRunning()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.remove(self._fin)
        self.executor.shutdown()

    def main(self):
        while 1:
            fd = os.open(self._fin, os.O_SYNC | os.O_RDONLY | os.O_CREAT)
            with open(fd, 'r') as pipe:
                while 1:
                    data = pipe.read()
                    if len(data) == 0:
                        print('pipe closed')
                        break
                    file_names = map(str.rstrip, data.splitlines())

                    skipped: List[str] = []
                    broken: List[str] = []

                    if self.config.filter_files:
                        filtered_files = []
                        for file_name in file_names:
                            if self.config.is_skipped(Path(file_name)):
                                skipped.append(file_name)
                            else:
                                filtered_files.append(file_name)
                        file_names = filtered_files

                    file_names = files.find(file_names, self.config, skipped, broken)
                    for file in file_names:
                        self.executor.submit(
                            sort_file,
                            file_name=file,
                            config=self.config,
                            disregard_skip=False,
                            ask_to_apply=False,
                            write_to_stdout=False,
                        )

    @classmethod
    def sort(self, *fp: str) -> None:
        fd = os.open(self._fin, os.O_SYNC | os.O_RDWR)
        with open(fd, 'w') as fout:
            files = ''.join(map('{}\n'.format, map(abspath, fp)))
            fout.write(files)
