import subprocess

class NetCTL(object):
    # These functions are to separate the Netctl code
    # from the GUI code.
    def __init__(self):
        super(NetCTL, self).__init__()

    @staticmethod
    def start(self, network):
        print("netctl:: start " + network)
        subprocess.call(["netctl", "start", network])
        print("netctl:: started " + network)

    @staticmethod
    def stop(self, network):
        print("netctl:: stop " + network)
        subprocess.call(["netctl", "stop", network])

    @staticmethod
    def stop_all(self):
        print("netctl:: stop-all")
        subprocess.call(["netctl", "stop-all"])

    @staticmethod
    def restart(self, network):
        print("netctl:: restart " + network)
        subprocess.call(["netctl", "restart", network])

    @staticmethod
    def list(self):
        print("netctl:: list")
        subprocess.call(["netctl", "list"])

    @staticmethod
    def enable(self, network):
        print("netctl:: enable " + network)
        subprocess.call(["netctl", "enable", network])

    @staticmethod
    def disable(self, network):
        print("netctl:: disable " + network)
        subprocess.call(["netctl", "disable", network])