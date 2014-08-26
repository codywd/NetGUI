'''
Basic TODO:
1.  Write help file (html/css/js)
2.  Finish preferences dialog
3.  Make notifications optional
4.  Write webbrowser.open wrapper script, where gid and uid are
    gid are set to the user, so it correctly runs, and doesn't
    error because it is set as root.
5.  Add tray icon
6.  Auto roaming capabilities (Preferences default profile, maybe
    set for multiple default profiles. NetCTL enable
7.  Basic network diagnostics?
8.  Incorporate surfatwork's NetCTL icon/applet for Gnome Shell
    (All actual coding is done for his, just incorporate it into
    ours somehow).
    (https://bbs.archlinux.org/viewtopic.php?id=182826)
'''

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


# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib
from gi.repository import Notify

# Checking for arguments in command line. We will never have a command line version of netgui (it's called netctl!)
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
    if arg == '--develop' or arg == '-d':
        print("Running in development mode. All files are set to be in the development folder.")
        program_loc = "./"
    if arg == '--nowifi' or arg == '-n':
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

        # Set all the handlers I defined in glade to local functions.
        handlers = {
            "onSwitch": self.onSwitch,
            "onExit": self.onBtnExit,
            "onAboutClicked": self.aboutClicked,
            "onScan": self.startScan,
            "onConnect": self.profileExists,
            "onDConnect": self.dConnectClicked,
            "onPrefClicked": self.prefClicked,
            "onHelpClicked": self.onHelpClicked,
            "onIssueReport": self.reportIssue,
            "onDAll": self.disconnect_all
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)

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
        self.interfaceName = get_interface()
        if self.interfaceName == "":
            n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            n.show()
            self.NoWifiScan(None)
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

    def no_wifi_scan(self):
        aps = {}
        profiles = os.listdir("/etc/netctl/")
        i = 0
        self.NoWifiMode = 1
        arg_no_wifi = 1
        for profile in profiles:
            if os.path.isfile("/etc/netctl/" + profile):
                aps["row" + str(i)] = self.APStore.append([profile, "", "", ""])
                self.APStore.set(aps["row" + str(i)], 1, "N/A in No-Wifi mode.")
                self.APStore.set(aps["row" + str(i)], 2, "N/A.")
                if is_connected() is False:
                    self.APStore.set(aps["row" + str(i)], 3, "No")
                else:
                    connectedNetwork = CheckOutput(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if profile in connectedNetwork:
                        self.APStore.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        self.APStore.set(aps["row" + str(i)], 3, "No")
                i = i + 1

    def startScan(self, e):
        ScanRoutines.scan(None)
        self.check_scan()

    def check_scan(self):
        sf = open(scan_file, 'r')
        realdir = sf.readline()
        realdir = realdir.strip()
        sf.close()
        print(realdir)
        shutil.move(realdir, status_dir + "final_results.log")

        with open(status_dir + "final_results.log") as tsv:
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

                if is_connected() is False:
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

    def onSwitch(self, e):
        self.APStore.clear()
        self.no_wifi_scan()
        self.NoWifiMode = 1
        arg_no_wifi = 1

    def onBtnExit(self, e):
        if self.p is None:
            pass
        else:
            self.p.terminate()
        sys.exit()
        Gtk.main_quit()

    def aboutClicked(self, e):
         # Getting the about dialog from UI.glade
        aboutDialog = self.builder.get_object("aboutDialog")
        # Opening the about dialog.
        aboutDialog.run()
        # Hiding the about dialog. Read in "prefDialog" for why we hide, not destroy.
        aboutDialog.hide()

    def profileExists(self, e):
        skipNoProfConn = 0
        select = self.APList.get_selection() # Get selected network
        SSID = self.getSSID(select) # Get SSID of selected network.
        for profile in os.listdir("/etc/netctl/"):
            if os.path.isfile("/etc/netctl/" + profile): # Is it a file, not dir?
                with open("/etc/netctl/" + profile, 'r') as current_profile:
                    current_profile_name = profile
                    for line in current_profile:
                        if "ESSID" in line.strip():
                            ESSIDName = line[6:]
                            if str(SSID).lower() in ESSIDName.lower():
                                self.connectClicked(1, current_profile_name)
                                skipNoProfConn = 1
                            else:
                                pass
                        else:
                            pass
            else:
                pass
        if skipNoProfConn is 1:
            pass
        else:
            self.connectClicked(0, None)

    def connectClicked(self, doesProfileExist, profileName):
        '''process a connection request from the user'''
        if doesProfileExist is 1:
            select = self.APList.get_selection()
            networkSSID = self.getSSID(select)
            n = Notify.Notification.new("Found existing profile.",
                "NetCTL found an existing profile for this network. Connecting to " + networkSSID + " using profile " + profileName)
            n.show()
            netinterface = self.interfaceName
            InterfaceControl.down(self, netinterface)
            NetCTL.stopall(self)
            NetCTL.start(self, profileName)
            n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
            n.show()

        elif doesProfileExist == 0:
            if self.NoWifiMode == 0:
                select = self.APList.get_selection()
                networkSSID = self.getSSID(select)
                print("nSSID = " + networkSSID)
                profile = "netgui_" + networkSSID
                print("profile = " + profile)
                netinterface = self.interfaceName
                if os.path.isfile(conf_dir + profile):
                    InterfaceControl.down(self, netinterface)
                    NetCTL.stopall(self)
                    NetCTL.start(profile)
                    n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
                    n.show()
                else:
                    networkSecurity = self.getSecurity(select)
                    key = self.get_network_pw()
                    create_config(networkSSID, self.interfaceName, networkSecurity, key)
                    try:
                        InterfaceControl.down(self, netinterface)
                        NetCTL.stopall(self)
                        NetCTL.start(self, profile)
                        n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
                        n.show()
                    except Exception as e:
                        n = Notify.Notification.new("Error!", "There was an error. The error was: " + str(e) + ". Please report an issue at the github page if it persists.", "dialog-information")
                        n.show()
                        Notify.uninit()
            elif self.NoWifiMode == 1:
                select = self.APList.get_selection()
                NWMprofile = self.getSSID(select)
                netinterface = get_interface()
                try:
                    InterfaceControl.down(self, netinterface)
                    NetCTL.stopall(self)
                    NetCTL.start(self, NWMprofile)
                    n = Notify.Notification.new("Connected to new profile!", "You are now connected to " + NWMprofile, "dialog-information")
                    n.show()
                except:
                    n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the github page if it persists.", "dialog-information")
                    n.show()
                    Notify.uninit()
            self.startScan(self)

    def get_network_pw(self):
        ret = self.dialog.run()
        self.dialog.hide()
        entry = self.builder.get_object("userEntry")
        if ret == 1:
            password = entry.get_text()
            return password

    def getSSID(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:
            return model[treeiter][0]

    def getSecurity(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter != None:
            securityType =  model[treeiter][2]
            securityType = securityType.lower()
            return securityType

    def dConnectClicked(self, e):
        select = self.APList.get_selection()
        networkSSID = self.getSSID(select)
        profile = "netgui_" + networkSSID
        interfaceName = get_interface()
        NetCTL.stop(self, profile)
        InterfaceControl.down(self, interfaceName)
        self.startScan(None)
        n = Notify.Notification.new("Disconnected from network!", "You are now disconnected from " + networkSSID, "dialog-information")
        n.show()

    def disconnect_all(self, e):
        select = self.APList.get_selection()
        networkSSID = self.getSSID(select)
        profile = "netgui_" + networkSSID
        interfaceName = get_interface()
        NetCTL.stopall(None)
        InterfaceControl.down(self, interfaceName)
        self.startScan(None)
        n = Notify.Notification.new("Disconnected from all networks!", "You are now disconnected from all networks.", "dialog-information")
        n.show()

    #TODO: Make rest of prefDialog work!
    def prefClicked(self, e):
        # Setting up the cancel function here fixes a weird bug where, if outside of the prefClicked function
        # it causes an extra button click for each time the dialog is hidden. The reason we hide the dialog
        # and not destroy it, is it causes another bug where the dialog becomes a small little
        # titlebar box. I don't know how to fix either besides this.
        def OnLoad(self):
            f = open(status_dir + "interface.cfg", 'r+')
            d = open(pref_file, 'r+')
            interfaceEntry.set_text(str(f.read()))
            for line in d:
                if "Default Profile:" in line:
                    default_profile.set_text(str(line)[17:])
                if "Unsecure Status:" in line:
                    if "No" in line:
                        unsecure_switch.set_active(False)
                    elif "Yes" in line:
                        unsecure_switch.set_active(True)
                if "Autoconnect Status:" in line:
                    if "No" in line:
                        autoconnect_switch.set_active(False)
                    elif "Yes" in line:
                        autoconnect_switch.set_active(True)
                if "NoteType:" in line:
                    if "Center" in line:
                        notification_type.set_active_id("1")
                    elif "Message" in line:
                        notification_type.set_active_id("2")
                    elif "Terminal" in line:
                        notification_type.set_active_id("3")
            f.close()
            d.close()

        def cancelClicked(self):
            preferencesDialog.hide()

        def chooseProfile(self):
            dialog = Gtk.FileChooserDialog("Choose your default profile.", None,
                Gtk.FileChooserAction.OPEN,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
            dialog.set_current_folder("/etc/netctl")

            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                default_profile.set_text(dialog.get_filename())
            elif response == Gtk.ResponseType.CANCEL:
                print("Cancel clicked")

            dialog.destroy()

        # Setting up the saveClicked function within the prefClicked function just because it looks cleaner
        # and because it makes the program flow more, IMHO
        def saveClicked(self):
            f = open(status_dir + "interface.cfg", 'r+')
            d = open(pref_file, 'r+')
            cur_int = f.read()
            f.close()
            new_int = interfaceEntry.get_text()
            if new_int != cur_int:
                for line in fileinput.input(status_dir + "interface.cfg", inplace=True):
                    print(new_int)

            if default_profile != "" or None:
                d.write("Default Profile: " + default_profile.get_text() + "\n")

            if unsecure_switch.get_active() is True:
                d.write("Unsecure Status: Yes\n")
            else:
                d.write("Unsecure Status: No\n")

            if autoconnect_switch.get_active() is True:
                d.write("Autoconnect Status: Yes\n")
            else:
                d.write("Autoconnect Status: No\n")

            nt = notification_type.get_active_text()
            d.write("NoteType: " + nt + "\n")
            d.close()
            preferencesDialog.hide()
        # Get everything we need from UI.glade
        go = self.builder.get_object
        preferencesDialog = go("prefDialog")
        saveButton = go("saveButton")
        cancelButton = go("cancelButton")
        interfaceEntry = go("wiInterface")
        default_profile = go("defaultProfilePath")
        unsecure_switch = go("unsecureSwitch")
        autoconnect_switch = go("autoconnectSwitch")
        notification_type = go("notification_type")
        filechooser = go("chooseDefaultProfile")

        # Connecting the "clicked" signals of each button to the relevant function.
        saveButton.connect("clicked", saveClicked)
        cancelButton.connect("clicked", cancelClicked)
        preferencesDialog.connect("show", OnLoad)
        filechooser.connect("clicked", chooseProfile)
        # Opening the Preferences Dialog.
        preferencesDialog.run()

    #TODO: Write help file!
    def onHelpClicked(self, e):
        pass

    def reportIssue(self, e):
        pass


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


class ScanRoutines():
    def __init__(self):
        super(ScanRoutines, self).__init__()
        self.p = None

    def scan(self):
        if os.path.exists(scan_file):
            os.remove(scan_file)
        if os.path.exists(status_dir + "final_results.log"):
            os.remove(status_dir + "final_results.log")
        p = multiprocessing.Process(target=ScanRoutines.run_scan(self))
        p.start()
        p.join()

    def run_scan(self):
        print("Please wait! Now Scanning.")
        # Huge thanks to joukewitteveen on GitHub for the following command!! Slightly modified from his comment
        subprocess.call('bash -c "source /usr/lib/network/globals; source /usr/lib/network/wpa; wpa_supplicant_scan ' + get_interface() + ' 3,4,5" >> ' + scan_file, shell=True)
        print("Done Scanning!")


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


def CheckOutput(self, command):
    # Run a command, return what it's output was, and convert it from bytes to unicode
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    output = p.communicate()[0]
    output = output.decode("utf-8")
    return output

''' Remove?
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