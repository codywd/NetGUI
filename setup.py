#!/usr/bin/python2

from distutils.core import setup

setup(name='netgui',
<<<<<<< HEAD
      version='0.8',
=======
      version='0.7.1',
>>>>>>> 0.7.1
    description = "More advanced GUI for NetCTL. Replaces WiFiz.",
    author = "Cody Dostal <dostalcody@gmail.com>, Gregory Mullen <greg@grayhatter.com>",
    url = "https://github.com/codywd/netgui",
    license = "Custom MIT (see NetGUI.license)",
    py_modules=['main'],
    #'runner' is in the root.
    scripts = ['scripts/netgui'],
    data_files=[
    ('/usr/share/netgui/',
        ['main.py',
        'UI.glade',
        'imgs/APScan.png',
        'imgs/connect.png',
        'imgs/exit.png',
        'imgs/newprofile.png',
        'imgs/aboutLogo.png',
        'imgs/disconnect.png',
        'imgs/logo.png',
        'imgs/preferences.png' ]),
    ('/usr/share/licenses/netgui',
        ['NetGUI.license'])
])
