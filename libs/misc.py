# encoding: utf-8
from logging import Handler
from PySide.QtCore import *


class DirEntry(object):
    def __init__(self,
                 attr='',
                 subdir_num='',
                 owner='', owner_group='',
                 size='',
                 month='', day='', year='', hour='', minute='', second='',
                 name='',
                 is_file=''):
        self.attr = attr.decode('utf-8')
        self.subdir_num = subdir_num.decode('utf-8')
        self.owner = owner.decode('utf-8')
        self.owner_group = owner_group.decode('utf-8')
        self.size = size.decode('utf-8')
        self.month = month.decode('utf-8')
        self.day = day.decode('utf-8')
        self.year = year.decode('utf-8')
        self.name = name.decode('utf-8')
        self.is_file = is_file


    def is_dir(self):
        return not self.is_file



class LoggerHandler(Handler):
    def __init__(self, logger_widget):
        self.logger_widget = logger_widget
        super(LoggerHandler, self).__init__()


    def emit(self, record):
        self.logger_widget.emit(SIGNAL('new_log(QString)'), self.format(record))


