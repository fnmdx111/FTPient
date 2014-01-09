# encoding: utf-8
import socket
import threading

from PySide.QtCore import *
from PySide.QtGui import *

from libs.ftp import FTPClient


class LoginDialog(QDialog, object):
    signal_start_login = Signal()
    signal_end_login = Signal(bool)
    signal_change_label = Signal(str)
    signal_msg_box = Signal(str, str)
    signal_reset_client = Signal(str)

    def __init__(self, parent):
        super(LoginDialog, self).__init__(parent)

        self.setWindowTitle(u'登录')

        label_server_ip = QLabel(u'服务器地址(&A)')
        self.edit_server_ip = QLineEdit('127.0.0.1')
        label_server_ip.setBuddy(self.edit_server_ip)

        label_username = QLabel(u'用户名(&U)')
        self.edit_username = QLineEdit('anony')
        label_username.setBuddy(self.edit_username)

        label_password = QLabel(u'密码(&P)')
        self.edit_password = QLineEdit('')
        self.edit_password.setEchoMode(QLineEdit.Password)
        label_password.setBuddy(self.edit_password)

        self.button_login = QPushButton(u'登录(&L)')
        self.button_cancel = QPushButton(u'取消(&C)')

        grid = QGridLayout()
        grid.addWidget(label_server_ip, 0, 0)
        grid.addWidget(self.edit_server_ip, 0, 1)
        grid.addWidget(label_username, 1, 0)
        grid.addWidget(self.edit_username, 1, 1)
        grid.addWidget(label_password, 2, 0)
        grid.addWidget(self.edit_password, 2, 1)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_login)
        button_layout.addWidget(self.button_cancel)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.button_login.clicked.connect(self.login)
        self.button_cancel.clicked.connect(self.reject)

        self.dialog_wait = QDialog(self)
        self.dialog_wait.setWindowFlags(Qt.Popup)
        self.dialog_wait.setWindowTitle(u'请稍候')
        self.label_wait = QLabel(u'<b>请稍候，正在登录</b>')
        layout_wait = QVBoxLayout()
        layout_wait.addWidget(self.label_wait)
        self.dialog_wait.setLayout(layout_wait)
        self.dialog_wait.setModal(True)

        self.signal_start_login.connect(lambda: self.dialog_wait.show())
        self.signal_end_login.connect(self.logged_in)
        self.signal_change_label.connect(self.change_label)
        self.signal_msg_box.connect(self.show_msg_box)
        self.signal_reset_client.connect(self.reset_client)

        self.logged = False


    def reset_client(self, server_ip):
        self.parent().client.quit()
        self.parent().client = FTPClient(server_ip)


    def show_msg_box(self, title, msg):
        QMessageBox.critical(self, title, msg, QMessageBox.Ok)


    def change_label(self, msg):
        self.label_wait.setText(u'<b>%s</b>' % msg)


    def logged_in(self, ret):
        self.dialog_wait.hide()

        self.logged = ret
        if not self.logged:
            QMessageBox.critical(self,
                                 u'错误',
                                 u'未能登录',
                                 QMessageBox.Ok)
        else:
            self.accept()


    def login(self):
        username = self.edit_username.text()
        password = self.edit_password.text()
        server_ip = self.edit_server_ip.text()
        self.signal_reset_client.emit(server_ip)

        def _():
            self.signal_start_login.emit()

            self.signal_change_label.emit(u'正在连接%s' % server_ip)
            try:
                self.parent().client.connect()
            except socket.error as e:
                self.signal_msg_box.emit(u'网络错误',
                                         u'不能连接到%s，%s' % (server_ip,
                                                               e.errno))
                self.signal_end_login.emit(False)
                return


            ret = False
            self.signal_change_label.emit(u'正在登录')
            try:
                ret = self.parent().client.login(username, password)
            except Exception:
                self.signal_msg_box.emit(u'网络错误',
                                         u'登录失败')
                self.signal_end_login.emit(False)

            self.signal_end_login.emit(ret)

        thread = threading.Thread(target=_)
        thread.start()



class FileModel(QAbstractTableModel):
    def __init__(self, entries, parent):
        super(FileModel, self).__init__(parent)

        self.entries = entries

        self.headers = [u'名称', u'大小', u'日期', u'所有者', u'属性']


    def columnCount(self, index=QModelIndex(), *args, **kwargs):
        if not index.isValid():
            return len(self.headers)
        return 0


    def rowCount(self, index=QModelIndex(), *args, **kwargs):
        if not index.isValid():
            return len(self.entries)
        return 0


    def data(self, idx, role=Qt.DisplayRole):
        if not self.is_valid_index(idx):
            return None

        row, col = idx.row(), idx.column()
        entry = self.entries[row]

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        elif role == Qt.DisplayRole:
            if col == 0:
                return entry.name
            elif col == 3:
                return entry.owner
            elif col == 1:
                if entry.is_dir():
                    return ''
                else:
                    return self.to_human_readable(entry.size)
            elif col == 4:
                return entry.attr
            elif col == 2:
                return '%s-%s-%s' % (entry.year, entry.month, entry.day)
        elif role == Qt.DecorationRole:
            if col == 0:
                if entry.is_dir():
                    return QFileIconProvider().icon(QFileIconProvider.Folder)
                else:
                    return QFileIconProvider().icon(QFileIconProvider.File)
        elif role == Qt.UserRole:
            return entry

        return None


    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]


    def is_valid_index(self, idx):
        row, col = idx.row(), idx.column()

        if not idx.isValid() \
            or not (0 <= row < self.rowCount()) \
            or not (0 <= col < self.columnCount()):
            return False
        return True


    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)


    def parent(self, idx):
        return self.createIndex(-1, -1)


    def reset_entries(self, entries):
        self.entries = entries
        self.reset()


    A_MILLION_BYTE = 1024 * 1000


    def to_human_readable(self, size):
        size_f = float(size)
        if size_f > 1024 * 1000 * 1000:
            human_readable_size = '%.2f GB' % (size_f /
                                                  (self.A_MILLION_BYTE * 1000))
        elif size_f > 1024 * 1000:
            human_readable_size = '%.2f MB' % (size_f / self.A_MILLION_BYTE)
        elif size_f > 1024:
            human_readable_size = '%.2f kB' % (size_f / 1024)
        else:
            human_readable_size = '%.2f B' % size_f
        return human_readable_size
