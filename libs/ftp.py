# encoding: utf-8
import os

import socket
import logging
from libs.misc import DirEntry


class FTPClient(object):

    def _ret(self):
        lines, codes, msgs = [], [], []
        while True:
            data = self._m_cmd_sock.recv(4096)

            lines = data.strip().split('\r\n')
            line = '000 '
            for line in lines:
                codes.append(int(line[:3]))
                msgs.append(line[4:])
            if line[3] == ' ':
                return codes, msgs


    def _info(self, (codes, msgs)):
        for code, data in zip(codes, msgs):
            self._m_logger.info('%s: %s', code, data)


    def __init__(self, server_ip, server_port=21,
                       client_ip='127.0.0.1', client_port=54321):
        self._c_server_ip = server_ip
        self._c_server_port = server_port
        self._c_client_ip = client_ip
        self._c_client_port = client_port

        self._m_cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connected = False

        logging.basicConfig(level=logging.DEBUG)
        self._m_logger = logging.getLogger(__name__)

        self.stop = False


    def connect(self):
        self._m_cmd_sock.connect((self._c_server_ip, self._c_server_port))
        self._c_client_ip, self._c_client_port = self._m_cmd_sock.getsockname()
        self._c_client_port += 1

        self._info(self._ret())
        self.connected = True


    def _cmd_send(self, cmd):
        self._m_cmd_sock.send(cmd.encode('utf-8'))
        self._m_logger.info('cmd: %s', cmd.strip())


    def login(self, username, password):
        self._cmd_send('USER %s\r\n' % username)
        ret = codes, msgs = self._ret()
        self._info(ret)

        if 331 in codes:
            self._cmd_send('PASS %s\r\n' % password)
            ret = codes, msgs = self._ret()
            self._info(ret)
            if 230 in codes:
                self._cmd_send('PWD\r\n')
                ret = codes, _ = self._ret()
                self._info(ret)
                if 257 in codes:
                    return True

        return False


    def passive_mode(self):
        self._cmd_send('TYPE I\r\n')
        ret = codes, _ = self._ret()
        self._info(ret)
        if 200 not in codes:
            return False

        self._cmd_send('PASV\r\n')
        ret = codes, msgs = self._ret()
        self._info(ret)

        if 227 in codes:
            t = map(int, eval(msgs[0].split()[3]))
            server_ip = '%d.%d.%d.%d' % (t[0], t[1], t[2], t[3])
            port = t[4] * 256 + t[5]

            self._m_data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._m_data_sock.connect((server_ip, port))
            self._m_logger.debug('   : connected to %s:%s', server_ip, port)

            return True

        return False


    def cwd(self, directory):
        self._cmd_send('CWD %s\r\n' % directory)
        ret = codes, msgs = self._ret()

        self._info(ret)
        if 250 in codes:
            return True
        return False


    def size(self, filename):
        self._cmd_send('SIZE %s\r\n' % filename)
        ret = codes, msgs = self._ret()

        self._info(ret)
        if 213 in codes:
            return True, int(msgs[0])
        return False, None


    def retrieve(self, filename, target_path, size, callback, passive=False):
        self._cmd_send('RETR %s\r\n' % filename)
        ret = codes, msgs = self._ret()

        if not passive:
            conn, _ = self._m_data_sock.accept()
        else:
            conn = self._m_data_sock

        if 150 in codes:
            self._info(ret)

            with open(target_path, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
                    callback(size, f.tell())
                    if self.stop:
                        break
                else:
                    self.stop = False

            conn.close()
            if not passive:
                self._m_data_sock.close()

            ret = codes, _ = self._ret()
            self._info(ret)
            if 226 in codes:
                return True

        return False


    def download(self, path, target_path, passive=True,
                 callback=lambda _1, _2: 1):
        directory, filename = os.path.split(path)

        if not filename:
            self._m_logger.error('%s is not a valid path', path)
            return False

        if not directory:
            directory = '.'
        if not self.cwd(directory):
            return False

        _, size = self.size(filename)
        if not size:
            return False

        if passive:
            self.passive_mode()
        else:
            self.port_mode()

        if not self.retrieve(filename, target_path, passive=passive,
                             callback=callback, size=size):
            return False

        return True


    def port_mode(self):
        self._m_data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._m_data_sock.bind((self._c_client_ip, self._c_client_port))
        self._m_data_sock.listen(64)

        h1, h2, h3, h4 = self._c_client_ip.split('.')
        p1, p2 = self._c_client_port / 256, self._c_client_port % 256
        self._cmd_send('PORT %s,%s,%s,%s,%s,%s\r\n' % (h1, h2, h3, h4, p1, p2))

        ret = codes, _ = self._ret()
        self._info(ret)
        if 200 not in codes:
            return False
        return True


    def upload(self, path, target_path, passive=True,
               callback=lambda _1, _2: 1):
        directory, filename = os.path.split(path)

        if not filename:
            self._m_logger.error('%s is not a valid path', path)
            return False

        if not directory:
            directory = '.'
        if not self.cwd(directory):
            return False

        if passive:
            self.passive_mode()
        else:
            self.port_mode()

        if not self.send_file(target_path, filename, passive=passive,
                              callback=callback):
            return False

        return True


    def send_file(self, target_path, filename, callback, passive=True):
        self._cmd_send('STOR %s\r\n' % filename)
        ret = codes, _ = self._ret()
        if 150 not in codes:
            return False
        self._info(ret)

        if not passive:
            conn, _ = self._m_data_sock.accept()
        else:
            conn = self._m_data_sock

        with open(target_path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            length = f.tell()
            f.seek(0, os.SEEK_SET)

            bytes_sent = 0
            while bytes_sent < length:
                sent = conn.send(f.read(51200))
                bytes_sent += sent
                callback(length, bytes_sent)
                if self.stop:
                    break
            else:
                self.stop = False

            conn.close()
            if not passive:
                self._m_data_sock.close()

            ret = codes, _ = self._ret()
            if 226 in codes:
                self._info(ret)
                return True
            return False


    def __enter__(self):
        self.connect()

        return self


    def quit(self):
        self._cmd_send('QUIT\r\n')
        ret = codes, _ = self._ret()
        if 221 not in codes:
            return False
        self._info(ret)

        self._m_cmd_sock.close()

        self.connected = False


    @staticmethod
    def _process_list(buf):
        lines = buf.strip('\r\n').split('\r\n')
        ret = []
        for line in lines:
            if not line:
                continue

            attrs = line.split(';')
            _, type_ = attrs[0].split('=')
            _, time = attrs[1].split('=')
            year = time[0:4]
            month = time[4:6]
            day = time[6:8]
            hour = time[8:10]
            minute = time[10:12]
            second = time[12:]
            if type_ == 'file':
                _, size = attrs[2].split('=')
                name = attrs[3][1:]
            else:
                size = ''
                name = attrs[2][1:]

            ret.append(DirEntry(year=year, month=month, day=day,
                                hour=hour, minute=minute, second=second,
                                name=name, is_file=(type_ == 'file'),
                                size=size))
        return ret


    def list(self, path='', passive=True):
        success = self.cwd(path)
        if not success:
            return False, []

        if passive:
            self.passive_mode()
            conn = self._m_data_sock
        else:
            self.port_mode()
            conn, _ = self._m_data_sock.accept()

        self._cmd_send('MLSD\r\n')
        ret = codes, _ = self._ret()
        self._info(ret)
        if 150 not in codes:
            return False, []

        ret = ''
        while True:
            buf = conn.recv(4096)
            if not buf:
                break
            ret += buf

        entries = []
        entries.append(DirEntry(name='..', is_file=False))
        entries += self._process_list(ret)

        ret = codes, _ = self._ret()
        self._info(ret)
        if 226 not in codes:
            print 'asdfasdfasdf'
            return False, []

        conn.close()
        if not passive:
            self._m_data_sock.close()
        self._m_logger.info(entries)

        return True, entries


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()



if __name__ == '__main__':
    client = FTPClient('127.0.0.1')
    client.connect()
    client.login('anony', '')
    ret = client.list()
    client.download('./xxx/xxx/11.gif', '111.gif')
    client.download('/xxx/libftp.txt', '1libftp.py')
    client.quit()

