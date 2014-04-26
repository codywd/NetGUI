#! /usr/bin/python3

# Import Standard Libraries
import fcntl, os, re, sys, time
import subprocess
import threading
import multiprocessing
# import webbrowser

# Import Third Party Libraries
from gi.repository import Gtk, Gdk, GObject, GLib
from gi.repository import Notify

# Setting base app information, such as version, and configuration 
# directories/files.

if os.path.dirname(os.path.realpath(__file__)) is not '/usr/share/netgui':
    # We'll store logs here instead
    status_directiory = os.path.dirname(os.path.realpath(__file__))
    config_directiory = os.getcwd()
else:
    status_directiory = '/usr/share/netgui'
    config_directiory = "/etc/netctl"
    if not os.path.exists(status_directiory):
        if not subprocess.call("mkdir -p " + status_directiory, shell=True):
            print("couldn't get a working directory")
            sys.exit(2)


program_version   = "0.65"
program_location  = os.path.dirname(os.path.realpath(__file__))
profile_prefix    = "/netgui_"
preferences_file  = status_directiory + "/preferences.cfg"
interface_file    = status_directiory + "/interface.cfg"
iwconfig_file     = status_directiory + "/iwlist.log"
iwlist_file       = status_directiory + "/iwlist.log"
wpa_cli_file      = status_directiory + "/wpa_cli.log"
pid_file          = status_directiory + "/netgui.pid"
imgs_directiory   = "/usr/share/netgui/imgs"
license_directory = '/usr/share/licenses/netgui'
pid_number        = os.getpid()

# Allows for command line arguments. Currently only a "Help" argument, 
# but more to come.
# TODO import ext libary to handel this for us
for arg in sys.argv:
    if arg == '--help' or arg == '-h':
        print("netgui The NetCTL GUI!\nNot very helpful we know, comming soon?")
        sys.exit(0)
    if arg == '--version' or arg == '-v':
        print("Your netgui version is " + program_version + ".")
        sys.exit(0)



# Let's make sure we're root, while at it.
euid = os.geteuid()
if euid != 0:
    print("netgui requries root to run.\nPlease sudo or su -c and try again.")
    sys.exit(77)

# Let's also not allow any more than one instance of netgui.
# Note that the builtin open will truncate the file even if it's already locked.
# We must use os.open to avoid the behavior and truncate it later.
fp = os.fdopen(os.open(pid_file, os.O_CREAT | os.O_WRONLY), 'w')
try:
    fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("We only allow one instance of netgui to be running at a time for precautionary reasons.")
    sys.exit(1)

fp.truncate()
fp.write(str(pid_number)+"\n")
fp.flush()

# The main class of netgui. Nifty name, eh?
class netgui(Gtk.Window):
    # AFAIK, I need __init__ to call InitUI right off the bat. I may be wrong, but it works.
    def __init__(self):
        self.InitUI()

    # Since I LOVE everything to be organized, I use a separate InitUI function so it's clean.
    def InitUI(self):
        
        # Create a "Builder", which basically allows me to import the Glade file for a complete interface.
        # I love Glade, btw. So much quicker than manually coding everything.
        self.builder = Gtk.Builder()
        self.builder.add_from_file(program_location + "/UI.glade")

        # Init Vars
        self.scanning = False
        self.APindex = 0
        self.p = None

        # Grab the "window1" attribute from UI.glade, and set it to show everything.
        window = self.builder.get_object("mainWindow")
        window.connect("delete-event", self.onExit)

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
        network_columns = ["ESSID","Strength","Encryption","Status"]
        for i in range(len(network_columns)):
            CellRenderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(network_columns[i], CellRenderer, text=i)
            column.set_resizable(True)
            self.APList.append_column(column)

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
        menu = self.builder.get_object("menubar1")
        profileMenu = self.builder.get_object("profilesMenu")
        profileMenu.set_submenu(Gtk.Menu())
        profiles = os.listdir(config_directiory)
        # Iterate through profiles directory, and add to "Profiles" Menu #
        for i in profiles:
            if os.path.isfile(config_directiory + i):
                profile = profileMenu.get_submenu().append(Gtk.MenuItem(label=i))   
        # This should automatically detect their wireless device name. I'm not 100% sure
        # if it works on every computer, but we can only know from multiple tests. If
        # it doesn't work, I will re-implement the old way.
        # Notify.init("NetGUI")

        self.interfaceName = GetInterface()
        if self.interfaceName == "":
            # n = Notify.Notification.new("Could not detect interface!", "No interface was detected. Now running in No-Wifi Mode. Scan Button is disabled.", "dialog-information")
            # n.show()
            self.NoWifiScan(None)
            self.NoWifiMode = 1
            ScanButton.props.sensitive = False
        else:
            self.startScan(None)
            self.NoWifiMode = 0

        # Start initial scan
        window.show_all()

    def NoWifiScan(self, e):
        '''Disables wifi scanning for wired connections'''
        aps = {}
        profiles = os.listdir(config_directiory)
        i = 0
        NoWifiMode = 1
        for profile in profiles:
            if os.path.isfile(config_directiory + profile):
                aps["row" + str(i)] = self.APStore.append([profile, 
                    "N/A in No-Wifi mode.", "N/A", "N/A"])

    def onExit(self, widget=None, event=None, data=None):
        '''kills main()'''
        if self.p == None:
            pass
        else:
            self.p.terminate()
        Gtk.main_quit()
        return True

    # This class is only here to actually start running all the code in "onScan" in a separate process.
    def startScan(self, e):
        '''call the scanning functions'''
        self.p = multiprocessing.Process(target=self.onScan)
        self.p.start()
        self.p.join()
        self.refresh_APlist()

    def onScan(self, e=None):
        with open(wpa_cli_file, 'w') as f:
            InterfaceCtl.up(self, self.interfaceName)
            subprocess.call(["wpa_cli", "scan"])
            output=CheckOutput(self, "wpa_cli scan_results")
            f.write(output)

    def refresh_APlist(self):
        '''get results of the scan... I think...'''
        self.APStore.clear()
        current_bssid = self.network_status('bssid')
        with open(wpa_cli_file, 'r') as seenAPs:
            APList = []
            for row in seenAPs:
                APList.append(row.split('\t',4))
            for AP in APList:
                # bssid / freq / power / opts / essid
                if len(AP) < 4:
                    continue
                essid = AP[4]
                if essid is ('' or '\n'):
                    essid = AP[0]
                power = str(((int(AP[2])*2)+200))+'%'
                opts = AP[3].strip('[]').replace('][', ' and ').rstrip(' and ESS')
                if current_bssid:
                    if current_bssid == AP[0]:
                        connected = 'Yes'
                    else:
                        connected = 'No'
                else:
                    connected = "unknown"
                self.APStore.append([essid, power, opts, connected])
        return True

    def network_status(self, req=None):
        status = subprocess.check_output(['wpa_cli', 'status']).decode("utf-8")
        if req is None:
            return status
        else:
            result = status.split('\n')
            for line in result:
                line = line.split('=',1)
                if line[0] == req:
                    return line[1]
        return False

    def connectClicked(self, menuItem):
        '''process a connection request from the user'''
        if self.NoWifiMode == 0:
            select = self.APList.get_selection()
            networkSSID = self.getSSID(select)
            profile = SSIDToProfileName(networkSSID)
            netinterface = GetInterface()
            if os.path.isfile(config_directiory + profile):
                network_interface.down(status_directiory, netinterface)
                NetCTL.stopall(self)
                NetCTL.start(self, profile)
                n = Notify.Notification.new("Connected to new network!", "You are now connected to " + networkSSID, "dialog-information")
                n.show()
            else:
                networkSecurity = self.getSecurity(select)
                key = get_network_pw(self, "Please enter network password", "Network Password Required.")
                CreateConfig(networkSSID, self.interfaceName, networkSecurity, key)
                try:
                    network_interface.down(self, netinterface)
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
                network_interface.down(self, netinterface)
                NetCTL.stopall(self)
                NetCTL.start(self, NWMprofile)
                n = Notify.Notification.new("Connected to new profile!", "You are now connected to " + NWMprofile, "dialog-information")
                n.show()
            except:    
                n = Notify.Notification.new("Error!", "There was an error. Please report an issue at the github page if it persists.", "dialog-information")
                n.show()
                Notify.uninit()   
        self.refresh_APlist()

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
        network_interface.down(self, interfaceName)
        self.startScan(None)
        n = Notify.Notification.new("Disconnected from network!", "You are now disconnected from " + networkSSID, "dialog-information")
        n.show()        

    def prefClicked(self, menuItem):
        # Setting up the cancel function here fixes a wierd bug where, if outside of the prefClicked function
        # it causes an extra button click for each time the dialog is hidden. The reason we hide the dialog
        # and not destroy it, is it causes another bug where the dialog becomes a small little
        # titlebar box. I don't know how to fix either besides this.
        def OnLoad(self):
            f = open(interface_file, 'r')
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
            # print("Cancel Clicked.")
            preferencesDialog.hide()

        # Setting up the saveClicked function within the prefClicked function just because it looks cleaner
        # and because it makes the program flow more, IMHO
        def saveClicked(self):
            with open(interface_file, 'r+') as f:
                interface = f.read()
                new_interface = interfaceEntry.get_text()
                if new_interface is not interface:
                    GetInterface(new_interface)
            preferencesDialog.hide()

        def CloseClicked(self, gtkevent):
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
        preferencesDialog.connect("delete-event", CloseClicked)

        # Opening the Preferences Dialog.
        preferencesDialog.run()

    def helpClicked(self, menuItem):
        # For some reason, anything besides subprocess.Popen
        # causes an error on exiting out of yelp...
        subprocess.Popen("yelp")

    def reportIssue(self, menuItem):
        # Why would I need a local way of reporting issues when I can use github? Exactly.
        # And since no more dependencies are caused by this, I have no problems with it.
        pass
        # webbrowser.open("https://github.com/codywd/NetGUI/issues")
        # disabled, don't open a webbrowser as root, WTF?

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

class network_interface:
    '''Control the network interface, a.k.a wlan0 or eth0 etc...'''
    def __init__(self, interface=None):
        if interface:
            self.interface = interface
            self.state = self.status()
        else:
            self.state = None
            self.interface = None

    def down(self, interface=None):
        '''put interface down'''
        if not interface:
            interface = self.interface
        subprocess.call(["ip", "link", "set", "down", "dev", interface])

    def up(self, interface=None):
        '''bring interface up'''
        if not interface:
            interface = self.interface
        subprocess.call(["ip", "link", "set", "up", "dev", interface])

    def status(self, interface=None, guess=None):
        '''get the current status of interface'''
        if not interface:
            interface = self.interface

        ip_link = subprocess.check_output(["ip", "link", "show", interface])
        ip_link = ip_link.decode("utf-8")
        if 'state UP' in ip_link:
            state = True
        elif 'state DOWN' in ip_link:
            state = False
        else:
            state = 'unknown'
        if guess is not None:
            if self.interface is not None:
                self.state = state
            return state
        else:
            if guess == state:
                return True
            else:
                return False
        try:
            pass
        except:
            raise 'Unhandled event in network_interface.status'
            print('unknown network status')
            sys.exit(9)

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
    f = open(config_directiory + filename, 'w')
    f.write("status_directiory='This profile was generated by netgui for " + str(ssid)+".'\n" +
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

def GetInterface(setit = None):
    if setit is not None:
        with open(interface_file, 'w') as f:
            f.write(setit)
            f.flush()
        return setit
    elif os.path.isfile(interface_file) is not True:
        devices = os.listdir("/sys/class/net")
        for device in devices:
            if device.startswith('wl'):
                interface = device
        if not interface:
            interface = get_network_pw(self, "We could not automatically "+\
                "detect your wireless interface. Please type it here. Leave "+\
                "blank for NoWifiMode.", "Network Interface Required.")
        with open(interface_file, 'w') as f:
            f.write(interface)
            f.flush()
        return interface.strip()
    else:
        with open(interface_file, 'r') as f:
            interface = f.read()
        return interface.strip()


def cleanup():
    # Clean up time
    try:
        os.unlink(iwlist_file)
        os.unlink(iwconfig_file)
    except:
        pass
    # To avoid race condition, we should unlink pid_file before unlock
    os.unlink(pid_file)
    fcntl.lockf(fp, fcntl.LOCK_UN)
    fp.close()

if __name__ == "__main__":
    try:
        Gdk.threads_init()
        Gdk.threads_enter()
        netgui()
        Gdk.threads_leave()
        Gtk.main()
    except Exception as e:
        print(e)
    finally:
        cleanup()