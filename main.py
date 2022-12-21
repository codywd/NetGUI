#! /usr/bin/python3

# Import Standard Libraries
import argparse
import csv
import fcntl
import json
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

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
gi.require_version("Notify", "0.7")
from gi.repository import Gtk, GObject, GtkSource

# Importing project libraries
from Library.profile_editor import NetGUIProfileEditor
from Library.interface_control import InterfaceControl
from Library.netctl_functions import NetCTL
from Library.notifications import Notification
from Library.scanning import ScanRoutines
from Library.generate_config import GenConfig
from Library.preferences import Preferences

# Define Constants
PROGRAM_VERSION = "0.86"
PROFILE_DIR = Path("/", "etc", "netctl")
STATUS_DIR = Path("/", "var", "lib", "netgui")
PROGRAM_LOC = Path("/", "usr", "share", "netgui")
INTERFACE_CONF_FILE = Path(STATUS_DIR, "interface.cfg")
LICENSE_DIR = Path("/", "usr", "share", "licenses", "netgui")
SCAN_FILE = Path(STATUS_DIR, "scan_results.log")
PID_FILE = Path(STATUS_DIR, "program.pid")
IMG_LOC = Path(PROGRAM_LOC, "imgs")
PREF_FILE = Path(STATUS_DIR, "preferences.json")
PID_NUMBER = os.getpid()
ARG_NO_WIFI = 0

# Safety First! Do we have our directories?
if not Path(STATUS_DIR).exists():
    os.makedirs(STATUS_DIR)
if not Path(PROGRAM_LOC).exists():
    os.makedirs(PROGRAM_LOC)
if not Path(LICENSE_DIR).exists():
    os.makedirs(LICENSE_DIR)
if not Path(PREF_FILE).exists():
    json_prefs = {
        "default_profile": "",
        "unsecure_status": "False",
        "autoconnect": "False",
        "notification_type": "Terminal",
    }

    with open(PREF_FILE, "w+") as outfile:
        json.dump(json_prefs, outfile)

# Parse a variety of arguments
parser = argparse.ArgumentParser(
    description="NetGUI; The NetCTL GUI! " + "We need root :)"
)
parser.add_argument(
    "-v", "--version", help="show the current version of NetGUI", action="store_true"
)
parser.add_argument(
    "-d",
    "--develop",
    help="run in development mode. " + "If you are not a developer, do not use this.",
    action="store_true",
)
parser.add_argument(
    "-n",
    "--nowifi",
    help="run in no-wifi-mode. "
    + "Does not scan for networks. "
    + "Uses profiles to connect.",
    action="store_true",
)
args = parser.parse_args()
if args.version:
    print("Your NetGUI version is " + PROGRAM_VERSION + ".")
    sys.exit(0)

if args.develop:
    print(
        "Running in development mode. "
        + "All files are set to be in the development folder."
    )
    PROGRAM_LOC = "./"
    IMG_LOC = "./imgs"

if args.nowifi:
    print("Running in No Wifi mode!")

# We only can allow one instance of netgui for safety.
with open(PID_FILE, "w") as fp:
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print(
            "We only allow one instance of netgui to be running at a time for precautionary reasons."
        )
        sys.exit(1)

    fp.write(str(PID_NUMBER) + "\n")
    fp.flush


class NetGUI(Gtk.Window):
    def __init__(self):
        self.scanning = False
        self.thread = None
        self.APindex = 0
        self.builder = Gtk.Builder()
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(str(Path(PROGRAM_LOC, "new-ui.glade")))
        self.password_dialog = self.builder.get_object("passwordDialog")
        self.ap_list = self.builder.get_object("treeview1")
        self.ap_store = Gtk.ListStore(str, str, str, str)
        self.statusbar = self.builder.get_object("statusbar1")
        self.context = self.statusbar.get_context_id("netgui")
        self.interface_name = ""
        self.NoWifiMode = False
        self.interface_control = InterfaceControl()
        self.next_function = None
        self.generate_config = GenConfig(PROFILE_DIR)

        self.notifications = Notification()

        self.init_ui()

    def init_ui(self):
        is_connected()  # Are we connected to a network?

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
        connect_quality_column = Gtk.TreeViewColumn(
            "Connection Quality", connect_quality_cell_renderer, text=1
        )
        connect_quality_column.set_resizable(True)
        connect_quality_column.set_expand(True)
        self.ap_list.append_column(connect_quality_column)

        security_type_cell_renderer = Gtk.CellRendererText()
        security_type_column = Gtk.TreeViewColumn(
            "Security Type", security_type_cell_renderer, text=2
        )
        security_type_column.set_resizable(True)
        security_type_column.set_expand(True)
        self.ap_list.append_column(security_type_column)

        connected_cell_renderer = Gtk.CellRendererText()
        connected_column = Gtk.TreeViewColumn(
            "Connected?", connected_cell_renderer, text=3
        )
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
            "onEditorActivate": self.open_profile_editor,
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)

        # Hardcode (relative) image paths
        APScanToolImg = self.builder.get_object("image1")
        APScanToolImg.set_from_file(str(Path(IMG_LOC, "APScan.png")))

        ConnectToolImg = self.builder.get_object("image2")
        ConnectToolImg.set_from_file(str(Path(IMG_LOC, "connect.png")))

        dConnectToolImg = self.builder.get_object("image3")
        dConnectToolImg.set_from_file(str(Path(IMG_LOC, "disconnect.png")))

        prefToolImg = self.builder.get_object("image5")
        prefToolImg.set_from_file(str(Path(IMG_LOC, "preferences.png")))

        exitToolImg = self.builder.get_object("image4")
        exitToolImg.set_from_file(str(Path(IMG_LOC, "exit.png")))

        # Populate profiles menu
        profile_menu = self.builder.get_object("profilesMenu")
        profile_menu.set_submenu(Gtk.Menu())
        profiles = os.listdir("/etc/netctl/")
        # Iterate through profiles directory, and add to "Profiles" Menu #
        for i in profiles:
            if Path("/etc/netctl/" + i).is_file():
                profile_menu.get_submenu().append(Gtk.MenuItem(label=i))
        # This should automatically detect their wireless device name. I'm not 100% sure
        # if it works on every computer, but we can only know from multiple tests. If
        # it doesn't work, I will re-implement the old way.
        self.interface_name = get_interface()
        global args
        if self.interface_name == "" or args.nowifi:
            self.notifications.show_notification(
                "Could not detect interface!",
                "No interface was detected. Now running in "
                + "No-Wifi Mode. Scan Button is disabled.",
            )
            self.no_wifi_scan_mode()
            self.NoWifiMode = True
            self.scan_button.props.sensitive = False
        else:
            self.NoWifiMode = False

        # Start initial scan
        self.start_scan(None)
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
        profiles = os.listdir(PROFILE_DIR)
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
                    connected_network = check_output(
                        self, "netctl list | sed -n 's/^\* //p'"
                    ).strip()
                    if profile in connected_network:
                        self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        self.ap_store.set(aps["row" + str(i)], 3, "No")
                i += 1

    def start_scan(self, e):
        self.notifications.show_notification(
            "Starting scan", "Scan is now beginning. Please wait for completion."
        )
        is_scan_done_queue = Queue()
        run_scan = ScanRoutines(
            self.interface_name, SCAN_FILE, STATUS_DIR, is_scan_done_queue
        )
        scan_thread = threading.Thread(target=run_scan.scan)
        scan_thread.daemon = True
        self.disable_buttons()
        self.statusbar.push(self.context, "Scanning...")
        scan_thread.start()
        self.is_thread_done(is_scan_done_queue, scan_thread)

    def is_thread_done(self, completion_queue, thread_to_join):
        try:
            completion_queue.get(False)
            thread_to_join.join()
            self.begin_check_scan()
            self.statusbar.push(self.context, "Scanning Complete.")
            self.enable_buttons()
        except Empty:
            timer = threading.Timer(
                0.5, self.is_thread_done, args=[completion_queue, thread_to_join]
            )
            timer.start()

    def begin_check_scan(self):
        check_scan_thread = threading.Thread(target=self.check_scan)
        check_scan_thread.daemon = True
        check_scan_thread.start()

    def check_scan(self):
        try:
            with open(SCAN_FILE, "r") as temp_file:
                real_dir = temp_file.readline()
                real_dir = real_dir.strip()
            try:
                shutil.move(real_dir, Path(STATUS_DIR, "final_results.log"))
                try:
                    with open(Path(STATUS_DIR, "final_results.log")) as results_of_scan:
                        self.ap_store.clear()

                        reader = csv.reader(results_of_scan, dialect="excel-tab")
                        aps = {}
                        i = 0
                        for row in reader:
                            # Get network from scan, and filter out blank networks
                            # and \x00 networks.
                            network = row[2]
                            if r"\x00" in network:
                                continue
                            elif network == "":
                                continue
                            else:
                                aps["row" + str(i)] = self.ap_store.append(
                                    [network, "", "", ""]
                                )

                            # Get quality from scan
                            quality = int(row[0])
                            if quality <= -100:
                                percent = "0%"
                            elif quality >= -50:
                                percent = "100%"
                            else:
                                final_quality = 2 * (quality + 100)
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
                                connected_network = check_output(
                                    self, "netctl list | sed -n 's/^\* //p'"
                                ).strip()
                                if network != "":
                                    if network in connected_network:
                                        self.ap_store.set(aps["row" + str(i)], 3, "Yes")
                                    else:
                                        self.ap_store.set(aps["row" + str(i)], 3, "No")
                            i += 1
                except FileNotFoundError:
                    self.notifications.show_notification(
                        "Error checking scan!",
                        "Perhaps there were no networks nearby!",
                        self,
                    )
                    self.statusbar.push(
                        self.context,
                        "Error checking results. Perhaps there are no networks nearby.",
                    )
            except FileNotFoundError:
                self.notifications.show_notification(
                    "Error checking scan!",
                    "Perhaps there were no networks nearby!",
                    self,
                )
                self.statusbar.push(
                    self.context,
                    "Error checking results. Perhaps there are no networks nearby.",
                )
        except FileNotFoundError:
            self.notifications.show_notification(
                "Error checking scan!", "Perhaps there were no networks nearby!", self
            )
            self.statusbar.push(
                self.context,
                "Error checking results. Perhaps there are no networks nearby.",
            )

    def on_switch(self, e):
        if self.NoWifiMode == False:
            self.notifications.show_notification(
                "Switching to No-Wifi mode.", "Switching to no-wifi mode.", self
            )
            self.ap_store.clear()
            self.no_wifi_scan_mode()
            self.NoWifiMode = True
        else:
            self.notifications.show_notification(
                "Switching to wifi mode.", "Switching to wifi mode.", self
            )
            self.ap_store.clear()
            self.NoWifiMode = False

    def on_exit(self, e, d=None):
        if self.thread is None:
            pass
        else:
            self.thread.join()
        Gtk.main_quit()
        sys.exit(0)

    def about_clicked(self, e):
        about_dialog = self.builder.get_object("aboutDialog")
        about_dialog.run()
        about_dialog.hide()

    def get_profile(self):
        select = self.ap_list.get_selection()
        ssid = self.get_ssid(select)
        for profile in os.listdir(Path("/", "etc", "netctl")):
            if Path("/", "etc", "netctl", profile).is_file():
                with open(Path("/", "etc", "netctl", profile), "r") as current_profile:
                    for line in current_profile:
                        if "ESSID" in line.strip():
                            essid_name = line[6:]
                            if str(ssid).lower() in essid_name.lower():
                                return profile
        return None

    def connect_clicked(self, e):
        self.disable_buttons()
        profile_name = self.get_profile()
        if profile_name is not None:
            self.notifications.show_notification(
                "Profile found!",
                "Found profile {} for this network. Connecting "
                + "using pre-existing profile!".format(profile_name),
                self,
            )
            select = self.ap_list.get_selection()
            network_ssid = self.get_ssid(select)
            self.statusbar.push(self.context, "Connecting to {}".format(profile_name))

            InterfaceControl.down(self.interface_name)
            NetCTL.stop_all()
            NetCTL.start(profile_name)
            self.statusbar.push(self.context, "Connected to {}".format(profile_name))
        else:
            if self.NoWifiMode == False:
                self.notifications.show_notification(
                    "No profile found.",
                    "There is no profile for this network. Creating one now!",
                    self,
                )
                select = self.ap_list.get_selection()
                network_ssid = self.get_ssid(select)
                profile = "netgui_" + network_ssid
                if Path(PROFILE_DIR, profile).is_file():
                    InterfaceControl.down(self.interface_name)
                    NetCTL.stop_all()
                    NetCTL.start(profile_name)
                else:
                    network_security = self.get_security(select)
                    if network_security == "Open":
                        key = "none"
                    else:
                        key = self.get_network_password()
                    self.generate_config.create_wireless_config(
                        network_ssid, self.interface_name, network_security, key
                    )
                    try:
                        InterfaceControl.down(self.interface_name)
                        NetCTL.stop_all()
                        NetCTL.start(profile_name)
                    except Exception as e:
                        pass
            elif self.NoWifiMode == 1:
                self.notifications.show_notification(
                    "We are in no-wifi mode.",
                    "We are in no-wifi mode, connecting to existing profile.",
                    self,
                )
                select = self.ap_list.get_selection()
                nwm_profile = self.get_profile()
                try:
                    InterfaceControl.down(self.interface_name)
                    NetCTL.stop_all()
                    NetCTL.start(nwm_profile)
                except:
                    pass
        self.start_scan(None)
        GObject.timeout_add_seconds(5, self.enable_buttons)

    def disable_buttons(self):
        self.scan_button.set_sensitive(False)
        self.connect_button.set_sensitive(False)
        self.disconnect_btn.set_sensitive(False)
        self.exit_btn.set_sensitive(False)
        self.preferences_btn.set_sensitive(False)

    def enable_buttons(self):
        self.scan_button.set_sensitive(True)
        self.connect_button.set_sensitive(True)
        self.disconnect_btn.set_sensitive(True)
        self.exit_btn.set_sensitive(True)
        self.preferences_btn.set_sensitive(True)

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
        self.notifications.show_notification(
            "Stopping profile.", "Stopping profile: {}".format(profile), self
        )
        InterfaceControl.down(self.interface_name)
        self.start_scan(None)

    def disconnect_all_clicked(self, e):
        self.notifications.show_notification(
            "Stopping all profiles.", "Stopping all profiles!", self
        )
        NetCTL.stop_all()
        InterfaceControl.down(self.interface_name)
        self.start_scan(None)

    def preferences_clicked(self, e):
        Preferences(PROGRAM_LOC)

    def help_clicked(self, e):
        self.notifications.show_notification(
            "Not Implemented", "This function is not yet implemented.", self
        )

    def report_issue(self, e):
        self.notifications.show_notification(
            "Not Implemented", "This function is not yet implemented.", self
        )


def is_connected():
    check = subprocess.check_output("netctl list | sed -n 's/^\* //p'", shell=True)
    if check == b"":
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
    if not Path(INTERFACE_CONF_FILE).is_file():

        devices = os.listdir("/sys/class/net")
        for device in devices:
            if "wl" in device:
                interface_name = device
            else:
                pass
        if interface_name == "":
            int_name_check = str(
                subprocess.check_output("cat /proc/net/wireless", shell=True)
            )
            interface_name = int_name_check[166:172]
        if interface_name == "":
            # interfaceName = Need the code here
            pass
        f = open(INTERFACE_CONF_FILE, "w")
        f.write(interface_name)
        f.close()
        return str(interface_name).strip()
    else:
        f = open(INTERFACE_CONF_FILE, "r")
        interface_name = f.readline()
        f.close()
        return str(interface_name).strip()


def cleanup():
    fcntl.lockf(fp, fcntl.LOCK_UN)
    fp.close()
    os.unlink(PID_FILE)
    try:
        os.unlink(SCAN_FILE)
        os.unlink(PREF_FILE)
        os.unlink(INTERFACE_CONF_FILE)
    except:
        pass


if __name__ == "__main__":
    NetGUI()
    Gtk.main()
