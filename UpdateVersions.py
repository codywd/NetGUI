import xml.etree.ElementTree as ET
import fileinput

<<<<<<< HEAD
progVer = "0.8"
=======
progVer = "0.7.1"
>>>>>>> 0.7.1
# Automatic Glade Version Setter, thanks to Dane White
# at the Stack Overflow forums!
class ProgramProperties(object):

    def __init__(self, xmlfile):

        # Parse the XML file
        self.__xmlfile = xmlfile
        self.__xml_tree = ET.parse(xmlfile)
        self.__version_element = self.__xml_tree.getroot().find(".//property[@name='version']")

        # Get an in-memory copy of 'version'
        self.__version = self.__version_element.text

    @property
    def version(self):
        return self.__version

    @version.setter
    def version(self, vers):

        # Avoid unecessary file I/O
        if self.__version != vers:

            # Store in-memory
            self.__version = vers

            # Save the version to the file
            self.__version_element.text = str(vers)
            self.__xml_tree.write(self.__xmlfile)
            
class ModifyOtherVers():
    def __init__(self):
        ModifyOtherVers.updatePkgBuild()
        
    def updatePkgBuild():
        PKGBUILD = ("scripts/PKGBUILD")
        for line in fileinput.input(PKGBUILD, inplace=True):
            if "pkgver=" in line:
                print(line.replace(line, "pkgver=" + str(prog.version)))
            else:
                print(line.strip())
        ModifyOtherVers.updateSetupPy()
                
    def updateSetupPy():
        SetupPy = ("setup.py")
        for line in fileinput.input(SetupPy, inplace=True):
            if "version" in line:
                print(line.replace(line, "      version='" + str(prog.version) + "',"))
            else:
                print(line.rstrip("\n"))
        ModifyOtherVers.updateMainFile()
        
    def updateMainFile():
        mainFile = ("main.py")
        for line in fileinput.input(mainFile, inplace=True):
            if "progVer =" in line:
                print(line.replace(line, 'progVer = "' + prog.version + '"'))
            else:
                print(line.rstrip("\n"))
                
        ModifyOtherVers.UpdateReadme()
                
    def UpdateReadme():
        README = ("README.md")
        for line in fileinput.input(README, inplace=True):
            if "# NetGUI v" in line:
                print(line.replace(line, "# NetGUI v" + prog.version))
            else:
                print(line.rstrip("\n"))

prog = ProgramProperties('UI.glade')
prog.version = progVer
ModifyOtherVers.updatePkgBuild()
