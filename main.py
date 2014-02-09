#! /usr/bin/python3

# Import Standard Libraries
import csv
import fcntl
import fileinput
import multiprocessing
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib
from gi.repository import Notify

# Setting base app information, such as version, and configuration directories/files.
progVer = "0.65"
conf_dir = "/etc/netctl/"
statusDir = "/usr/lib/netgui/"
progLoc = "/usr/share/netgui/"
profile_prefix = "netgui_"
intFile = statusDir + "interface.cfg"
license_dir = '/usr/share/licenses/netgui/'
iwconfigFile = statusDir + "iwlist.log"
wpacliFile = statusDir + "wpa_cli.log"
iwlistFile = statusDir + "iwlist.log"
pidFile = statusDir + "program.pid"
imgLoc = "/usr/share/netgui/imgs"
prefFile = statusDir + "preferences.cfg"
pidNumber = os.getpid()

# Allows for command line arguments. Currently only a "Help" argument, but more to come.
# TODO import ext libary to handel this for us
for arg in sys.argv:
    if arg == '--help' or arg == '-h':
        print("netgui; The NetCTL GUI! \nWe need root :)")
        sys.exit(0)
    if arg == '--version' or arg == '-v':
        print("Your netgui version is " + progVer + ".")
        sys.exit(0)

if os.path.exists(statusDir):
    pass
else:
    subprocess.call("mkdir " + statusDir, shell=True)

# Let's make sure we're root, while at it.
euid = os.geteuid()
if euid != 0:
    print("netgui NEEDS to be run as root, since many commands we use requires it.\nPlease sudo or su -c and try again.")
    sys.exit(77)

# Let's also not allow any more than one instance of netgui.
# Note that the builtin open will truncate the file even if it's already locked.
# We must use os.open to avoid the behavior and truncate it later.
fp = os.fdopen(os.open(pidFile, os.O_CREAT | os.O_WRONLY), 'w')
try:
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("We only allow one instance of netgui to be running at a time for precautionary reasons.")
    sys.exit(1)

fp.truncate()
fp.write(str(pidNumber)+"\n")
fp.flush()

# The main class of netgui. Nifty name, eh?
class netgui(Gtk.Window):
    # AFAIK, I need __init__ to call InitUI right off the bat. I may be wrong, but it works.
    def __init__(self):
        self.InitUI()

    # Since I LOVE everything to be organized, I use a separate InitUI function so it's clean.
    def InitUI(self):
        IsConnected()
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.
        self.builder = Gtk.Builder()
        self.builder.add_from_file(progLoc + "UI.glade")

        # Init Vars
        self.scanning = False
        self.APindex = 0
        self.p = None

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
        self.APList.append_column(SSIDColumn)

        connectQualityCellRenderer = Gtk.CellRendererText()
        connectQualityColumn = Gtk.TreeViewColumn("Connection Quality", connectQualityCellRenderer, text=1)
        self.APList.append_column(connectQualityColumn)

        securityTypeCellRenderer = Gtk.CellRendererText()
        securityTypeColumn = Gtk.TreeViewColumn("Security Type", securityTypeCellRenderer, text=2)
        self.APList.append_column(securityTypeColumn)

        connectedCellRenderer = Gtk.CellRendererText()
        connectedColumn = Gtk.TreeViewColumn("Connected?", connectedCellRenderer, text=3)
        self.APList.append_column(connectedColumn)

        # Set TreeView as Reorderable
        self.APList.set_reorderable(True)

        # Setting the selection detection. Heh, that rhymes.

        # Set all the handlers I defined in glade to local functions.
        handlers = {
        "onExit": self.onExit,
        "onAboutClicked": self.aboutClicked,
        "onScan": self.startScan,
        "onConnect": self.connectClicked,
        "onDConnect": self.dConnectClicked,
        "onPrefClicked": self.prefClicked,
        "onHelpClicked": self.helpClicked,
        "onIssueReport": self.reportIssue
        }
        # Connect all the above handlers to actually call the functions.
        self.builder.connect_signals(handlers)
        
        # Populate profiles menu
        profileMenu = self.builder.get_object("profilesMenu")
        profiles = os.listdir("/etc/netctl/")
        # Iterate through profiles directory, and add to "Profiles" Menu #
        #for i in profiles:
        #    if os.path.isfile("/etc/netctl/" + i):
        #        profile = profileMenu.set_submenu(i)   
        # This should automatically detect their wireless device name. I'm not 100% sure
        # if it works on every computer, but we can only know from multiple tests. If
        # it doesn't work, I will re-implement the old way.
        Notify.init("NetGUI")
            
        self.interfaceName = GetInterface()
        if self.interfaceName == "":
            n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            n.show()
            self.NoWifiScan(None)
            self.NoWifiMode = 1
            ScanButton.props.sensitive = False
            print(str(self.NoWifiMode))
        else:
            self.startScan(None)
            self.NoWifiMode = 0
            print(str(self.NoWifiMode))

        # Start initial scan
        window.show_all()
        
        
    def NoWifiScan(self, e):
        aps = {}
        profiles = os.listdir("/etc/netctl/")
        i = 0
        NoWifiMode = 1
        for profile in profiles:
            if os.path.isfile("/etc/netctl/" + profile):
                aps["row" + str(i)] = self.APStore.append([profile, "", "", ""])
                self.APStore.set(aps["row" + str(i)], 1, "N/A in No-Wifi mode.")
                self.APStore.set(aps["row" + str(i)], 2, "N/A.")
                self.APStore.set(aps["row" + str(i)], 3, "N/A.")
                i = i + 1
            
    def onExit(self, e):
        if self.p == None:
            pass
        else:
            self.p.terminate()
        Gtk.main_quit()

    # This class is only here to actually start running all the code in "onScan" in a separate process.
    def startScan(self, e):
        self.p = multiprocessing.Process(target=self.onScan)
        self.p.start()
        self.p.join()
        self.checkScan()
        
    def onScan(self, e=None):
        print("Please wait! Now Scanning.")
        wpacliFileHandler = open(wpacliFile, 'w')
        InterfaceCtl.up(self, self.interfaceName)
        subprocess.call(["wpa_cli", "scan"])
        output=CheckOutput(self, "wpa_cli scan_results")
        wpacliFileHandler.write(output)
        wpacliFileHandler.close()
        print("Done Scanning!")
    
    def checkScan(self):
        self.APStore.clear()
        
        with open(wpacliFile, 'r') as tsv:
            r = csv.reader(tsv, dialect='excel-tab')
            next(r)
            next(r)
            aps = {}
            i = 0
            for row in r:                
                network = row[4]            
                if network == "":
                    next(r)
                aps["row" + str(i)] = self.APStore.append([network, "", "", ""])   
                
                quality = row[2]
                if int(quality) <= -100:
                    percent = "0%"
                elif int(quality) >= -50:
                    percent = "100%"
                else:
                    fquality = (2 * (int(quality) + 100))
                    percent = str(fquality) + "%"
                self.APStore.set(aps["row" + str(i)], 1, percent)
                
                security = row[3]
                if "WPA" and "PSK" and not "TKIP" in security:
                    encryption = "WPA2-PSK"
                elif "WPA" and "TKIP" in security:
                    encryption = "WPA2-TKIP"
                elif "OPENSSID" in security:
                    encryption = "Open"
                elif "WEP" in security:
                    encryption = "WEP"
                else:
                    encryption = "Unknown"
                self.APStore.set(aps["row" + str(i)], 2, encryption)
                
                
                if IsConnected() == False:
                    self.APStore.set(aps["row" + str(i)], 3, "No")
                else:
                    connectedNetwork = CheckOutput(self, "netctl list | sed -n 's/^\* //p'").strip()
                    if SSIDToProfileName(network) == connectedNetwork:
                        self.APStore.set(aps["row" + str(i)], 3, "Yes")
                    else:
                        self.APStore.set(aps["row" + str(i)], 3, "No")              
                i=i+1

    def connectClicked(self, menuItem):
        print(str(self.NoWifiMode))
        if self.NoWifiMode == 0:
            select = self.APList.get_selection()
            networkSSID = self.getSSID(select)
            profile = SSIDToProfileName(networkSSID)
            netinterface = GetInterface()
            if os.path.isfile(conf_dir + profile):
                InterfaceCtl.down(self, netinterface)
                NetCTL.stopall(self)
                NetCTL.start(self, profile)
                n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
                n.show()
            else:
                networkSecurity = self.getSecurity(select)
                key = get_network_pw(self, "Please enter network password", "Network Password Required.")
                CreateConfig(networkSSID, self.interfaceName, networkSecurity, key)
                try:
                    InterfaceCtl.down(self, netinterface)
                    NetCTL.stopall(self)
                    NetCTL.start(self, profile)
                    n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
                    n.show()
                    #wx.MessageBox("You are now connected to " +
                    #             str(nameofProfile).strip() + ".", "Connected.")
                except:
                    #wx.MessageBox("There has been an error, please try again. If"
                    #              " it persists, please contact Cody Dostal at "
                    #              "dostalcody@gmail.com.", "Error!")        
                    n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the github page if it persists.", "dialog-information")
                    n.show()
                    Notify.uninit()        
        elif self.NoWifiMode == 1:
            select = self.APList.get_selection()
            NWMprofile = self.getSSID(select)
            netinterface = GetInterface()
            try:
                InterfaceCtl.down(self, netinterface)
                NetCTL.stopall(self)
                NetCTL.start(self, NWMprofile)
                n = Notify.Notification.new("Connected to new profile!", "You are now connected to " + NWMprofile, "dialog-information")
                n.show()
            except:    
                n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the github page if it persists.", "dialog-information")
                n.show()
                Notify.uninit()   
            
    
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

    def dConnectClicked(self, menuItem):
        select = self.APList.get_selection()
        networkSSID = self.getSSID(select)
        profile = SSIDToProfileName(networkSSID)
        interfaceName = GetInterface()
        NetCTL.stop(self, profile)
        InterfaceCtl.down(self, interfaceName)
        self.startScan(None)
        n = Notify.Notification.new("Disconnected from network!", "You are now disconnected from " + networkSSID, "dialog-information")
        n.show()        
        
    def prefClicked(self, menuItem):
        # Setting up the cancel function here fixes a wierd bug where, if outside of the prefClicked function
        # it causes an extra button click for each time the dialog is hidden. The reason we hide the dialog
        # and not destroy it, is it causes another bug where the dialog becomes a small little
        # titlebar box. I don't know how to fix either besides this.
        def OnLoad(self):
            f = open("/usr/lib/netgui/interface.cfg", 'r')
            interfaceEntry.set_text(str(f.read()))
            f.close()
            
        def profBrowseClicked(self):
            dialog = Gtk.FileChooserDialog("Please Choose Your Profile", self,
                                           Gtk.FileChooserAction.OPEN,
                                           (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
            
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                defaultProfName.set_text(dialog.get_filename())
            elif response == Gtk.ResponseType.CANCEL:
                pass
            
            dialog.destroy()
            
        def cancelClicked(self):
            print("Cancel Clicked.")
            preferencesDialog.hide()

        # Setting up the saveClicked function within the prefClicked function just because it looks cleaner
        # and because it makes the program flow more, IMHO
        def saveClicked(self):
            f = open("/usr/lib/netgui/interface.cfg", 'r+')
            curInt = f.read()
            f.close()
            newInt = interfaceEntry.get_text()
            if newInt != curInt:
                for line in fileinput.input("/usr/lib/netgui/interface.cfg", inplace=True):
                    print(newInt)
            preferencesDialog.hide()

        # Get the things we need from UI.glade
        preferencesDialog = self.builder.get_object("prefDialog")
        saveButton = self.builder.get_object("saveButton")
        cancelButton = self.builder.get_object("cancelButton")
        interfaceEntry = self.builder.get_object("wiInterface")
        defaultProfBrowse = self.builder.get_object("fileChooser")
        defaultProfName = self.builder.get_object("defaultProfilePath")
        
        # Connecting the "clicked" signals of each button to the relevant function.
        saveButton.connect("clicked", saveClicked)
        cancelButton.connect("clicked", cancelClicked)
        defaultProfBrowse.connect("clicked", profBrowseClicked)
        preferencesDialog.connect("show", OnLoad)

        # Opening the Preferences Dialog.
        preferencesDialog.run()

    def helpClicked(self, menuItem):
        # For some reason, anything besides subprocess.Popen
        # causes an error on exiting out of yelp...
        subprocess.Popen("yelp")

    def reportIssue(self, menuItem):
        # Why would I need a local way of reporting issues when I can use github? Exactly.
        # And since no more dependencies are caused by this, I have no problems with it.
        webbrowser.open("https://github.com/codywd/NetGUI/issues")

    def aboutClicked(self, menuItem):
        # Getting the about dialog from UI.glade
        aboutDialog = self.builder.get_object("aboutDialog")
        # Opening the about dialog.
        aboutDialog.run()
        # Hiding the about dialog. Read in "prefDialog" for why we hide, not destroy.
        aboutDialog.hide()

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
        print("netctl:: restart" + network)
        subprocess.call(["netctl", "restart", profile])

class InterfaceCtl(object):
    # Control the network interface, a.k.a wlan0 or eth0
    # etc...

    def __init__(self):
        super(InterfaceCtl, self).__init__()

    def down(self, interface):
        print("interface:: down: " + interface)
        subprocess.call(["ip", "link", "set", "down", "dev", interface])

    def up(self, interface):
        print("interface:: up: " + interface)
        subprocess.call(["ip", "link", "set", "up", "dev", interface])

def SSIDToProfileName(ssid):
    return profile_prefix + ssid

def CreateConfig(ssid, interface, security, key, ip='dhcp'):
    print("Creating Profile! Don't interrupt!\n")
    filename = SSIDToProfileName(ssid)
    if 'wpa' in security:
        security = 'wpa'
    elif 'wep' in security:
        security = 'wep'
    else:
        security = 'none'
    f = open(conf_dir + filename, 'w')
    f.write("Description='This profile was generated by netgui for " + str(ssid)+".'\n" +
            "Interface=" + str(interface) + "\n" +
            "Connection=wireless\n" +
            "Security=" + str(security) + "\n" +
            "ESSID='" + str(ssid) + "'\n")
    if key:
        f.write(r"Key='" + key + "'\n")
    else:
        f.write(r'Key=None')
    f.write("\nIP=dhcp\n")
    f.close()
    print("Alright, I have finished making the profile!")

def IsConnected():
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

def get_network_pw(parent, message, title=''):
    # Returns user input as a string or None
    # If user does not input text it returns None, NOT AN EMPTY STRING.
    dialogWindow = Gtk.MessageDialog(parent,
                          Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                          Gtk.MessageType.QUESTION,
                          Gtk.ButtonsType.OK_CANCEL,
                          message)

    dialogWindow.set_title(title)

    dialogBox = dialogWindow.get_content_area()
    userEntry = Gtk.Entry()
    userEntry.set_visibility(False)
    userEntry.set_invisible_char("*")
    userEntry.set_size_request(250,0)
    dialogBox.pack_end(userEntry, False, False, 0)

    dialogWindow.show_all()
    response = dialogWindow.run()
    text = userEntry.get_text() 
    dialogWindow.destroy()
    if (response == Gtk.ResponseType.OK):
        return text
    else:
        return None

def CheckGrep(self, grepCmd):
    # Run a grep command, decode it from bytes to unicode, strip it of spaces,
    # and return it's output.
    p = subprocess.Popen(grepCmd, stdout=subprocess.PIPE, shell=True)
    output = ((p.communicate()[0]).decode("utf-8")).strip()
    return output

def GetInterface():
    if os.path.isfile(intFile) != True:
        
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
            interfaceName = get_network_pw(self, "We could not automatically detect your wireless interface. Please type it here. Leave blank for NoWifiMode.", "Network Interface Required.")
        f = open(intFile, 'w')
        f.write(interfaceName)
        f.close()
        return str(interfaceName).strip()
    else:
        f = open(intFile, 'r')
        interfaceName = f.readline()
        f.close()   
        return str(interfaceName).strip()


def cleanup():
    # Clean up time
    try:
        os.unlink(iwlistFile)
        os.unlink(iwconfigFile)
    except:
        pass
    # To avoid race condition, we should unlink pidFile before unlock
    os.unlink(pidFile)
    fcntl.lockf(fp, fcntl.LOCK_UN)
    fp.close()

if __name__ == "__main__":
    try:
        Gdk.threads_init()
        Gdk.threads_enter()
        netgui()
        Gdk.threads_leave()
        Gtk.main()
    except:
        pass
    finally:
        cleanup()
