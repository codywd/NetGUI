import os
from pathlib import Path
import subprocess

class ScanRoutines():
    def __init__(self, interface, scan_file, status_dir, scan_completion_queue):
        super(ScanRoutines, self).__init__()
        self.scan_file = scan_file
        self.status_dir = status_dir
        self.interface = interface
        self.scan_completion_queue = scan_completion_queue

    def scan(self):
        print("Scanning! Please wait...")
        if Path(self.scan_file).exists():
            os.remove(self.scan_file)
        if Path(self.status_dir, "final_results.log").exists():
            os.remove(Path(self.status_dir, "final_results.log"))
        # Huge thanks to joukewitteveen on GitHub for the following command!! Slightly modified from his comment
        subprocess.call('bash -c "source /usr/lib/netctl/globals; source /usr/lib/netctl/wpa; wpa_supplicant_scan ' +
                        self.interface + ' 3,4,5" >> ' + str(self.scan_file), shell=True)
        print("Done scanning!")
        self.scan_completion_queue.put("Finished")