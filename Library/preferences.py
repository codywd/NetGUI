# Import Standard Libraries
import csv
import fcntl
import fileinput
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser

# Setting base app information, such as version, and configuration directories/files.
profile_dir = "/etc/netctl/"
#program_loc = "/usr/share/netgui/"
program_loc = "./"
status_dir = "/var/lib/netgui/"

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib, GtkSource

class Preferences(Gtk.Window):
    def __init__(self):
        # Init Vars
        self.pref_file = pref_file = Path("/", "var", "lib", "netgui", "preferences.cfg")
        self.builder = Gtk.Builder()
        self.init_ui()

    def init_ui(self):
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(program_loc + "UI.glade")

        # Get everything we need from UI.glade
        go = self.builder.get_object
        self.preferences_dialog = go("prefDialog")
        save_button = go("saveButton")
        cancel_button = go("cancelButton")
        self.interface_entry = go("wiInterface")
        self.default_profile = go("defaultProfilePath")
        self.unsecure_switch = go("unsecureSwitch")
        self.autoconnect_switch = go("autoconnectSwitch")
        self.notification_type = go("self.notification_type")
        filechooser = go("chooseDefaultProfile")

        # Connecting the "clicked" signals of each button to the relevant function.
        save_button.connect("clicked", self.save_clicked)
        cancel_button.connect("clicked", self.cancel_clicked)
        self.preferences_dialog.connect("show", self.on_load)
        filechooser.connect("clicked", self.choose_profile)
        # Opening the Preferences Dialog.
        self.preferences_dialog.run()

    def cancel_clicked(self):
        self.preferences_dialog.hide()

    def choose_profile(self):
        dialog = Gtk.FileChooserDialog("Choose your default profile.", None,
                                        Gtk.FileChooserAction.OPEN,
                                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        dialog.set_current_folder("/etc/netctl")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.default_profile.set_text(dialog.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            print("Cancel clicked")

        dialog.destroy()

    # Setting up the saveClicked function within the prefClicked function just because it looks cleaner
    # and because it makes the program flow more, IMHO
    def save_clicked(self, e):
        f = open(status_dir + "interface.cfg", 'w+')
        d = open(self.pref_file, 'r+')
        cur_int = f.read()
        f.close()
        new_int = self.interface_entry.get_text()
        if new_int != cur_int:
            for line in fileinput.input(status_dir + "interface.cfg", inplace=True):
                print(new_int)

        if self.default_profile != "" or None:
            d.write("Default Profile: " + self.default_profile.get_text() + "\n")

        if self.unsecure_switch.get_active() is True:
            d.write("Unsecure Status: Yes\n")
        else:
            d.write("Unsecure Status: No\n")

        if self.autoconnect_switch.get_active() is True:
            d.write("Autoconnect Status: Yes\n")
        else:
            d.write("Autoconnect Status: No\n")

        nt = self.notification_type.get_active_text()
        d.write("NoteType: " + nt + "\n")
        d.close()
        self.preferences_dialog.hide()

    def on_load(self):
        f = open(status_dir + "interface.cfg", 'r+')
        d = open(self.pref_file, 'r+')
        self.interface_entry.set_text(str(f.read()))
        for line in d:
            if "Default Profile:" in line:
                self.default_profile.set_text(str(line)[17:])
            if "Unsecure Status:" in line:
                if "No" in line:
                    self.unsecure_switch.set_active(False)
                elif "Yes" in line:
                    self.unsecure_switch.set_active(True)
            if "Autoconnect Status:" in line:
                if "No" in line:
                    self.autoconnect_switch.set_active(False)
                elif "Yes" in line:
                    self.autoconnect_switch.set_active(True)
            if "NoteType:" in line:
                if "Center" in line:
                    self.notification_type.set_active_id("1")
                elif "Message" in line:
                    self.notification_type.set_active_id("2")
                elif "Terminal" in line:
                    self.notification_type.set_active_id("3")
        f.close()
        d.close()

    @staticmethod
    def exit_prof_clicked(self):
        sys.exit()


if __name__ == "__main__":
    Preferences()
    Gtk.main()