#!/usr/bin/python

from distutils.core import setup

setup(
    name="netgui",
    version="0.86",
    description="More advanced GUI for NetCTL. Replaces WiFiz.",
    author="Cody Dostal <netgui@codydostal.net>, Gregory Mullen <greg@grayhatter.com>",
    url="https://github.com/codywd/netgui",
    license="Custom MIT (see NetGUI.license)",
    py_modules=["main"],
    #'runner' is in the root.
    scripts=["scripts/netgui"],
    data_files=[
        ("/usr/share/netgui/", ["main.py", "UI.glade"]),
        ("/usr/share/licenses/netgui", ["NetGUI.license"]),
        (
            "/usr/share/netgui/imgs",
            [
                "imgs/APScan.png",
                "imgs/connect.png",
                "imgs/exit.png",
                "imgs/newprofile.png",
                "imgs/aboutLogo.png",
                "imgs/disconnect.png",
                "imgs/logo.png",
                "imgs/preferences.png",
            ],
        ),
        (
            "/usr/share/netgui/Library",
            [
                "Library/__init__.py",
                "Library/generate_config.py",
                "Library/interface_control.py",
                "Library/netctl_functions.py",
                "Library/notifications.py",
                "Library/preferences.py",
                "Library/profile_editor.py",
                "Library/run_as_root.py",
                "Library/scanning.py",
            ],
        ),
        ("/usr/share/applications", ["scripts/netgui.desktop"]),
    ],
)
