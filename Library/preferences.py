# Import Standard Libraries
import json
import os
from pathlib import Path
import sys

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib, GtkSource

class Preferences(Gtk.Window):
    def __init__(self, program_loc):
        # Init Vars
        self.pref_file = Path("/", "var", "lib", "netgui", "preferences.json")
        self.builder = Gtk.Builder()
        self.program_loc = program_loc
        self.status_dir = Path("/", "var", "lib", "netgui")
        self.init_ui()

    def init_ui(self):
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(str(Path(self.program_loc, "UI.glade")))

        # Get everything we need from UI.glade
        go = self.builder.get_object
        self.preferences_dialog = go("prefDialog")
        save_button = go("saveButton")
        cancel_button = go("cancelButton")
        self.interface_entry = go("wiInterface")
        self.default_profile = go("defaultProfilePath")
        self.unsecure_switch = go("unsecureSwitch")
        self.autoconnect_switch = go("autoconnectSwitch")
        self.notification_type = go("notification_type")
        filechooser = go("chooseDefaultProfile")

        # Connecting the "clicked" signals of each button to the relevant function.
        save_button.connect("clicked", self.save_clicked)
        cancel_button.connect("clicked", self.cancel_clicked)
        self.preferences_dialog.connect("show", self.on_load)
        filechooser.connect("clicked", self.choose_profile)
        # Opening the Preferences Dialog.
        self.preferences_dialog.run()

    def cancel_clicked(self, e):
        self.preferences_dialog.hide()

    def choose_profile(self, e):
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

    def save_clicked(self, e):
        new_int = self.interface_entry.get_text()
        with open(Path(self.status_dir, "interface.cfg"), 'w+') as interface_file:
            interface_file.write(new_int)

        json_prefs = {
            "default_profile": self.default_profile.get_text(),
            "unsecure_status": self.unsecure_switch.get_active(),
            "autoconnect": self.autoconnect_switch.get_active(),
            "notification_type": self.notification_type.get_active_text()
        }

        with open(self.pref_file, 'w+') as outfile:
            json.dump(json_prefs, outfile)

        self.preferences_dialog.destroy()

    def on_load(self, e):
        f = open(Path(self.status_dir, "interface.cfg"), 'r+')
        data = json.load(open(self.pref_file))
        self.interface_entry.set_text(str(f.read()))

        self.default_profile.set_text(data["default_profile"])
        self.unsecure_switch.set_active(data["unsecure_status"])
        self.autoconnect_switch.set_active(data["autoconnect"])
        if "Center" in data["notification_type"]:
            self.notification_type.set_active_id("1")
        elif "Message" in data["notification_type"]:
            self.notification_type.set_active_id("2")
        elif "Terminal" in data["notification_type"]:
            self.notification_type.set_active_id("3")

        f.close()