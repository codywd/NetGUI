import subprocess


class NetCTL(object):
    # These functions are to separate the Netctl code
    # from the GUI code.
    def __init__(self):
        super(NetCTL, self).__init__()

    @staticmethod
    def start(network):
        print("netctl:: start " + network)
        subprocess.call(["netctl", "start", network])
        print("netctl:: started " + network)

    @staticmethod
    def stop(network):
        print("netctl:: stop " + network)
        subprocess.call(["netctl", "stop", network])

    @staticmethod
    def stop_all():
        print("netctl:: stop-all")
        subprocess.call(["netctl", "stop-all"])

    @staticmethod
    def restart(network):
        print("netctl:: restart " + network)
        subprocess.call(["netctl", "restart", network])

    @staticmethod
    def list():
        print("netctl:: list")
        subprocess.call(["netctl", "list"])

    @staticmethod
    def enable(network):
        print("netctl:: enable " + network)
        subprocess.call(["netctl", "enable", network])

    @staticmethod
    def disable(network):
        print("netctl:: disable " + network)
        subprocess.call(["netctl", "disable", network])