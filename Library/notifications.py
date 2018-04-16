import json
from pathlib import Path
from gi.repository import Notify

class Notification():
    def __init__(self):
        preferences_file = Path("/", "var", "lib", "netgui", "preferences.json")

        user_prefs = json.load(open(preferences_file))

        if "Center" in user_prefs["notification_type"]:
            self.notification_type = "NotificationCenter"
            Notify.init("netgui")
        elif "Message" in user_prefs["notification_type"]:
            self.notification_type = "MessageBoxes"
        elif "Terminal" in user_prefs["notification_type"]:
            self.notification_type = "print"

    def show_notification(self, title, message):
        if self.notification_type == "NotificationCenter":
            n = Notify.Notification.new(title, message, "dialog-information")
            n.set_timeout(1000)
            n.show()
        elif self.notification_type == "MessageBoxes":
            pass
        elif self.notification_type == "print":
            print("{}: {}".format(title, message))