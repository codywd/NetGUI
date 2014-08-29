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
import netgui

try:
    d = open(status_dir + "profile_to_edit", 'r')
    profile_to_edit = d.readline()
    if profile_to_edit != "":
        print(profile_to_edit)
        if profile_to_edit != None:
            print(profile_to_edit)
            profile_to_edit = profile_to_edit
        else:
            profile_to_edit = None
    else:
        profile_to_edit = None
    d.close()
except Exception as e:
    print(e)
    profile_to_edit = None


class NetGUIProfileEditor(Gtk.Window):
    def __init__(self):
        # Init Vars
        self.scanning = False
        self.APindex = 0
        self.p = None
        self.builder = Gtk.Builder()
        self.InitUI()

    def InitUI(self):
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(program_loc + "UI.glade")

        go = self.builder.get_object
        profileEditor = go("profileEditor")
        menuProfExit = go("exitProfWin")
        saveBtn = go("saveMenuProf")
        saveToolBtn = go("saveToolBtn")
        openToolBtn = go("openToolBtn")
        clearBtn = go("clearToolBtn")
        attributesBtn = go("attributesToolBtn")
        exitProfBtn = go("exitToolBtn")
        self.netctlEditor = go("profileEditorView")
        self.buffer = go("textbuffer1")

        # Connecting the "clicked" signals of each button to the relevant function.
        saveBtn.connect("activate", self.saveClicked)
        saveToolBtn.connect("clicked", self.saveClicked)
        attributesBtn.connect("clicked", self.attributesClicked)
        clearBtn.connect("clicked", self.clearClicked)
        profileEditor.connect("show", self.OnLoad)
        exitProfBtn.connect("clicked", self.exitProfClicked)
        menuProfExit.connect("activate", self.exitProfClicked)
        openToolBtn.connect("clicked", self.openClicked)
        # Opening the Prefereces Dialog.
        profileEditor.show_all()

    def openClicked(self, e):
        pass

    def saveClicked(self, e):
        pass

    def attributesClicked(self, e):
        pass

    def clearClicked(self, e):
        pass

    def OnLoad(self, e):
        try:
            txt=open(profile_to_edit).read()
        except:
            return False
        self.buffer.set_text(txt)
        self.buffer.set_data('filename', profile_to_edit)
        self.buffer.set_modified(False)
        self.buffer.place_cursor(self.buffer.get_start_iter())
        return True

    def exitProfClicked(self, e):
        sys.exit()


if __name__ == "__main__":
    NetGUIProfileEditor()
    Gtk.main()