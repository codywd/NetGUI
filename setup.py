#!/usr/bin/python2

from distutils.core import setup

setup(name='netgui',
      version='0.7.2',
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
        'UI.glade']),
    ('/usr/share/licenses/netgui',
        ['NetGUI.license']),
    ('/usr/share/negui/imgs',
        ['APScan.png',
         'connect.png',
         'exit.png',
         'newprofile.png',
         'aboutLogo.png',
         'disconnect.png',
         'logo.png',
         'preferences.png'])

])
