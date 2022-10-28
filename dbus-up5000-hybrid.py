#!/usr/bin/env python3

"""
"""
from gi.repository import GLib
import platform
import logging
import sys
import os, time
import dbus.service

sys.path.insert(1, os.path.join(os.path.dirname(__file__), './ext'))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), './ext/velib_python'))
from vedbus import VeDbusService
from dbusmonitor import DbusMonitor
from ve_utils import exit_on_error
from UPower import UPower            # xxx use own methods...

# UP5000 Modbus registers
RegACVol = 0x3521
RegACCur = 0x3522
RegPVYield = 0x3557

RegPVVol = 0x3549
RegPVCur = 0x354a

# battery voltage
RegBAVol = 0x351d

class UP5000(object):

    def __init__(self, dev, connection='UP5000'):

        servicenameCharger=f'com.victronenergy.solarcharger.{dev}'
        # servicenameInverter=f'com.victronenergy.inverter.{dev}'
        # servicenameInverter=f'com.victronenergy.multi.{dev}'
        servicenameInverter=f'com.victronenergy.vebus.{dev}'

        logging.debug("Opening serial interface xxx for modbus...")
        self.up = UPower(device="/dev/" + dev)
        if self.up.connect() < 0:
            logging.warning("Cant open rs485 interface /dev/{dev}, exiting")
            sys.exit(0)

        logging.debug("Reading initial values to test connection...")
        pvvol = self.up.readReg(RegPVVol)
        pvcur = self.up.readReg(RegPVCur)
        acvol = self.up.readReg(RegACVol)
        accur = self.up.readReg(RegACCur)
        if pvvol == -2 and pvcur == -2 and acvol == -2 and accur == -2:
            sys.exit(0)

        logging.debug("Service %s and %s starting... " % (servicenameCharger, servicenameInverter))

        dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
        # register = { '/Dc/0/Voltage': dummy, '/Dc/0/Current': dummy } 
        dbus_tree= {
                # 'com.victronenergy.battery': register,
                }

        self._dbusmonitor = DbusMonitor(dbus_tree)

	# Get dynamic servicename for serial-battery
        # serviceList = self._get_service_having_lowest_instance('com.victronenergy.battery')
        # if not serviceList:
            # # Restart process
            # logging.info("service com.victronenergy.battery not registered yet, exiting...")
            # sys.exit(0)
        # self.batt_service = serviceList[0]
        # logging.info("service of battery: " +  self.batt_service)

        self._dbusserviceCharger = VeDbusService(servicenameCharger, bus=dbus.bus.BusConnection.__new__(dbus.bus.BusConnection, dbus.bus.BusConnection.TYPE_SYSTEM))
        self._dbusserviceInverter = VeDbusService(servicenameInverter, bus=dbus.bus.BusConnection.__new__(dbus.bus.BusConnection, dbus.bus.BusConnection.TYPE_SYSTEM))

        self.createManagementPaths(self._dbusserviceCharger, "Manne Spezial Lader", connection)
        self.createManagementPaths(self._dbusserviceInverter, "Manne Spezial Inverter", connection)

        # PVcharger
        self._dbusserviceCharger.add_path('/Dc/0/Voltage', 0)
        self._dbusserviceCharger.add_path('/Dc/0/Current', 0)
        self._dbusserviceCharger.add_path('/Pv/0/V', 0)
        self._dbusserviceCharger.add_path('/Pv/0/P', 0)
        self._dbusserviceCharger.add_path('/Load/I', 0)
        self._dbusserviceCharger.add_path('/Mode', 0)
        self._dbusserviceCharger.add_path('/NrOfTrackers', 0)
        self._dbusserviceCharger.add_path('/Yield/Power', 0)
        self._dbusserviceCharger.add_path('/Yield/System', 0)
        self._dbusserviceCharger.add_path('/Yield/User', 0)

        self._dbusserviceCharger['/Dc/0/Voltage'] = 0
        self._dbusserviceCharger['/Dc/0/Current'] = 0
        self._dbusserviceCharger['/Load/I'] = 0 # 0
        self._dbusserviceCharger['/Mode'] = 1 # on
        self._dbusserviceCharger['/NrOfTrackers'] = 1
        self._dbusserviceCharger['/Pv/0/V'] = 0
        self._dbusserviceCharger['/Pv/0/P'] = 0
        self._dbusserviceCharger['/Yield/Power'] = 0
        self._dbusserviceCharger['/Yield/System'] = 0
        self._dbusserviceCharger['/Yield/User'] = 0

        # Inverter
        """
        self._dbusserviceInverter.add_path('/Dc/0/Voltage', 0)
        self._dbusserviceInverter.add_path('/Dc/0/Current', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/V', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/I', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/P', 0)

        self._dbusserviceInverter['/Dc/0/Voltage'] = 2
        self._dbusserviceInverter['/Dc/0/Current'] = 1
        self._dbusserviceInverter['/Ac/Out/L1/V'] = 2
        self._dbusserviceInverter['/Ac/Out/L1/I'] = 1
        self._dbusserviceInverter['/Ac/Out/L1/P'] = 2
        """

        # '/Ac/ActiveIn/ActiveInput': dummy,
        # '/Ac/In/2/Type': dummy,
        # '/Ac/In/2/L1/P': dummy,
        # '/Yield/Power': dummy,
        # '/Soc': dummy},

        """
        '/Ac/ActiveIn/ActiveInput': dummy,
        '/Ac/ActiveIn/L1/P': dummy,
        '/Ac/ActiveIn/L2/P': dummy,
        '/Ac/ActiveIn/L3/P': dummy,
        '/Ac/Out/L1/P': dummy,
        '/Ac/Out/L2/P': dummy,
        '/Ac/Out/L3/P': dummy,
        '/Mode': dummy,
        '/State': dummy,
        '/Dc/0/Voltage': dummy,
        '/Dc/0/Current': dummy,
        '/Dc/0/Power': dummy,
        '/Soc': dummy},
        """

        self._dbusserviceInverter.add_path('/Dc/0/Voltage', 0)
        self._dbusserviceInverter.add_path('/Dc/0/Current', 0)

        self._dbusserviceInverter.add_path('/Ac/Out/L1/V', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/I', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/P', 0)
        self._dbusserviceInverter.add_path('/Ac/Out/L1/F', 0)

        self._dbusserviceInverter.add_path('/Ac/ActiveIn/ActiveInput', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/Connected', 0)
        # self._dbusserviceInverter.add_path('/Ac/In/1/Type', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/P', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/V', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/I', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/F', 0)

        self._dbusserviceInverter.add_path('/Mode', 0)
        self._dbusserviceInverter.add_path('/State', 0)

        self._dbusserviceInverter['/Dc/0/Voltage'] = 0
        self._dbusserviceInverter['/Dc/0/Current'] = 0

        self._dbusserviceInverter['/Ac/Out/L1/V'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/I'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/P'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/F'] = 44 # xxx

        self._dbusserviceInverter['/Ac/ActiveIn/ActiveInput'] = 0
        self._dbusserviceInverter['/Ac/ActiveIn/Connected'] = 1
        # self._dbusserviceInverter['/Ac/In/1/Type'] = 1
        self._dbusserviceInverter['/Ac/ActiveIn/L1/P'] = 23
        self._dbusserviceInverter['/Ac/ActiveIn/L1/V'] = 230 # xxx not used?
        self._dbusserviceInverter['/Ac/ActiveIn/L1/I'] = 0.1 # xxx not used?
        self._dbusserviceInverter['/Ac/ActiveIn/L1/F'] = 33 # xxx not used?

        self._dbusserviceInverter['/Mode'] = 3 # on
        self._dbusserviceInverter['/State'] =  9 # inverting

        # Grid input
        # self._dbusservice.add_path('/A/CloseFile', 0, description="Request to close file", writeable=True, onchangecallback=self.closeRequest)

        # self._dbusservice['/A/FileOpened'] = 1
        # self._dbusservice['/A/CloseFile'] = 0

        self.update()

        GLib.timeout_add(5000, exit_on_error, self.update)

    def createManagementPaths(self, dbusservice, productname, connection):

        # Create the management objects, as specified in the ccgx dbus-api document
        dbusservice.add_path('/Mgmt/ProcessName', __file__)
        dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        dbusservice.add_path('/DeviceInstance', 1) # deviceinstance)
        dbusservice.add_path('/ProductId', 0)
        dbusservice.add_path('/ProductName', productname)
        dbusservice.add_path('/FirmwareVersion', 0)
        dbusservice.add_path('/HardwareVersion', 0)
        dbusservice.add_path('/Connected', 1)

    def update(self):

        logging.info('update...')

        pvvol = self.up.readReg(RegPVVol)
        pvcur = self.up.readReg(RegPVCur)
        pvpow = pvvol * pvcur

        acvol = self.up.readReg(RegACVol)
        accur = self.up.readReg(RegACCur)
        acpow = acvol * accur

        bavol = self.up.readReg(0x351d)

        pvyield = self.up.readReg(RegPVYield)
        
        logging.info("PV power: %f (%f * %f)" % (pvpow, pvvol, pvcur))
        logging.info("AC power: %f (%f * %f)" % (acpow, acvol, accur))

        self._dbusserviceCharger['/Dc/0/Voltage'] = pvvol
        self._dbusserviceCharger['/Dc/0/Current'] = pvcur
        self._dbusserviceCharger['/Load/I'] = 0
        self._dbusserviceCharger['/Pv/0/V'] = pvvol
        self._dbusserviceCharger['/Pv/0/P'] = pvpow
        self._dbusserviceCharger['/Yield/Power'] = pvpow
        self._dbusserviceCharger['/Yield/System'] = pvyield
        self._dbusserviceCharger['/Yield/User'] = pvyield

        self._dbusserviceInverter['/Dc/0/Voltage'] = bavol
        self._dbusserviceInverter['/Dc/0/Current'] = -acpow/bavol # negative, inverter is discharging the batterie

        self._dbusserviceInverter['/Ac/Out/L1/V'] = acvol
        self._dbusserviceInverter['/Ac/Out/L1/I'] = accur
        self._dbusserviceInverter['/Ac/Out/L1/P'] = acpow

        return True

    """
    # returns a tuple (servicename, instance)
    def _get_service_having_lowest_instance(self, classfilter=None): 
        services = self._get_connected_service_list(classfilter=classfilter)
        if len(services) == 0: return None
        s = sorted((value, key) for (key, value) in services.items())
        return (s[0][1], s[0][0])

    def _get_connected_service_list(self, classfilter=None):
        services = self._dbusmonitor.get_service_list(classfilter=classfilter)
        # self._remove_unconnected_services(services)
        return services
    """

# === All code below is to simply run it from the commandline for debugging purposes ===

# It will created a dbus service called com.victronenergy.pvinverter.output.
# To try this on commandline, start this program in one terminal, and try these commands
# from another terminal:
# dbus com.victronenergy.pvinverter.output
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward GetValue
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward SetValue %20
#
# Above examples use this dbus client: http://code.google.com/p/dbus-tools/wiki/DBusCli
# See their manual to explain the % in %20

def main():

    format = "%(asctime)s %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=logging.DEBUG, format=format, datefmt="%d.%m.%y_%X_%Z")

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    up5000 = UP5000( dev = sys.argv[1] )

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()

    mainloop.run()


if __name__ == "__main__":
    main()


