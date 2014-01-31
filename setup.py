#!/usr/bin/python2

from distutils.core import setup

setup(name='netgui',
      version='0.1.0',
      description = "More advanced GUI for NetCTL. Replaces WiFiz.",
      author = "Cody Dostal <dostalcody@gmail.com>, Gregory Mullen <greg@grayhatter.com>",
      url = "https://bitbucket.org/codywd/netgui/overview",
      license = "Custom MIT (see NetGUI.license)",
      #py_modules=['main'],
      #'runner' is in the root.
      scripts = ['scripts/wifiz'],
      data_files=[('/usr/share/netgui', ['main.py']),
                  ('/usr/share/netgui/imgs/',
        ['imgs/APScan.png', 'imgs/connect.png', 'imgs/exit.png',
        'imgs/newprofile.png', 'imgs/aboutLogo.png', 'imgs/disconnect.png',
        'imgs/logo.png', 'imgs/preferences.png' ]),
                  ('/usr/share/licenses/netgui',['NetGUI.license'])
                 ]
      )
