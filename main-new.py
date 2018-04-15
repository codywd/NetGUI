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
import time
from queue import Queue, Empty

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
        self.scanning = False
        self.thread = None
        self.APindex = 0
        self.builder = Gtk.Builder()
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(str(Path(program_loc, "UI.glade")))
        self.password_dialog = self.builder.get_object("passwordDialog")
        self.ap_list = self.builder.get_object("treeview1")
        self.ap_store = Gtk.ListStore(str, str, str, str)
        self.interface_name = ""
        self.NoWifiMode = False
        self.interface_control = InterfaceControl()
        self.generate_config = GenConfig(profile_dir)
        self.init_ui()

    def init_ui(self):
        is_connected() # Are we connected to a network?

        # Grab the "mainWindow" attribute from UI.glade, and set it to show everything.
        window = self.builder.get_object("mainWindow")
        window.connect("delete-event", Gtk.main_quit)

        # Get the buttons in case we need to disable them
        self.scan_button = self.builder.get_object("scanAPsTool")
        self.connect_button = self.builder.get_object("connectTool")
        self.disconnect_btn = self.builder.get_object("dConnectTool")
        self.preferences_btn = self.builder.get_object("prefToolBtn")
        self.exit_btn = self.builder.get_object("exitTool")

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
            "onExit": self.on_exit,
            "onAboutClicked": self.about_clicked,
            "onScan": self.start_scan,
            "onConnect": self.connect_clicked,
            "onDConnect": self.disconnect_clicked,
            "onPrefClicked": self.preferences_clicked,
            "onHelpClicked": self.help_clicked,
            "onIssueReport": self.report_issue,
            "onDAll": self.disconnect_all_clicked,
            "onEditorActivate": self.open_profile_editor
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)
        
        # Hardcode (relative) image paths
        APScanToolImg = self.builder.get_object("image1")
        APScanToolImg.set_from_file(str(Path(img_loc, "APScan.png")))
        
        ConnectToolImg = self.builder.get_object("image2")
        ConnectToolImg.set_from_file(str(Path(img_loc, "connect.png")))
        
        dConnectToolImg = self.builder.get_object("image3")
        dConnectToolImg.set_from_file(str(Path(img_loc, "disconnect.png")))
        
        prefToolImg = self.builder.get_object("image5")
        prefToolImg.set_from_file(str(Path(img_loc, "preferences.png")))
        
        exitToolImg = self.builder.get_object("image4")
        exitToolImg.set_from_file(str(Path(img_loc, "exit.png")))

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
            self.no_wifi_scan_mode()
            self.NoWifiMode = True
            self.scan_button.props.sensitive = False
            print(str(self.NoWifiMode))
        elif args.nowifi:
            self.no_wifi_scan_mode()
            self.NoWifiMode = True
            self.scan_button.props.sensitive = False
        else:
            #self.startScan(None)
            self.NoWifiMode = False

        # Start initial scan
        #Notify.init("NetGUI")
        window.show_all()

    def open_profile_editor(self, e):
        select = self.ap_list.get_selection()
        network_ssid = self.get_ssid(select)
        if network_ssid is None:
            profile_edit_window = NetGUIProfileEditor(None)
            profile_edit_window.show()
        else:
            profile = str(Path("/", "etc", "netctl", self.get_profile()))
            profile_edit_window = NetGUIProfileEditor(profile)
            profile_edit_window.show()

    def no_wifi_scan_mode(self):
        aps = {}
        profiles = os.listdir(profile_dir)
        i = 0
        self.NoWifiMode = 1
        global args
        args.nowifi = True
        for profile in profiles:
            if Path("/", "etc", "netctl", profile).is_file():
                aps["row" + str(i)] = self.ap_store.append([profile, "", "", ""])
                self.ap_store.set(aps["row" + str(i)], 1, "N/A in No-Wifi mode.")
                self.ap_store.set(aps["row" + str(i)], 2, "N/A")
                if is_connected is False:
                    self.ap_store.set(aps["row" + str(i)], 3, "No")
                else:
                    connected_network = check_output(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if profile in connected_network:
                        self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        self.ap_store.set(aps["row" + str(i)], 3, "No")
                i += 1

    def start_scan(self, e):
        is_scan_done_queue = Queue()
        run_scan = ScanRoutines(self.interface_name, scan_file, status_dir, is_scan_done_queue)
        scan_thread = threading.Thread(target=run_scan.scan)
        scan_thread.daemon = True
        self.scan_button.set_sensitive(False)
        scan_thread.start()

        self.is_thread_done(is_scan_done_queue, scan_thread, "check_scan")

    def is_thread_done(self, completion_queue, thread_to_join, reason):
        try:
            status = completion_queue.get(False)
            print(status)
            thread_to_join.join()
            if reason == "check_scan":
                self.begin_check_scan()
                self.scan_button.set_sensitive(True)
            elif reason == "new_scan":
                self.start_scan(self)
                self.scan_button.set_sensitive(True)
            elif reason == "netctl_stop_all":
                pass
            elif reason == "netctl_start":
                pass
            elif reason == "interface_down":
                pass
        except Empty:
            timer = threading.Timer(0.5, self.is_thread_done, args=[completion_queue, thread_to_join, reason])
            timer.start()

    def begin_check_scan(self):
        check_scan_thread = threading.Thread(target=self.check_scan)
        check_scan_thread.daemon = True
        check_scan_thread.start()

    def check_scan(self):
        with open(scan_file, 'r') as temp_file:
            real_dir = temp_file.readline()
            real_dir = real_dir.strip()
        shutil.move(real_dir, Path(status_dir, "final_results.log"))

        with open(Path(status_dir, "final_results.log")) as results_of_scan:
            self.ap_store.clear()

            reader = csv.reader(results_of_scan, dialect='excel-tab')
            aps = {}
            i = 0
            for row in reader:
                # Get network from scan, and filter out blank networks
                # and \x00 networks.
                network = row[2]
                if r"\x00" in network:
                    continue
                elif network is "":
                    continue
                else:
                    aps["row" + str(i)] = self.ap_store.append([network, "", "", ""])
                
                # Get quality from scan
                quality = int(row[0])
                if quality <= -100:
                    percent = "0%"
                elif quality >= -50:
                    percent = "100%"
                else:
                    final_quality = (2 * (quality + 100))
                    percent = str(final_quality) + "%"
                if network == "":
                    pass
                else:
                    self.ap_store.set(aps["row" + str(i)], 1, percent)

                # Get Security
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

                if is_connected is False:
                    if network != "":
                        self.ap_store.set(aps["row" + str(i)], 3, "No")
                else:
                    connected_network = check_output(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if network != "":
                        if network in connected_network:
                            self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                        else:
                            self.ap_store.set(aps["row" + str(i)], 3, "No")
                i += 1
        
    def on_switch(self, e):
        if self.NoWifiMode == False:
            self.ap_store.clear()
            self.no_wifi_scan_mode()
            self.NoWifiMode = True
        else:
            self.ap_store.clear()
            self.NoWifiMode = False

    def on_exit(self, e, d=None):
        if self.thread is None:
            pass
        else:
            self.thread.terminate()
        Gtk.main_quit()
        sys.exit(0)

    def about_clicked(self, e):
        about_dialog = self.builder.get_object("aboutDialog")
        about_dialog.run()
        about_dialog.hide()

    def get_profile(self):
        skip_no_prof_conn = False
        found_profile = False
        select = self.ap_list.get_selection()
        ssid = self.get_ssid(select)
        for profile in os.listdir(Path("/", "etc", "netctl")):
            if Path("/", "etc", "netctl", profile).is_file():
                with open(Path("/", "etc", "netctl", profile), 'r') as current_profile:
                    for line in current_profile:
                        if "ESSID" in line.strip():
                            essid_name = line[6:]
                            if str(ssid).lower() in essid_name.lower():
                                skip_no_prof_conn = True
                                return profile
        return None

    def start_new_thread(self, task, profile=None):
        task_queue = Queue()
        if task == "interface_down":
            thread = threading.Thread(target=InterfaceControl.down, args=[self.interface_name])
        elif task == "netctl_stop_all":
            thread = threading.Thread(target=NetCTL.stop_all)
        elif task == "netctl_start":
            thread = threading.Thread(target=NetCTL.start, args=[profile])
        elif task == "netctl_stop":
            thread = threading.Thread(target=NetCTL.stop, args=[profile])
        thread.daemon = True
        thread.start()
        self.is_thread_done(task_queue, thread, task)


    def connect_clicked(self, e):
        self.scan_button.set_sensitive(False)
        profile_name = self.get_profile()
        # process a connection request from the user
        if profile_name is not None:
            select = self.ap_list.get_selection()
            network_ssid = self.get_ssid(select)
            # TODO: Notification
            #n = Notify.Notification.new("Found existing profile.",
            #                            "NetCTL found an existing profile for this network. Connecting to " +
            #                            network_ssid + " using profile " + profile_name)
            #n.show()
            self.start_new_thread("interface_down")
            self.start_new_thread("netctl_stop_all")
            self.start_new_thread("netctl_start", profile_name)
            # TODO: Notification
            #n = Notify.Notification.new("Connected to new network!", "You are now connected to " + network_ssid,
            #                            "dialog-information")
            #n.show()

        else:
            if self.NoWifiMode == 0:
                select = self.ap_list.get_selection()
                network_ssid = self.get_ssid(select)
                print("nSSID = " + network_ssid)
                profile = "netgui_" + network_ssid
                print("profile = " + profile)
                if Path(profile_dir, profile).is_file():
                    self.start_new_thread("interface_down")
                    self.start_new_thread("netctl_stop_all")
                    self.start_new_thread("netctl_start", profile_name)
                    # TODO: Notification
                    # n = Notify.Notification.new("Connected to new network!", "You are now connected to " +
                    #                             network_ssid, "dialog-information")
                    # n.show()
                else:
                    network_security = self.get_security(select)
                    if network_security == "Open":
                        key = "none"
                    else:
                        key = self.get_network_password()
                    self.generate_config.create_wireless_config(network_ssid, self.interface_name, network_security, key)
                    try:
                        self.start_new_thread("interface_down")
                        self.start_new_thread("netctl_stop_all")
                        self.start_new_thread("netctl_start", profile_name)
                        #TODO: Notification
                        # n = Notify.Notification.new("Connected to new network!", "You are now connected to " +
                        #                             network_ssid, "dialog-information")
                        # n.show()
                    except Exception as e:
                        pass
                        # TODO: Notification
                        # n = Notify.Notification.new("Error!", "There was an error. The error was: " + str(e) +
                        #                             ". Please report an issue at the github page if it persists.",
                        #                             "dialog-information")
                        # n.show()
                        # Notify.uninit()
            elif self.NoWifiMode == 1:
                select = self.ap_list.get_selection()
                nwm_profile = self.get_ssid(select)
                net_interface = get_interface()
                try:
                    self.start_new_thread("interface_down")
                    self.start_new_thread("netctl_stop_all")
                    self.start_new_thread("netctl_start", nwm_profile)
                    # TODO: Notification
                    # n = Notify.Notification.new("Connected to new profile!", "You are now connected to " + nwm_profile,
                    #                             "dialog-information")
                    # n.show()
                except:
                    pass
                    # TODO: Notification
                    # n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the "
                    #                             + "github page if it persists.", "dialog-information")
                    # n.show()
                    # Notify.uninit()

        done_queue = Queue()
        wait_thread = threading.Thread(target=self.non_block_wait, args=[done_queue])
        wait_thread.daemon = True
        wait_thread.start()

        self.is_thread_done(done_queue, wait_thread, "new_scan")

    def get_network_password(self):
        ret = self.password_dialog.run()
        self.password_dialog.hide()
        entry = self.builder.get_object("userEntry")
        if ret == 1:
            password = entry.get_text()
            return password

    def get_ssid(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            return model[treeiter][0]

    def get_security(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            security_type = model[treeiter][2]
            security_type = security_type.lower()
            return security_type

    def disconnect_clicked(self, e):
        select = self.ap_list.get_selection()
        profile = self.get_profile()
        NetCTL.stop(profile)
        InterfaceControl.down(self, self.interface_name)
        self.start_scan(None)
        # TODO: Notification

    def disconnect_all_clicked(self, e):
        NetCTL.stop_all()
        # TODO: Check Interface Control
        InterfaceControl.down(None, self.interface_name)
        self.start_scan(None)

    def preferences_clicked(self, e):
        Preferences(program_loc)

    def help_clicked(self, e):
        pass

    def report_issue(self, e):
        pass

    def non_block_wait(self, queue):
        time.sleep(1)
        queue.put("Done")

def is_connected():
    check = subprocess.check_output("netctl list | sed -n 's/^\* //p'", shell=True)
    if check == b'':
        return False
    else:
        return True

def check_output(self, command):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    output = p.communicate()[0]
    output = output.decode("utf-8")
    return output

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