import subprocess

class InterfaceControl():
    # Control the network interface. Examples are wlan0, wlp9s0, wlp2s0, etc...

    def __init__(self):
        super(InterfaceControl, self).__init__()

    @staticmethod
    def down(interface):
        print("interface:: down: " + interface)
        subprocess.call(["ip", "link", "set", "down", "dev", interface])

    @staticmethod
    def up(interface):
        print("interface:: up: " + interface)
        subprocess.call(["ip", "link", "set", "up", "dev", interface])