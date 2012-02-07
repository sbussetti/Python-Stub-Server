import threading, time
import SocketServer
import re
import os

class FTPServer(SocketServer.BaseRequestHandler):
   
    def __init__(self, port, interactions, files):
        self.port = port
        self.interactions = interactions
        self.files = files
        self.cwd = ''
   
    def __call__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()
        try:
           self.handle()
        finally:
           self.finish()
        return self

    def handle(self):
        # Establish connection
        self.request.send('220 (FtpStubServer 0.1a)\r\n')
        self.communicating = True
        while self.communicating:
            cmd = self.request.recv(1024)
            if cmd:
                self.interactions.append(cmd)
                (attr, ) = re.findall(r'^([^\s]+)\s', cmd) 
                getattr(self, '_' + attr)(cmd)

    def _USER(self, cmd):
        self.request.send('331 Please specify password.\r\n')

    def _PASS(self, cmd):
        self.request.send('230 You are now logged in.\r\n')

    def _TYPE(self, cmd):
        self.request.send('200 Switching to ascii mode.\r\n')

    def _CWD(self, cmd):
        (path, ) = re.findall(re.compile(r'^CWD\s(.*?)[\r\n]+$', re.S), cmd)
        self.cwd = path
        self.request.send('250 OK. Current directory is %s\r\n' % path)

    def _PASV(self, cmd):
        self.data_handler = FTPDataServer(self.interactions, self.files, self.cwd)
        def start_data_server():
            self.port = self.port + 1
            data_server = SocketServer.TCPServer(('localhost',self.port + 1), self.data_handler)
            data_server.handle_request()
            data_server.server_close()
        self.t2 = threading.Thread(target=start_data_server)
        self.t2.start()
        time.sleep(0.1)
        self.request.send('227 Entering Passive Mode. (127,0,0,1,%s,%s)\r\n' %(int((self.port + 1)/256), (self.port + 1) % 256))

    def _STOR(self, cmd):
        self.request.send('150 Okay to send data\r\n')
        time.sleep(0.2)
        self.request.send('226 Got the file\r\n')
        self.t2.join(1)

    def _LIST(self, cmd):
        self.request.send('150 Accepted data connection\r\n')
        time.sleep(0.2)
        self.request.send('226 You got the listings now\r\n')
        self.t2.join(1)

    def _RETR(self, cmd):
        self.request.send('150 Accepted data connection\r\n')
        time.sleep(0.2)
        self.request.send('226 Enjoy your file\r\n')
        self.t2.join(1)
        
    def _QUIT(self, cmd):
        self.request.send('221 Goodbye\r\n')
        self.communicating = False
        time.sleep(0.001)

class FTPDataServer(SocketServer.StreamRequestHandler):
    
    def __init__(self, interactions, files, cwd):
        self.interactions = interactions
        self.files = files
        self.command = 'LIST'
        self.cwd = cwd
            
    def __call__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()
        try:
          self.handle()
          return self
        finally:
          self.finish()
        
    def handle(self):
        while not hasattr(self, '_' + self.interactions[-1:][0][:4]):
            time.sleep(0.01)
        getattr(self, '_' + self.interactions[-1:][0][:4])()
        
    def filename(self):
        return self.interactions[-1:][0][5:].strip()

    def _STOR(self):
        abspath=os.path.join(self.cwd, self.filename())
        self.files[abspath] = self.rfile.read().strip()

    def _LIST(self):
        self.wfile.write('\n'.join([name for name in self.files.keys()]))
        
    def _RETR(self):
        self.wfile.write(self.files[self.filename()])

class FTPStubServer(object):

    def __init__(self, port):
        self.port = port
        self._interactions = []
        self._files = {}

    def files(self, name):
        if name in self._files:
            return self._files[name]
        return None
        
    def add_file(self, name, content):
        self._files[name] = content
        
    def run(self):
        self.server = SocketServer.TCPServer(('localhost',self.port), FTPServer(self.port, self._interactions, self._files))
        self.server.timeout = 2
        self.server_thread = threading.Thread(target=self._run)
        self.server_thread.setDaemon(True)
        self.server_thread.start()
   
    def _run(self):
        self.server.handle_request()
        self.server.server_close()
   
    def stop(self):
        self.server_thread.join()
        while self._interactions:
            self._interactions.pop()
        while self._files:
            self._files.popitem()
