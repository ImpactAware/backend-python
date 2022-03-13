from threading import Lock, Thread
from datetime import datetime
from json import dumps
import re
import logging

import serial
import flask
import timeago

# Represents a remote sensor
class RemoteSensor():
    def __init__(self, id):
        self.id = id
        self.hits = 0
        self.last_hit = 0
        self.connected = False

    def hit(self):
        self.hits += 1
        self.last_hit = datetime.now()
        self.connected = True

    def conn(self):
        self.connected = True

    def drop(self):
        self.connected = False

    def to_dict(self):
        if self.last_hit == 0:
            last_hit_text = "Never"
        else:
            last_hit_text = timeago.format(self.last_hit, datetime.now())

        return {
            "device_id": self.id,
            "hits": self.hits,
            "last_hit": last_hit_text,
            "connected": self.connected
        }

# Represents a command from the board
class SerialMessage():

    serial_msg = re.compile("^([A-Z]{4})\s(\d*)\s{0,1}(\d{10})$")

    def __init__(self, msg) -> None:
        self.cmd, self.__payload, self.id = self.serial_msg.findall(msg)[0]

        self.id = int(self.id)

        if self.cmd == "DROP":
            self.drop_id = int(self.__payload)
            self.hits = 0

        elif self.cmd == "VIBR":
            self.drop_id = 0
            self.hits = int(self.__payload)

        else:
            self.drop_id = 0
            self.hits = 0


comm_board = serial.Serial("COM5", baudrate=115200)

board_lock = Lock()

boards = {
    3873486081: RemoteSensor(3873486081), # Blue ESP32
    2218631381: RemoteSensor(2218631381), # Red ESP32 Thing Plus
    2383250881: RemoteSensor(2383250881), # Black ESP32
    2734061871: RemoteSensor(2734061871), # ESP8266
}

def serial_update():
    while True:
        try:
            msg = comm_board.read_until(b'\n').decode('utf-8')
            msg = SerialMessage(msg)
        except:
            # print(return_json()+'\n')
            continue
        
        if msg.cmd == "CONN":
            with board_lock:
                boards[msg.id].conn()

        elif msg.cmd == "DROP":
            with board_lock:
                boards[msg.drop_id].drop()

        elif msg.cmd == "VIBR":
            with board_lock:
                boards[msg.id].hit()

        # print(return_json()+'\n')
        print(f"Command: {msg.cmd}")
        print(f"Hits: {msg.hits}")
        print(f"Drop ID: {msg.drop_id}")
        print(f"ID: {msg.id}")
        print()

backend = Thread(target=serial_update, daemon=True, name='Serial Thread')
backend.start()

app = flask.Flask(__name__)

log = logging.getLogger('werkzeug')
log.disabled = True

@app.route("/")
def default():
    return app.send_static_file("index.html")

@app.route("/nodes", methods=['GET'])
def return_json():
    with board_lock:
        return dumps([i.to_dict() for i in boards.values()], sort_keys=True, indent=4)

@app.route("/<path:path>")
def static_serve(path):
    return app.send_static_file(path)

app.run()