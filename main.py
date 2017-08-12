'''
Basic TODO:
1.  Write help file (html/css/js)
2.  Finish preferences dialog (DONE!)
2a. Implement preference choices throughout the program.
3.  Make notifications optional
4.  Write webbrowser.open wrapper script, where gid and uid are
    gid are set to the user, so it correctly runs, and doesn't
    error because it is set as root.
5.  Add tray icon
6.  Auto roaming capabilities (Preferences default profile, maybe
    set for multiple default profiles? NetCTL enable)
7.  Basic network diagnostics?
8.  Incorporate surfatwork's NetCTL icon/applet for Gnome Shell
    (All actual coding is done for his, just incorporate it into
    ours somehow). (https://bbs.archlinux.org/viewtopic.php?id=182826)
    (Work in progress! Watch https://github.com/codywd/netctlgnome to watch the progress.)

'''

#! /usr/bin/python3

# Import Standard Libraries
import argparse
import csv
import fcntl
import fileinput
import multiprocessing
import os
import shutil
import subprocess
import sys

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
# arg_no_wifi = 0

file_to_pass = ""


# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib, GtkSource
from gi.repository import Notify

# Checking for arguments in command line. We will never have a command line version of netgui (it's called netctl!)

# argument parser
parser = argparse.ArgumentParser(description='NetGUI; The NetCTL GUI! ' +
                                             'We need root :)')
parser.add_argument('-v', '--version',
                    help='show the current version of NetGUI',
                    action='store_true')
parser.add_argument('-d', '--develop',
                    help='run in development mode. ' +
                    'If you are not a developer, do not use this.',
                    action='store_true')
parser.add_argument('-n', '--nowifi',
                    help='run in no-wifi-mode. ' +
                         'Does not scan for networks. ' +
                         'Uses profiles to connect.',
                    action='store_true')
args = parser.parse_args()
if args.version:
    print('Your NetGUI version is ' + prog_ver + '.')
    sys.exit(0)

if args.develop:
    print('Running in development mode. ' +
          'All files are set to be in the development folder.')
    program_loc = './'

if args.nowifi:
    print('Running in No Wifi mode!')

# Import Project Libraries
import profileEditor

# If our directory for netgui does not exist, create it.
if os.path.exists(status_dir):
    pass
else:
    subprocess.call("mkdir " + status_dir, shell=True)

# Let's make sure we're root, while at it.
euid = os.geteuid()
if euid != 0:
    print("netgui needs to be run as root, since many commands we use requires it.\n" +
          "Please sudo or su -c and try again.")
    sys.exit(77)

# Let's also not allow any more than one instance of netgui.
fp = open(pid_file, 'w')
try:
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(program_loc + "UI.glade")
        self.dialog = self.builder.get_object("passwordDialog")
        self.ap_list = self.builder.get_object("treeview1")
        self.ap_store = Gtk.ListStore(str, str, str, str)
        self.interface_name = ""
        self.NoWifiMode = 0
        self.init_ui()

    def init_ui(self):
        is_connected()
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.

        # Grab the "window1" attribute from UI.glade, and set it to show everything.
        window = self.builder.get_object("mainWindow")
        window.connect("delete-event", Gtk.main_quit)

        # Get the OnScan button in case we are going to run in NoWifiMode
        scan_button = self.builder.get_object("scanAPsTool")

        # Setup the main area of netgui: The network list.

        self.ap_list.set_model(self.ap_store)

        # Set Up Columns
        # renderer1 = The Cell renderer. Basically allows for text to show.
        # column1 = The actual setup of the column. Arguments = title, CellRenderer, textIndex)
        # Actually append the column to the treeview.
        ssid_cell_renderer = Gtk.CellRendererText()
        ssid_column = Gtk.TreeViewColumn("SSID", ssid_cell_renderer, text=0)
        ssid_column.set_resizable(True)
        ssid_column.set_expand(True)
        self.ap_list.append_column(ssid_column)

        connect_quality_cell_renderer = Gtk.CellRendererText()
        connect_quality_column = Gtk.TreeViewColumn("Connection Quality", connect_quality_cell_renderer, text=1)
        connect_quality_column.set_resizable(True)
        connect_quality_column.set_expand(True)
        self.ap_list.append_column(connect_quality_column)

        security_type_cell_renderer = Gtk.CellRendererText()
        security_type_column = Gtk.TreeViewColumn("Security Type", security_type_cell_renderer, text=2)
        security_type_column.set_resizable(True)
        security_type_column.set_expand(True)
        self.ap_list.append_column(security_type_column)

        connected_cell_renderer = Gtk.CellRendererText()
        connected_column = Gtk.TreeViewColumn("Connected?", connected_cell_renderer, text=3)
        connected_column.set_resizable(True)
        connected_column.set_expand(True)
        self.ap_list.append_column(connected_column)

        # Set TreeView as Re-orderable
        self.ap_list.set_reorderable(True)

        # Set all the handlers I defined in glade to local functions.
        handlers = {
            "onSwitch": self.on_switch,
            "onExit": self.on_btn_exit,
            "onAboutClicked": self.about_clicked,
            "onScan": self.start_scan,
            "onConnect": self.profile_exists,
            "onDConnect": self.disconnect_clicked,
            "onPrefClicked": self.preferences_clicked,
            "onHelpClicked": self.on_help_clicked,
            "onIssueReport": self.report_issue,
            "onDAll": self.disconnect_all,
            "onEditorActivate": self.open_editor
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)

        # Populate profiles menu
        #menu = self.builder.get_object("menubar1")
        profile_menu = self.builder.get_object("profilesMenu")
        profile_menu.set_submenu(Gtk.Menu())
        profiles = os.listdir("/etc/netctl/")
        # Iterate through profiles directory, and add to "Profiles" Menu #
        for i in profiles:
            if os.path.isfile("/etc/netctl/" + i):
                profile_menu.get_submenu().append(Gtk.MenuItem(label=i))
        #This should automatically detect their wireless device name. I'm not 100% sure
        #if it works on every computer, but we can only know from multiple tests. If
        #it doesn't work, I will re-implement the old way.
        self.interface_name = get_interface()
        if self.interface_name == "":
            n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in " +
                                        "No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            n.show()
            self.NoWifiScan(None)
            self.NoWifiMode = 1
            scan_button.props.sensitive = False
            print(str(self.NoWifiMode))
        elif args.nowifi:
            self.NoWifiScan(None)
            self.NoWifiMode = 1
            scan_button.props.sensitive = False
        else:
            #self.startScan(None)
            self.NoWifiMode = 0

        # Start initial scan
        Notify.init("NetGUI")
        window.show_all()

    def open_editor(self, e):
        open(status_dir + "profile_to_edit", 'w').close()
        select = self.ap_list.get_selection()
        network_ssid = self.get_ssid(select)
        if network_ssid is None:
            profileEditor.NetGUIProfileEditor()
        else:
            profile = "/etc/netctl/netgui_" + network_ssid
            d = open(status_dir + "profile_to_edit", 'w')
            d.write(profile)
            d.close()
            profileEditor.NetGUIProfileEditor()

    def no_wifi_scan(self):
        aps = {}
        profiles = os.listdir("/etc/netctl/")
        i = 0
        self.NoWifiMode = 1
        global args
        args.nowifi = True
        for profile in profiles:
            if os.path.isfile("/etc/netctl/" + profile):
                aps["row" + str(i)] = self.ap_store.append([profile, "", "", ""])
                self.ap_store.set(aps["row" + str(i)], 1, "N/A in No-Wifi mode.")
                self.ap_store.set(aps["row" + str(i)], 2, "N/A.")
                if is_connected() is False:
                    self.ap_store.set(aps["row" + str(i)], 3, "No")
                else:
                    connected_network = check_output(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if profile in connected_network:
                        self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        self.ap_store.set(aps["row" + str(i)], 3, "No")
                i += 1

    def start_scan(self, e):
        ScanRoutines.scan(None)
        self.check_scan()

    def check_scan(self):
        sf = open(scan_file, 'r')
        real_dir = sf.readline()
        real_dir = real_dir.strip()
        sf.close()
        print(real_dir)
        shutil.move(real_dir, status_dir + "final_results.log")

        with open(status_dir + "final_results.log") as tsv:
            self.ap_store.clear()

            r = csv.reader(tsv, dialect='excel-tab')
            aps = {}
            i = 0
            for row in r:
                network = row[2]
                print(ascii(network))
                if r"\x00" in network:
                    continue
                elif network is "":
                    continue
                else:
                    aps["row" + str(i)] = self.ap_store.append([network, "", "", ""])
                quality = row[0]
                if int(quality) <= -100:
                    percent = "0%"
                elif int(quality) >= -50:
                    percent = "100%"
                else:
                    final_quality = (2 * (int(quality) + 100))
                    percent = str(final_quality) + "%"
                if network == "":
                    pass
                else:
                    self.ap_store.set(aps["row" + str(i)], 1, percent)

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
                    self.ap_store.set(aps["row" + str(i)], 2, encryption)

                if is_connected() is False:
                    if network == "":
                        pass
                    else:
                        if network == "":
                            pass
                        else:
                            self.ap_store.set(aps["row" + str(i)], 3, "No")
                else:
                    connected_network = check_output(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if network in connected_network:
                        if network == "":
                            pass
                        else:
                            self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        if network == "":
                            pass
                        else:
                            self.ap_store.set(aps["row" + str(i)], 3, "No")

                i += 1

    def on_switch(self, e):
        self.ap_store.clear()
        self.no_wifi_scan()
        self.NoWifiMode = 1
        global args
        args.nowifi = True

    def on_btn_exit(self, e):
        if self.p is None:
            pass
        else:
            self.p.terminate()
        Gtk.main_quit()
        sys.exit()

    def about_clicked(self, e):
         # Getting the about dialog from UI.glade
        about_dialog = self.builder.get_object("aboutDialog")
        # Opening the about dialog.
        about_dialog.run()
        # Hiding the about dialog. Read in "prefDialog" for why we hide, not destroy.
        about_dialog.hide()

    def profile_exists(self, e):
        skip_no_prof_conn = 0
        found_profile = 0
        select = self.ap_list.get_selection()  # Get selected network
        ssid = self.get_ssid(select)  # Get SSID of selected network.
        for profile in os.listdir("/etc/netctl/"):
            if os.path.isfile("/etc/netctl/" + profile):  # Is it a file, not dir?
                with open("/etc/netctl/" + profile, 'r') as current_profile:
                    current_profile_name = profile
                    for line in current_profile:
                        if "ESSID" in line.strip():
                            essid_name = line[6:]
                            if str(ssid).lower() in essid_name.lower():
                                skip_no_prof_conn = 1
                                if found_profile is 1:
                                    break
                                else:
                                    self.connect_clicked(1, current_profile_name)
                                    found_profile = 1
                            else:
                                pass
                        else:
                            pass
            else:
                pass
        if skip_no_prof_conn is 1:
            pass
        else:
            self.connect_clicked(0, None)

    def connect_clicked(self, does_profile_exist, profile_name):
        # process a connection request from the user
        if does_profile_exist is 1:
            select = self.ap_list.get_selection()
            network_ssid = self.get_ssid(select)
            n = Notify.Notification.new("Found existing profile.",
                                        "NetCTL found an existing profile for this network. Connecting to " +
                                        network_ssid + " using profile " + profile_name)
            n.show()
            net_interface = self.interface_name
            InterfaceControl.down(self, net_interface)
            NetCTL.stop_all(self)
            NetCTL.start(self, profile_name)
            n = Notify.Notification.new("Connected to new network!", "You are now connected to " + network_ssid,
                                        "dialog-information")
            n.show()

        elif does_profile_exist == 0:
            if self.NoWifiMode == 0:
                select = self.ap_list.get_selection()
                network_ssid = self.get_ssid(select)
                print("nSSID = " + network_ssid)
                profile = "netgui_" + network_ssid
                print("profile = " + profile)
                net_interface = self.interface_name
                if os.path.isfile(profile_dir + profile):
                    InterfaceControl.down(self, net_interface)
                    NetCTL.stop_all(self)
                    NetCTL.start(profile)
                    n = Notify.Notification.new("Connected to new network!", "You are now connected to " +
                                                network_ssid, "dialog-information")
                    n.show()
                else:
                    network_security = self.get_security(select)
                    if network_security == "Open":
                        key = "none"
                    else:
                        key = self.get_network_pw()
                    create_config(network_ssid, self.interface_name, network_security, key)
                    try:
                        InterfaceControl.down(self, net_interface)
                        NetCTL.stop_all(self)
                        NetCTL.start(self, profile)
                        n = Notify.Notification.new("Connected to new network!", "You are now connected to " +
                                                    network_ssid, "dialog-information")
                        n.show()
                    except Exception as e:
                        n = Notify.Notification.new("Error!", "There was an error. The error was: " + str(e) +
                                                    ". Please report an issue at the github page if it persists.",
                                                    "dialog-information")
                        n.show()
                        Notify.uninit()
            elif self.NoWifiMode == 1:
                select = self.ap_list.get_selection()
                nwm_profile = self.get_ssid(select)
                net_interface = get_interface()
                try:
                    InterfaceControl.down(self, net_interface)
                    NetCTL.stop_all(self)
                    NetCTL.start(self, nwm_profile)
                    n = Notify.Notification.new("Connected to new profile!", "You are now connected to " + nwm_profile,
                                                "dialog-information")
                    n.show()
                except:
                    n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the "
                                                + "github page if it persists.", "dialog-information")
                    n.show()
                    Notify.uninit()
            self.start_scan(self)

    def get_network_pw(self):
        ret = self.dialog.run()
        self.dialog.hide()
        entry = self.builder.get_object("userEntry")
        if ret == 1:
            password = entry.get_text()
            return password


    def get_ssid(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            return model[treeiter][0]

    @staticmethod
    def get_security(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            security_type = model[treeiter][2]
            security_type = security_type.lower()
            return security_type

    def disconnect_clicked(self, e):
        select = self.ap_list.get_selection()
        network_ssid = self.get_ssid(select)
        profile = "netgui_" + network_ssid
        interface_name = get_interface()
        NetCTL.stop(self, profile)
        InterfaceControl.down(self, interface_name)
        self.start_scan(None)
        n = Notify.Notification.new("Disconnected from network!", "You are now disconnected from " + network_ssid,
                                    "dialog-information")
        n.show()

    def disconnect_all(self, e):
        interface_name = get_interface()
        NetCTL.stop_all(None)
        InterfaceControl.down(self, interface_name)
        self.start_scan(None)
        n = Notify.Notification.new("Disconnected from all networks!", "You are now disconnected from all networks.",
                                    "dialog-information")
        n.show()

    def preferences_clicked(self, e):
        # Setting up the cancel function here fixes a weird bug where, if outside of the prefClicked function
        # it causes an extra button click for each time the dialog is hidden. The reason we hide the dialog
        # and not destroy it, is it causes another bug where the dialog becomes a small little
        # titlebar box. I don't know how to fix either besides this.
        def on_load(self):
            f = open(status_dir + "interface.cfg", 'r+')
            d = open(pref_file, 'r+')
            interface_entry.set_text(str(f.read()))
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

        def cancel_clicked(self):
            preferences_dialog.hide()

        def choose_profile(self):
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
        def save_clicked(self):
            f = open(status_dir + "interface.cfg", 'r+')
            d = open(pref_file, 'r+')
            cur_int = f.read()
            f.close()
            new_int = interface_entry.get_text()
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
            preferences_dialog.hide()
        # Get everything we need from UI.glade
        go = self.builder.get_object
        preferences_dialog = go("prefDialog")
        save_button = go("saveButton")
        cancel_button = go("cancelButton")
        interface_entry = go("wiInterface")
        default_profile = go("defaultProfilePath")
        unsecure_switch = go("unsecureSwitch")
        autoconnect_switch = go("autoconnectSwitch")
        notification_type = go("notification_type")
        filechooser = go("chooseDefaultProfile")

        # Connecting the "clicked" signals of each button to the relevant function.
        save_button.connect("clicked", save_clicked)
        cancel_button.connect("clicked", cancel_clicked)
        preferences_dialog.connect("show", on_load)
        filechooser.connect("clicked", choose_profile)
        # Opening the Preferences Dialog.
        preferences_dialog.run()

    #TODO: Write help file!
    def on_help_clicked(self, e):
        pass

    def report_issue(self, e):
        pass


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


class InterfaceControl(object):
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

    @staticmethod
    def run_scan(self):
        print("Please wait! Now Scanning.")
        # Huge thanks to joukewitteveen on GitHub for the following command!! Slightly modified from his comment
        subprocess.call('bash -c "source /usr/lib/netctl/globals; source /usr/lib/netctl/wpa; wpa_supplicant_scan ' +
                        get_interface() + ' 3,4,5" >> ' + scan_file, shell=True)
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
    f.write("\nIP=%s\n" % ip)
    f.close()
    print("Alright, I have finished making the profile!")


def is_connected():
    # If we are connected to a network, it lists it. Otherwise, it returns nothing (or an empty byte).
    check = subprocess.check_output("netctl list | sed -n 's/^\* //p'", shell=True)
    if check == b'':
        return False
    else:
        return True


def check_output(self, command):
    # Run a command, return what it's output was, and convert it from bytes to unicode
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    output = p.communicate()[0]
    output = output.decode("utf-8")
    return output


def get_interface():
    interface_name = ""
    if not os.path.isfile(interface_conf_file):

        devices = os.listdir("/sys/class/net")
        for device in devices:
            if "wl" in device:
                interface_name = device
            else:
                pass
        if interface_name == "":
            int_name_check = str(subprocess.check_output("cat /proc/net/wireless", shell=True))
            interface_name = int_name_check[166:172]
        if interface_name == "":
            #interfaceName = Need the code here
            pass
        f = open(interface_conf_file, 'w')
        f.write(interface_name)
        f.close()
        return str(interface_name).strip()
    else:
        f = open(interface_conf_file, 'r')
        interface_name = f.readline()
        f.close()
        return str(interface_name).strip()


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