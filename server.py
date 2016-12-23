from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import options
from website import app
from config import CERT_PATH, KEY_PATH

options.parse_command_line(args=None, final=True)

http_server = HTTPServer(WSGIContainer(app))
http_server.listen(80)

https_server = HTTPServer(WSGIContainer(app), ssl_options={
    "certfile": CERT_PATH,
    "keyfile": KEY_PATH
})
https_server.listen(443)

IOLoop.instance().start()
