import fcntl
import subprocess
import sys

class run_as_root():
    def __init__(self):
        self.pid_file = None

    @staticmethod
    def set_pid_file(self, pid_number, pid_file):
        # Let's also not allow any more than one instance of netgui.
        self.pid_file = open(pid_file, 'w')
        try:
            fcntl.lockf(self.pid_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("We only allow one instance of netgui to be running at a time for precautionary reasons.")
            sys.exit(1)

        self.pid_file.write(str(pid_number)+"\n")
        self.pid_file.flush()

    def close_pid_file(self):
        fcntl.lockf(self.pid_file, fcntl.LOCK_UN)
        self.pid_file.close()