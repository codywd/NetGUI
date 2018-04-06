#! /usr/bin/python3

# Import Standard Libraries
import argparse
import csv
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

# Import third party libraries
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Gdk, GObject, GLib, GtkSource

# Importing project libraries
from Library.profile_editor import NetGUIProfileEditor
from Library.interface_control import InterfaceControl
from Library.netctl_functions import NetCTL
from Library.notifications import Notification
from Library.scanning import ScanRoutines
from Library.generate_config import GenConfig
from Library.preferences import Preferences

# Base App Info
program_version = "0.85"
profile_dir = Path("/", "etc", "netctl")
status_dir = Path("/", "var", "lib", "netgui")
program_loc = Path("/", "/usr", "share", "netgui")
interface_conf_file = Path(status_dir, "interface.cfg")
license_dir = Path("/", "usr", "share", "licenses", "netgui")
scan_file = Path(status_dir, "scan_results.log")
pid_file = Path(status_dir, "program.pid")
img_loc = Path(program_loc, "imgs")
pref_file = Path(status_dir, "preferences.cfg")
pid_number = os.getpid()
arg_no_wifi = 0

# Safety First! Do we have our directories?
if not Path(status_dir).exists():
    os.makedirs(status_dir)
if not Path(program_loc).exists():
    os.makedirs(program_loc)
if not Path(license_dir).exists():
    os.makedirs(license_dir)

# Parse a variety of arguments
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
    print('Your NetGUI version is ' + program_version + '.')
    sys.exit(0)

if args.develop:
    print('Running in development mode. ' +
          'All files are set to be in the development folder.')
    program_loc = './'
    img_loc = "./imgs"

if args.nowifi:
    print('Running in No Wifi mode!')

# We only can allow one instance of netgui for safety.
with open(pid_file, 'w') as fp:
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("We only allow one instance of netgui to be running at a time for precautionary reasons.")
        sys.exit(1)
    
    fp.write(str(pid_number)+"\n")
    fp.flush

class NetGUI(Gtk.Window):
    def __init__(self):
        pass

    def init_ui(self):
        is_connected() # Are we connected to a network?

        # Grab the "mainWindow" attribute from UI.glade, and set it to show everything.
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
        
        # Hardcode (relative) image paths
        APScanToolImg = self.builder.get_object("image1")
        APScanToolImg.set_from_file(img_loc + "/APScan.png")
        
        ConnectToolImg = self.builder.get_object("image2")
        ConnectToolImg.set_from_file(img_loc + "/connect.png")
        
        dConnectToolImg = self.builder.get_object("image3")
        dConnectToolImg.set_from_file(img_loc + "/disconnect.png")
        
        prefToolImg = self.builder.get_object("image5")
        prefToolImg.set_from_file(img_loc + "/preferences.png")
        
        exitToolImg = self.builder.get_object("image4")
        exitToolImg.set_from_file(img_loc + "/exit.png")

        # Populate profiles menu
        profile_menu = self.builder.get_object("profilesMenu")
        profile_menu.set_submenu(Gtk.Menu())
        profiles = os.listdir("/etc/netctl/")
        # Iterate through profiles directory, and add to "Profiles" Menu #
        for i in profiles:
            if Path("/etc/netctl/" + i).is_file():
                profile_menu.get_submenu().append(Gtk.MenuItem(label=i))
        #This should automatically detect their wireless device name. I'm not 100% sure
        #if it works on every computer, but we can only know from multiple tests. If
        #it doesn't work, I will re-implement the old way.
        self.interface_name = get_interface()
        if self.interface_name == "":
            #n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in " +
            #                            "No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            #n.show()
            self.no_wifi_scan()
            self.NoWifiMode = 1
            scan_button.props.sensitive = False
            print(str(self.NoWifiMode))
        elif args.nowifi:
            self.no_wifi_scan()
            self.NoWifiMode = 1
            scan_button.props.sensitive = False
        else:
            #self.startScan(None)
            self.NoWifiMode = 0

        # Start initial scan
        #Notify.init("NetGUI")
        window.show_all()

    def open_profile_editor(self, e):
        pass

    def no_wifi_scan_mode(self):
        pass

    def start_scan(self):
        run_scan = ScanRoutines(self.interface_name, scan_file, status_dir)
        print("starting scan...")
        threading.Thread(target=run_scan.scan())
        print("done scanning")

    def check_scan(self):
        pass

    def on_switch(self):
        pass

    def on_exit(self):
        pass

    def about_clicked(self):
        pass

    def profile_exists(self, e):
        pass

    def connect_clicked(self, does_profile_exist, profile_name):
        pass

    def get_network_password(self):
        pass

    def get_ssid(self, selection):
        pass

    def get_security(self, selection):
        pass

    def disconnect_clicked(self, e):
        pass

    def disconnect_all_clicked(self, e):
        pass

    def preferences_clicked(self, e):
        pass

    def help_clicked(self, e):
        pass

    def report_issue(self, e):
        pass

def is_connected():
    pass

def check_output(self, command):
    pass

def get_interface():
    interface_name = ""
    if not Path(interface_conf_file).is_file():

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
    Gdk.threads_init()
    Gdk.threads_enter()
    NetGUI()
    Gdk.threads_leave()
    Gtk.main()