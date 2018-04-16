import subprocess
from gi.repository import Gio


class NetCTL(object):
    # These functions are to separate the Netctl code
    # from the GUI code.
    def __init__(self):
        super(NetCTL, self).__init__()

    @staticmethod
    def start(network):
        print("netctl:: start " + network)
        process = Gio.Subprocess.new(["netctl", "start", network], 0)
        process.wait_async()
        print("netctl:: started " + network)

    @staticmethod
    def stop(network):
        print("netctl:: stop " + network)
        process = Gio.Subprocess.new(["netctl", "stop", network], 0)
        process.wait()

    @staticmethod
    def stop_all():
        print("netctl:: stop-all")
        process = Gio.Subprocess.new(["netctl", "stop-all"], 0)
        process.wait()

    @staticmethod
    def restart(network):
        print("netctl:: restart " + network)
        process = Gio.Subprocess.new(["netctl", "restart", network], 0)
        process.wait()

    @staticmethod
    def list():
        print("netctl:: list")
        process = Gio.Subprocess.new(["netctl", "list"], 0)
        process.wait()

    @staticmethod
    def enable(network):
        print("netctl:: enable " + network)
        process = Gio.Subprocess.new(["netctl", "enable", network], 0)
        process.wait()

    @staticmethod
    def disable(network):
        print("netctl:: disable " + network)
        process = Gio.Subprocess.new(["netctl", "disable", network], 0)
        process.wait()