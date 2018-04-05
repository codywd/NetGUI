import multiprocessing
import os
from pathlib import Path
import subprocess

class ScanRoutines():
    def __init__(self, interface, scan_file, status_dir):
        super(ScanRoutines, self).__init__()
        self.p = None
        self.scan_file = scan_file
        self.status_dir = status_dir
        self.interface = interface

    def scan(self):
        if Path(self.scan_file).exists():
            os.remove(self.scan_file)
        if Path(self.status_dir, "final_results.log").exists():
            os.remove(Path(self.status_dir, "final_results.log"))
        p = multiprocessing.Process(target=ScanRoutines.run_scan(self))
        p.start()
        p.join()

    @staticmethod
    def run_scan(self):
        print("Please wait! Now Scanning.")
        # Huge thanks to joukewitteveen on GitHub for the following command!! Slightly modified from his comment
        subprocess.call('bash -c "source /usr/lib/netctl/globals; source /usr/lib/netctl/wpa; wpa_supplicant_scan ' +
                        self.interface + ' 3,4,5" >> ' + str(self.scan_file), shell=True)
        print("Done Scanning!")