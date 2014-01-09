# encoding: utf-8
import os
import threading
import sys

from PySide.QtGui import *
from PySide.QtCore import *

from libs.ftp import FTPClient
from libs.misc import LoggerHandler
from libs.components import LoginDialog, FileModel


class FTPClientPanel(QDialog, object):

    signal_list_end = Signal(list)
    signal_download_end = Signal(bool)
    signal_download_start = Signal()
    signal_upload_end = Signal(bool)
    signal_upload_start = Signal()

    def __init__(self, server_ip):
        super(FTPClientPanel, self).__init__()

        self.client = FTPClient(server_ip)

        self.entries = []

        self.setMinimumWidth(400)
        self.setWindowTitle('FTPient')

        self.widget_logger = QTextBrowser(self)

        self.btn_upload = QPushButton(u'上传到此处')
        self.btn_download = QPushButton(u'下载')
        self.btn_show_logger = QPushButton(u'日志')
        self.btn_login = QPushButton(u'登录')

        self.view_ftp = QTreeView(self)
        self.view_ftp.setItemsExpandable(False)
        self.view_ftp.setExpandsOnDoubleClick(False)
        self.view_ftp.setRootIsDecorated(False)
        self.model = FileModel(self.entries, self)
        self.view_ftp.setModel(self.model)

        self.dialog_logger = QDialog(self)
        self.dialog_login = LoginDialog(self)

        self.setup_layout()
        self.setup_logger()

        self.lock()

        self.signal_list_end.connect(self.show_list)
        self.signal_download_start.connect(self.download_start)
        self.signal_download_end.connect(self.download_end)
        self.signal_upload_start.connect(self.upload_start)
        self.signal_upload_end.connect(self.upload_end)

        self.view_ftp.doubleClicked.connect(self.double_click_item)

        self.current_ftp_path = '/'

    def double_click_item(self, idx):
        entry = self.model.data(idx, role=Qt.UserRole)
        if entry.is_dir():
            self.current_ftp_path = os.path.normpath(os.path.join(self.current_ftp_path, entry.name))
            self.client._m_logger.info(self.current_ftp_path)
            self.asynchronized_list(self.current_ftp_path)
        else:
            self.download()


    def download(self):
        idx = self.view_ftp.selectedIndexes()
        if not idx:
            return

        idx = idx[0]
        entry = self.model.data(idx, role=Qt.UserRole)

        save_path, _ = QFileDialog.getSaveFileName(self,
                                                   u'下载至',
                                                   os.path.join('.', entry.name),
                                                   u'所有文件 (*.*)')

        self.asynchronized_download(os.path.join(self.current_ftp_path,
                                                 entry.name),
                                    save_path)


    def upload(self):
        path, _ = QFileDialog.getOpenFileName(self,
                                              u'上传文件',
                                              '.',
                                              u'所有文件 (*.*)')
        _, filename = os.path.split(path)
        self.asynchronized_upload(filename, path)


    def setup_layout(self):
        grid = QGridLayout()
        grid.addWidget(self.view_ftp, 0, 0, 1, 2)
        grid.addWidget(self.btn_upload, 1, 0, 1, 1)
        grid.addWidget(self.btn_login, 1, 1, 1, 1)
        grid.addWidget(self.btn_download, 2, 0, 1, 1)
        grid.addWidget(self.btn_show_logger, 2, 1, 1, 1)

        self.setLayout(grid)

        self.btn_show_logger.clicked.connect(self.show_logger)
        self.btn_login.clicked.connect(self.show_login)
        self.btn_download.clicked.connect(self.download)
        self.btn_upload.clicked.connect(self.upload)


    def setup_logger(self):
        handler = LoggerHandler(self.widget_logger)
        self.client._m_logger.addHandler(handler)
        self.connect(self.widget_logger,
                     SIGNAL('new_log(QString)'),
                     self.widget_logger,
                     SLOT('append(QString)'))

        self.dialog_logger.setWindowTitle(u'日志')
        self.dialog_logger.resize(400, 200)
        layout = QVBoxLayout(self.dialog_logger)
        layout.addWidget(self.widget_logger)
        self.dialog_logger.setLayout(layout)


    def show_login(self):
        logged = self.dialog_login.exec_()
        if logged:
            self.unlock()
            self.current_ftp_path = '/'
            self.asynchronized_list(self.current_ftp_path)
        else:
            self.lock()


    def lock(self):
        self.btn_upload.setEnabled(False)
        self.btn_download.setEnabled(False)


    def unlock(self):
        self.btn_upload.setEnabled(True)
        self.btn_download.setEnabled(True)


    def show_logger(self):
        if self.dialog_logger.isVisible():
            self.dialog_logger.hide()
        else:
            self.dialog_logger.show()


    def asynchronized_list(self, path):
        def _():
            success, ret = self.client.list(path)
            if not success:
                return
            self.signal_list_end.emit(ret)

        threading.Thread(target=_).start()


    def asynchronized_download(self, path, target_path):
        def _():
            def callback(total, now):
                self.dialog_login.signal_change_label.emit(
                    u'正在下载 %s/%s' % (
                        self.model.to_human_readable(now),
                        self.model.to_human_readable(total)
                    ))
            self.signal_download_start.emit()
            success = self.client.download(path, target_path, callback=callback)
            self.signal_download_end.emit(success)

        threading.Thread(target=_).start()


    def asynchronized_upload(self, path, target_path):
        def _():
            def callback(total, now):
                self.dialog_login.signal_change_label.emit(
                    u'正在上传 %s/%s' % (
                        self.model.to_human_readable(now),
                        self.model.to_human_readable(total)
                    ))
            self.signal_upload_start.emit()
            success = self.client.upload(path, target_path, callback=callback)
            self.signal_upload_end.emit(success)

        threading.Thread(target=_).start()


    def download_start(self):
        self.dialog_login.change_label(u'正在下载，请稍候')
        self.dialog_login.dialog_wait.show()


    def download_end(self, success):
        self.dialog_login.dialog_wait.hide()
        if success:
            QMessageBox.information(self, u'成功', u'下载成功', QMessageBox.Ok)
        else:
            QMessageBox.critical(self, u'错误', u'下载失败', QMessageBox.Ok)


    def upload_start(self):
        self.dialog_login.change_label(u'正在上传，请稍候')
        self.dialog_login.dialog_wait.show()


    def upload_end(self, success):
        self.dialog_login.dialog_wait.hide()
        if success:
            QMessageBox.information(self, u'成功', u'上传成功', QMessageBox.Ok)
        else:
            QMessageBox.critical(self, u'错误', u'上传失败', QMessageBox.Ok)


    def show_list(self, entries):
        self.model.reset_entries(entries)




if __name__ == '__main__':
    app = QApplication(sys.argv)

    panel = FTPClientPanel('127.0.0.1')
    panel.show()

    app.exec_()




