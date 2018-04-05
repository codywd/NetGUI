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
profile_dir = "/etc/netctl/"
#program_loc = "/usr/share/netgui/"
program_loc = "./"
status_dir = "/var/lib/netgui/"

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib, GtkSource
from gi.repository import Notify

# Import Personal Files

class NetGUIProfileEditor(Gtk.Window):
    def __init__(self, profile_to_edit):
        # Init Vars
        self.scanning = False
        self.APindex = 0
        self.profile_to_edit = profile_to_edit
        self.builder = Gtk.Builder()
    
    def show(self):
        self.init_ui()

    def init_ui(self):
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(program_loc + "UI.glade")

        go = self.builder.get_object
        self.profile_editor = go("profileEditor")
        menu_prof_exit = go("exitProfWin")
        save_button = go("saveMenuProf")
        save_tool_button = go("saveToolBtn")
        open_tool_button = go("openToolBtn")
        clear_button = go("clearToolBtn")
        attributes_button = go("attributesToolBtn")
        exit_profile_button = go("exitToolBtn")
        self.netctlEditor = go("profileEditorView")
        self.buffer = go("gtksourcebuffer")

        # Connecting the "clicked" signals of each button to the relevant function.
        save_button.connect("activate", self.save_clicked)
        save_tool_button.connect("clicked", self.save_clicked)
        attributes_button.connect("clicked", self.attributes_clicked)
        clear_button.connect("clicked", self.clear_clicked)
        self.profile_editor.connect("show", self.on_load)
        exit_profile_button.connect("clicked", self.exit_prof_clicked)
        menu_prof_exit.connect("activate", self.exit_prof_clicked)
        open_tool_button.connect("clicked", self.open_clicked)
        # Opening the Prefereces Dialog.
        self.profile_editor.show_all()

    def open_clicked(self, e):
        pass

    def save_clicked(self, e):
        pass

    def attributes_clicked(self, e):
        pass

    def clear_clicked(self, e):
        pass

    def on_load(self, e):
        if self.profile_to_edit is None:
            pass
        else:
            try:
                txt=open(self.profile_to_edit, 'r').read()
            except e:
                print(e)
            self.buffer.set_text(txt)
            self.buffer.set_modified(False)
            self.buffer.place_cursor(self.buffer.get_start_iter())

    def exit_prof_clicked(self, e):
        self.profile_editor.hide()
