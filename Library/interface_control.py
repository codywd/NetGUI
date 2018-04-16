import subprocess
from gi.repository import Gio

class InterfaceControl():
    # Control the network interface. Examples are wlan0, wlp9s0, wlp2s0, etc...

    def __init__(self):
        super(InterfaceControl, self).__init__()

    @staticmethod
    def down(interface):
        print("interface:: down: " + interface)
        process = Gio.Subprocess.new(["ip", "link", "set", "down", "dev", interface], 0)
        process.wait()

    @staticmethod
    def up(interface):
        print("interface:: up: " + interface)
        process = Gio.Subprocess.new(["ip", "link", "set", "up", "dev", interface], 0)
        process.wait()
