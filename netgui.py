#! /usr/bin/python3

# Import Standard Libraries
import csv
import fcntl
import fileinput
import multiprocessing
import os
import shutil
import subprocess
import sys
import webbrowser

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib, Gio
from gi.repository import Notify

# Setting base app information, such as version, and configuration directories/files.
prog_ver = "0.8"
profile_dir = "/etc/netctl/"
status_dir = "/var/lib/netgui/"
program_loc = "/usr/share/netgui/"
interface_conf_file = status_dir + "interface.cfg"
license_dir = '/usr/share/licenses/netgui/'
scan_file = status_dir + "scan_results.log"
pid_file = status_dir + "program.pid"
img_loc = "/usr/share/netgui/imgs"
pref_file = status_dir + "preferences.cfg"
pid_number = os.getpid()
arg_no_wifi = 0

# Checking for arugments in command line. We will never have a command line version of netgui (it's called netctl!)
for arg in sys.argv:
    if arg == '--help' or arg == '-h':
        print("The NetGUI help menu:\n")
        print("--version, -v: Find our your NetGUI Version.\n")
        print("--develop, -d: Run in development mode. If not a developer, do not use.")
        print("--nowifi, -n: Run in no-wifi-mode. Does not scan for networks. Uses profiles to connect.")
        sys.exit(0)
    if arg == '--version' or arg == '-v':
        print("Your netgui version is " + prog_ver + ".")
        sys.exit(0)
    if arg == '--develop' or arg =='-d':
        print("Running in development mode. All files are set to be in the development folder.")
        program_loc = "./"
    if arg == '--nowifi' or arg =='-n':
        print("Running in No Wifi mode!")
        argNoWifi = 1

# If our directory for netgui does not exist, create it.
if os.path.exists(status_dir):
    pass
else:
    subprocess.call("mkdir " + status_dir, shell=True)

# Let's make sure we're root, while at it.
euid = os.geteuid()
if euid != 0:
    print("netgui needs to be run as root, since many commands we use requires it.\nPlease sudo or su -c and try again.")
    sys.exit(77)

# Let's also not allow any more than one instance of netgui.
fp = open(pid_file, 'w')
try:
    fcntl.lockf(fp, fcntl.LOCK_EX|fcntl.LOCK_NB)
except IOError:
    print("We only allow one instance of netgui to be running at a time for precautionary reasons.")
    sys.exit(1)

fp.write(str(pid_number)+"\n")
fp.flush()

class NetGUI(Gtk.Window):
    def __init__(self):
        # Init Vars
        self.scanning = False
        self.APindex = 0
        self.p = None
        self.builder = Gtk.Builder()

        self.InitUI()

    def InitUI(self):
        is_connected()
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.
        self.builder.add_from_file(program_loc + "UI.glade")

        # Grab the "window1" attribute from UI.glade, and set it to show everything.
        window = self.builder.get_object("mainWindow")
        window.connect("delete-event", Gtk.main_quit)

        # Get the OnScan button in case we are going to run in NoWifiMode
        ScanButton = self.builder.get_object("scanAPsTool")

        # Setup the main area of netgui: The network list.
        self.APList = self.builder.get_object("treeview1")
        self.APStore = Gtk.ListStore(str, str, str, str)
        self.APList.set_model(self.APStore)

        # Set Up Columns
        # renderer1 = The Cell renderer. Basically allows for text to show.
        # column1 = The actual setup of the column. Arguments = title, CellRenderer, textIndex)
        # Actually append the column to the treeview.
        SSIDCellRenderer = Gtk.CellRendererText()
        SSIDColumn = Gtk.TreeViewColumn("SSID", SSIDCellRenderer, text=0)
        SSIDColumn.set_resizable(True)
        SSIDColumn.set_expand(True)
        self.APList.append_column(SSIDColumn)

        connectQualityCellRenderer = Gtk.CellRendererText()
        connectQualityColumn = Gtk.TreeViewColumn("Connection Quality", connectQualityCellRenderer, text=1)
        connectQualityColumn.set_resizable(True)
        connectQualityColumn.set_expand(True)
        self.APList.append_column(connectQualityColumn)

        securityTypeCellRenderer = Gtk.CellRendererText()
        securityTypeColumn = Gtk.TreeViewColumn("Security Type", securityTypeCellRenderer, text=2)
        securityTypeColumn.set_resizable(True)
        securityTypeColumn.set_expand(True)
        self.APList.append_column(securityTypeColumn)

        connectedCellRenderer = Gtk.CellRendererText()
        connectedColumn = Gtk.TreeViewColumn("Connected?", connectedCellRenderer, text=3)
        connectedColumn.set_resizable(True)
        connectedColumn.set_expand(True)
        self.APList.append_column(connectedColumn)

        # Set TreeView as Reorderable
        self.APList.set_reorderable(True)

        '''
        # Set all the handlers I defined in glade to local functions.
        handlers = {
        "onSwitch": self.onSwitch,
        "onExit": self.onExit,
        "onAboutClicked": self.aboutClicked,
        "onScan": self.startScan,
        "onConnect": self.profileExists,
        "onDConnect": self.dConnectClicked,
        "onPrefClicked": self.prefClicked,
        "onHelpClicked": self.get_network_pw,
        "onIssueReport": self.reportIssue
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)
        '''
        # Populate profiles menu
        menu = self.builder.get_object("menubar1")
        profileMenu = self.builder.get_object("profilesMenu")
        profileMenu.set_submenu(Gtk.Menu())
        profiles = os.listdir("/etc/netctl/")
        # Iterate through profiles directory, and add to "Profiles" Menu #
        for i in profiles:
            if os.path.isfile("/etc/netctl/" + i):
                profile = profileMenu.get_submenu().append(Gtk.MenuItem(label=i))
        #This should automatically detect their wireless device name. I'm not 100% sure
        #if it works on every computer, but we can only know from multiple tests. If
        #it doesn't work, I will re-implement the old way.
        Notify.init("NetGUI")

        self.interfaceName = get_interface()
        if self.interfaceName == "":
            n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            n.show()
            #self.NoWifiScan(None)
            self.NoWifiMode = 1
            ScanButton.props.sensitive = False
            print(str(self.NoWifiMode))
        elif arg_no_wifi is 1:
            self.NoWifiScan(None)
            self.NoWifiMode = 1
            ScanButton.props.sensitive = False
        else:
            #self.startScan(None)
            self.NoWifiMode = 0

        # Start initial scan
        window.show_all()

    def startScan(self, e):
        ScanRoutines.scan(None)


class NetCTL(object):
    # These functions are to separate the Netctl code
    # from the GUI code.
    def __init__(self):
        super(NetCTL, self).__init__()

    def start(self, network):
        print("netctl:: start " + network)
        subprocess.call(["netctl", "start", network])
        print("netctl:: started " + network)

    def stop(self, network):
        print("netctl:: stop " + network)
        subprocess.call(["netctl", "stop", network])

    def stopall(self):
        print("netctl:: stop-all")
        subprocess.call(["netctl", "stop-all"])

    def restart(self, network):
        print("netctl:: restart " + network)
        subprocess.call(["netctl", "restart", network])

    def list(self):
        print("netctl:: list")
        subprocess.call(["netctl", "list"])

    def enable(self, network):
        print("netctl:: enable " + network)
        subprocess.call(["netctl", "enable", network])

    def disable(self, network):
        print("netctl:: disable " + network)
        subprocess.call(["netctl", "disable", network])


class InterfaceControl(object):
    # Control the network interface. Examples are wlan0, wlp9s0, wlp2s0, etc...

    def __init__(self):
        super(InterfaceControl, self).__init__()

    def down(self, interface):
        print("interface:: down: " + interface)
        subprocess.call(["ip", "link", "set", "down", "dev", interface])

    def up(self, interface):
        print("interface:: up: " + interface)
        subprocess.call(["ip", "link", "set", "up", "dev", interface])


class ScanRoutines(object):
    def __init__(self):
        super(ScanRoutines, self).__init__()

    def scan(self):
        if os.path.exists(scan_file):
            os.remove(scan_fileile)
        if os.path.exists(status_dir + "final_results.log"):
            os.remove(status_dir + "final_results.log")
        self.p = multiprocessing.Process(target=self.run_scan)
        self.p.start()
        self.p.join()
        self.checkScan()

    def run_scan(self):
        print("Please wait! Now Scanning.")
        # Huge thanks to joukewitteveen on GitHub for the following command!! Slightly modified from his comment

        subprocess.call('bash -c "source /usr/lib/network/globals; source /usr/lib/network/wpa; wpa_supplicant_scan ' + self.interfaceName + ' 3,4,5" >> ' + scan_file, shell=True)
        print("Done Scanning!")
    ## TODO: Rewrite for new GUI/Scan split functions
    def check_scan(self):
        sf = open(scanFile, 'r')
        realdir = sf.readline()
        realdir = realdir.strip()
        sf.close()
        print(realdir)
        shutil.move(realdir, statusDir + "final_results.log")

        with open(statusDir + "final_results.log") as tsv:
            self.APStore.clear()

            r = csv.reader(tsv, dialect='excel-tab')
            aps = {}
            i = 0
            for row in r:
                network = row[2]
                print(network)
                if network == "":
                    pass
                elif "\x00" in network:
                    pass
                else:
                    aps["row" + str(i)] = self.APStore.append([network, "", "", ""])

                quality = row[0]
                if int(quality) <= -100:
                    percent = "0%"
                elif int(quality) >= -50:
                    percent = "100%"
                else:
                    fquality = (2 * (int(quality) + 100))
                    percent = str(fquality) + "%"
                if network == "":
                    pass
                else:
                    self.APStore.set(aps["row" + str(i)], 1, percent)

                security = row[1]
                if "WPA" in security:
                    encryption = "WPA"
                elif "OPENSSID" in security:
                    encryption = "Open"
                elif "WPS" in security:
                    encryption = "WPS"
                elif "WEP" in security:
                    encryption = "WEP"
                else:
                    encryption = "Open"
                if network == "":
                    pass
                else:
                    self.APStore.set(aps["row" + str(i)], 2, encryption)

                if IsConnected() is False:
                    if network == "":
                        pass
                    else:
                        if network == "":
                            pass
                        else:
                            self.APStore.set(aps["row" + str(i)], 3, "No")
                else:
                    connectedNetwork = CheckOutput(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if network in connectedNetwork:
                        if network == "":
                            pass
                        else:
                            self.APStore.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        if network == "":
                            pass
                        else:
                            self.APStore.set(aps["row" + str(i)], 3, "No")
                i=i+1


def create_config(name, interface, security, key, ip='dhcp'):
    print("Creating Profile! Don't interrupt!\n")
    filename = "netgui_" + name
    f = open(profile_dir + filename, 'w')
    f.write("Description='This profile was generated by netgui for " + str(name)+".'\n" +
            "Interface=" + str(interface) + "\n" +
            "Connection=wireless\n" +
            "Security=" + str(security) + "\n" +
            "ESSID='" + str(name) + "'\n")
    if key:
        f.write(r"Key='" + key + "'\n")
    else:
        f.write(r'Key=None')
    f.write("\nIP=dhcp\n")
    f.close()
    print("Alright, I have finished making the profile!")


def is_connected():
    # If we are connected to a network, it lists it. Otherwise, it returns nothing (or an empty byte).
    check = subprocess.check_output("netctl list | sed -n 's/^\* //p'", shell=True)
    if check == b'':
        return False
    else:
        return True

''' Remove?
def CheckOutput(self, command):
    # Run a command, return what it's output was, and convert it from bytes to unicode
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    output = p.communicate()[0]
    output = output.decode("utf-8")
    return output


def CheckGrep(self, grepCmd):
    # Run a grep command, decode it from bytes to unicode, strip it of spaces,
    # and return it's output.
    p = subprocess.Popen(grepCmd, stdout=subprocess.PIPE, shell=True)
    output = ((p.communicate()[0]).decode("utf-8")).strip()
    return output
'''


def get_interface():
    if os.path.isfile(interface_conf_file) != True:

        devices = os.listdir("/sys/class/net")
        for device in devices:
            if "wlp" or "wlan" in device:
                interfaceName = device
            else:
                pass
        if interfaceName == "":
            intNameCheck = str(subprocess.check_output("cat /proc/net/wireless", shell=True))
            interfaceName = intNameCheck[166:172]
        if interfaceName == "":
            #interfaceName = Need the code here
            pass
        f = open(interface_conf_file, 'w')
        f.write(interfaceName)
        f.close()
        return str(interfaceName).strip()
    else:
        f = open(interface_conf_file, 'r')
        interfaceName = f.readline()
        f.close()
        return str(interfaceName).strip()


def cleanup():
    # Clean up time
    fcntl.lockf(fp, fcntl.LOCK_UN)
    fp.close()
    os.unlink(pid_file)
    try:
        os.unlink(scan_file)
        os.unlink(pref_file)
        os.unlink(interface_conf_file)
    except:
        pass


if __name__ == "__main__":
    cleanup()
    Gdk.threads_init()
    Gdk.threads_enter()
    NetGUI()
    Gdk.threads_leave()
    Gtk.main()