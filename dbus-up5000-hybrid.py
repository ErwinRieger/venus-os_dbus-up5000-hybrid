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

# problem mit 32 bit long werten: diese werden als 2 16 bit worte übertragen
# die jeweils mit 100 skaliert sind.
# wertebereich eines wortes: 0xffff/100 = 655.35
#
#
# long signed problematik: es gibt nur einen (long) wert der vorzeichenbehaftet ist,
# und das ist der batt. strom B129/B130. Dort reicht es aber aus, nur das low-wort zu
# beachten, da ein wertebereich von +/- 327.x A reichen sollte...
#

# UP5000 Modbus registers
# RegInvInputVol = 0x351d # B30, DC-AC discharging module-Current input voltage
RegACVol = 0x3521 # B34 Load Output Voltage
RegACCur = 0x3522 # Load Output Current
# XXX there is no "Load Output Power" register, compute it from voltage and current

RegPVYield = 0x3557 # Long B88/B89 PV 1 Total Cumulative Charge + 

RegPVVol = 0x3549 # B74
RegPVCur = 0x354a # B75
RegPVPow = 0x354b # Long B76/B77

# battery voltage
RegBAVol = 0x3580 # B128, Current system battery voltage
RegBACur = 0x3581 # Long B129/B130 Battery 1 Current L, It is positive when charging and negative when discharging.
RegBASoc = 0x3586 # Long B129/B130 Battery 1 Current L, It is positive when charging and negative when discharging.

# Grid input
RegGridVol = 0x3500 # B1, Electricity 1 Charging Input Voltage
RegGridCur = 0x3501 # B2, Electricity 1 Charging Input Current
RegGridPow = 0x3502 # B3/B4, Electricity 1 Charging Input Power L, AC-DC charging module--AC input current power

# Charger control
RegVCtrl_ECV = 0x9618 # D10, Equalize Charging Voltage
RegVCtrl_BCV = 0x9619 # D11, Boost Charging Voltage 
RegVCtrl_FCV = 0x961A # D12, Float Charging Voltage
RegVCtrl_BVR = 0x961B # D13, Boost Reconnect Charging Voltage

#
# State Registers
#
# RegGridChargerState': 1026 0x402 -> D10 + D1 set -> "Hardware over-voltage" + "Faults"
#
"""
B18 Electricity 1 Charging Status 3511
* D15~D14, 00 Normal input voltage, 01 Low input voltage, 02 High input voltage, 03 No connect to the input power, etc.
* D13~D12, Output power 00-Light load, 01-Medium load, 02-Nominal load, 03- Overload
* D5 Busbar over-voltage,
* D6 Busbar under-voltage,
* D7 Input over current,
* D8 abnormal output voltage,
* D9 Heat sink overheating,
* D10 Hardware over-voltage,
* D11 Short circuit,
* D4 Low temperature,
* D3~2 Charging status 00 No charging, 01 Float charging, 02 Boost charging, 03 Equalizing charging
* D1. 0 Normal, 1 Faults
* D0. 1 Run, 0 Standby
"""
RegGridChargerState = 0x3511


"""
B36 Load Output Status 3523
* D15~D14, 00 Normal input voltage, 01 Low input voltage, 02 High input voltage, 03 No connect to the input power, etc.
* D13~D12, Output power 00-Light load, 01-Medium load, 02-Nominal load, 03- Overload
* D5 Output fail, 
* D6 High voltage side short-circuit, 
* D7 Input over-current, 
* D8 Abnormal Output voltage, 
* D9 Unable to stop discharge, 
* D10 Unable to discharge,
* D11 short-circuit, 
* D4 Abnormal frequency, 
* D3 High temperature, 
* D2 Low temperature.
* D1. 0 Normal, 1 Faults
* D0. 1 Run, 0 Standby
"""
RegLoadState = 0x3523


"""
B90 PV 1 Charging Device 1 Work Status  3559 
* D15~D14 Input voltage status. 00 Normal, 01 Without input power, 02H High input voltage, 03H Error input voltage.
* D13 Charging MOS tube short circuit, 
* D12 Charging or anti-reverse MOS tube open circuit
* D11 Anti-reverse MOS tube short circuit, 
* D10 Input over current, 
* D9 Load over current when charges the device connected with load, 
* D8 Load short- circuit, 
* D7 Load MOS tube short-circuit
* D3~2 Charging status 00 No charging, 01 Float charging, 02 Boost charging, 03 Equalizing charging
* D4. PV Input Short Circuit(Add in 9/16/2013)
* D5. LED Load Open Circuit(Add in 8/12/2013)
* D6. Three-way Circuit Imbalance(Add in 8/12/2013)
* D1. 0 Normal, 1 Faults
* D0. 1 Run, 0 Standby
"""
RegPVChargerState = 0x3559


"""
B137 Battery 1 Status 3589 
* D3~D0, 01H Over voltage, 00H Normal, 02H Under voltage, 03H Over discharge, 04H Faults(BMS Protection) 
* D7~D4, 00H Normal, 01H Over temperature (exceeds the high temperature alarm value), 02H Low temperature(lower than the low temperature alarm value), 
* D8, Battery internal resistance abnormal 1, normal 0; 
* D9 Lithium battery charging protection; 
* D10 Lithium battery discharging protection.
* D15, 1-Nominal voltage identification error(The relationship between electricity and PV charging for batteries)
"""
RegBattState = 0x3589



def noround(v, x):
    return v

class UP5000(object):

    def __init__(self, dev, connection='UP5000'):

        servicenameCharger=f'com.victronenergy.solarcharger.{dev}'
        # servicenameInverter=f'com.victronenergy.inverter.{dev}'
        # servicenameInverter=f'com.victronenergy.multi.{dev}'
        servicenameInverter=f'com.victronenergy.vebus.{dev}'

        logging.debug(f"Opening serial interface {dev} for modbus...")
        self.device = "/dev/" + dev
        self.up = UPower(device=self.device)
        if self.up.connect() < 0:
            logging.warning("Cant open rs485 interface {device}, exiting")
            sys.exit(0)

        logging.debug("Service %s and %s starting... " % (servicenameCharger, servicenameInverter))

        dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
        register = { '/Info/MaxDischargeCurrent': dummy, '/Info/MaxChargeVoltage': dummy } 
        dbus_tree= {
            'com.victronenergy.settings': {
                '/': dummy,
                '/Settings/SystemSetup/AcInput1': dummy,
            },
            'com.victronenergy.battery': register,
        }
        self._dbusmonitor = DbusMonitor(dbus_tree)

	    # Get dynamic servicename for serial-battery
        serviceList = self._get_service_having_lowest_instance('com.victronenergy.battery')
        print(serviceList)
        if not serviceList:
            # Restart process
            logging.info("service com.victronenergy.battery not registered yet, exiting...")
            sys.exit(0)
        self.batt_service = serviceList[0]
        logging.info("service of battery: " +  self.batt_service)

        self._dbusserviceCharger = VeDbusService(servicenameCharger, bus=dbus.bus.BusConnection.__new__(dbus.bus.BusConnection, dbus.bus.BusConnection.TYPE_SYSTEM))
        self._dbusserviceInverter = VeDbusService(servicenameInverter, bus=dbus.bus.BusConnection.__new__(dbus.bus.BusConnection, dbus.bus.BusConnection.TYPE_SYSTEM))

        self.createManagementPaths(self._dbusserviceCharger, "UP5000 MPPT Solar Charger", connection)
        self.createManagementPaths(self._dbusserviceInverter, "UP5000 Inverter", connection)

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

        # Open-state of datafile
        self._dbusserviceCharger.add_path('/Modbus/ModbusOpened', 1)
        # Request to close datafile
        self._dbusserviceCharger.add_path('/Modbus/CloseModbus', 0, description="Request to close file", writeable=True, onchangecallback=self.closeRequest)

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

        self._dbusserviceCharger['/Modbus/ModbusOpened'] = 1
        self._dbusserviceCharger['/Modbus/CloseModbus'] = 0

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
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/NumberOfAcInputs', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/Connected', 0)
        # self._dbusserviceInverter.add_path('/Ac/In/1/Type', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/P', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/V', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/I', 0)
        self._dbusserviceInverter.add_path('/Ac/ActiveIn/L1/F', 0)

        self._dbusserviceInverter.add_path('/Mode', 0)
        self._dbusserviceInverter.add_path('/State', 0)
        self._dbusserviceInverter.add_path('/Soc', 0)

        self._dbusserviceInverter['/Dc/0/Voltage'] = 0
        self._dbusserviceInverter['/Dc/0/Current'] = 0

        self._dbusserviceInverter['/Ac/Out/L1/V'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/I'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/P'] = 0
        self._dbusserviceInverter['/Ac/Out/L1/F'] = 50 # xxx

        self._dbusserviceInverter['/Ac/ActiveIn/ActiveInput'] = 0
        self._dbusserviceInverter['/Ac/ActiveIn/NumberOfAcInputs'] = 1
        self._dbusserviceInverter['/Ac/ActiveIn/Connected'] = 1
        # self._dbusserviceInverter['/Ac/In/1/Type'] = 1
        self._dbusserviceInverter['/Ac/ActiveIn/L1/P'] = 23
        self._dbusserviceInverter['/Ac/ActiveIn/L1/V'] = 230 # xxx not used?
        self._dbusserviceInverter['/Ac/ActiveIn/L1/I'] = 0.1 # xxx not used?
        self._dbusserviceInverter['/Ac/ActiveIn/L1/F'] = 50 # xxx not used?

        self._dbusserviceInverter['/Mode'] = 3 # on
        self._dbusserviceInverter['/State'] =  9 # inverting
        self._dbusserviceInverter['/Soc'] = 0

        logging.debug("Reading initial values to test modbus connection...")
        pvvol = self.up.readReg(RegPVVol, "RegPVVol")
        pvcur = self.up.readReg(RegPVCur, "RegPVCur")
        loadVol = self.up.readReg(RegACVol, "RegACVol")
        accur = self.up.readReg(RegACCur, "RegACCur")
        if pvvol == None and pvcur == None and loadVol == None and accur == None:
            sys.exit(0)

        #
        # Setting '/Settings/SystemSetup/AcInput1' must be set to a valid input source type (0: nothing, 1: grid, 2: generator), this 
        # can be done using victron-remote web interface under settings/system-setup/ac input.
        #
        # Use
        #   dbus -y com.victronenergy.settings /Settings AddSetting SystemSetup AcInput1 1 i 0 3
        # to create setting.
        # See https://github.com/victronenergy/localsettings, https://github.com/victronenergy/velib_python/blob/master/settingsdevice.py#L69,
        # https://community.victronenergy.com/questions/61051/how-to-create-a-new-local-setting-using-comvictron.html
        #
        # ok, we need SettingsDevice
        # self._dbusmonitor.set_value('com.victronenergy.settings', '/Settings/SystemSetup/AcInput1', 1)
        #
        """
		# Connect to localsettings
		supported_settings = {
			'batteryservice': ['/Settings/SystemSetup/BatteryService', self.BATSERVICE_DEFAULT, 0, 0],
			'hasdcsystem': ['/Settings/SystemSetup/HasDcSystem', 0, 0, 1],
			'useacout': ['/Settings/SystemSetup/HasAcOutSystem', 1, 0, 1]}

		for m in self._modules:
			for setting in m.get_settings():
				supported_settings[setting[0]] = list(setting[1:])

		self._settings = self._create_settings(supported_settings, self._handlechangedsetting)



	def _create_settings(self, *args, **kwargs):
		bus = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
		return SettingsDevice(bus, *args, timeout=10, **kwargs)

	def _create_dbus_service(self):
		venusversion, venusbuildtime = self._get_venus_versioninfo()

		dbusservice = VeDbusService('com.victronenergy.system')
		dbusservice.add_mandatory_paths(
			processname=__file__,

        """

        self.update()

        GLib.timeout_add(5000, exit_on_error, self.update)
        # GLib.timeout_add(5000, self.update)

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

    def setChargingVoltage(self, vc):

        # get current setting
        curcv = self.up.readReg(RegVCtrl_ECV, "RegVCtrl_ECV")

        if curcv != None:

            if vc < curcv:

                self.up.writeParam(RegVCtrl_BVR, vc) # RegVCtrl_BVR = 0x961B # D13, Boost Reconnect Charging Voltage

                self.up.writeParam(RegVCtrl_ECV, vc) # RegVCtrl_ECV = 0x9618 # D10, Equalize Charging Voltage
                self.up.writeParam(RegVCtrl_BCV, vc) # RegVCtrl_BCV = 0x9619 # D11, Boost Charging Voltage 
                self.up.writeParam(RegVCtrl_FCV, vc) # RegVCtrl_FCV = 0x961A # D12, Float Charging Voltage

            elif vc > curcv:

                self.up.writeParam(RegVCtrl_ECV, vc) # RegVCtrl_ECV = 0x9618 # D10, Equalize Charging Voltage
                self.up.writeParam(RegVCtrl_BCV, vc) # RegVCtrl_BCV = 0x9619 # D11, Boost Charging Voltage 
                self.up.writeParam(RegVCtrl_FCV, vc) # RegVCtrl_FCV = 0x961A # D12, Float Charging Voltage

                self.up.writeParam(RegVCtrl_BVR, vc) # RegVCtrl_BVR = 0x961B # D13, Boost Reconnect Charging Voltage

            else:
                pass

    def update(self):

        if not self.devIsOpen():
            logging.info('update(): modbus device closed, skipping read/update.')
            return True

        logging.info('update...')

        #
        # Cell-voltage-based Battery manaement
        #
        # Charging 
        # input: bms.Info/MaxChargeVoltage                                                                                                                                                                                                                          55.2
        # output: up5000 
        # 
        maxCV = self._dbusmonitor.get_value(self.batt_service, "/Info/MaxChargeVoltage")
        if maxCV != None:
            logging.info(f"update(): MaxChargeVoltage info from BMS: {maxCV} V")
            # set boost, equalize and bost-reconnect voltages to charging
            # voltage from bms
            self.setChargingVoltage(54.4)
        else:
            logging.info("update(): no /Info/MaxChargeVoltage info from BMS!")
            # set boost, equalize and bost-reconnect voltages to a save value
            self.setChargingVoltage(54.4)

        # Discharging 
        # input: bms.Info/MaxDischargeCurrent 
        # output: up5000 C9 "Output Priority Mode" UP-OSP 9608 (0 Inverter priority 1 Utility priority)
        # 
        maxDC = self._dbusmonitor.get_value(self.batt_service, "/Info/MaxDischargeCurrent")
        if maxDC != None:
            logging.info(f"update(): MaxDischargeCurrent info from BMS: {maxDC} A")
        else:
            logging.info("update(): no /Info/MaxDischargeCurrent info from BMS!")


        #
        # AC Input (Grid), inverter
        #
        gridvol = self.up.readReg(RegGridVol, "RegGridVol")
        if gridvol != None:
            self._dbusserviceInverter['/Ac/ActiveIn/L1/V'] = gridvol
        gridcur = self.up.readReg(RegGridCur, "RegGridCur")
        if gridcur != None:
            self._dbusserviceInverter['/Ac/ActiveIn/L1/I'] = gridcur
        gridpow = self.up.readLong(RegGridPow, "RegGridPow")
        if gridpow != None:
            self._dbusserviceInverter['/Ac/ActiveIn/L1/P'] = gridpow

        #
        # AC Output, inverter, Load
        #
        loadVol = self.up.readReg(RegACVol, "RegACVol")
        if loadVol != None:
            self._dbusserviceInverter['/Ac/Out/L1/V'] = noround(loadVol, 2)

        accur = self.up.readReg(RegACCur, "RegACCur")
        if accur != None:
            self._dbusserviceInverter['/Ac/Out/L1/I'] = noround(accur, 2)

        if loadVol != None and accur != None:
            acpow = loadVol * accur
            logging.info("AC power: %f (%f * %f)" % (acpow, loadVol, accur))
            self._dbusserviceInverter['/Ac/Out/L1/P'] = noround(acpow, 2)

        #
        # PV Input, charger
        #
        pvyield = self.up.readLong(RegPVYield, "RegPVYield")
        if pvyield != None:
            self._dbusserviceCharger['/Yield/System'] = pvyield
            self._dbusserviceCharger['/Yield/User'] = pvyield

        pvvol = self.up.readReg(RegPVVol, "RegPVVol")
        if pvvol != None:
            self._dbusserviceCharger['/Pv/0/V'] = noround(pvvol, 2)

        # pvcur = self.up.readReg(RegPVCur, "RegPVCur") # not used, for tracing only

        pvpow = self.up.readLong(RegPVPow, "RegPVPow")
        if pvpow != None:
            self._dbusserviceCharger['/Pv/0/P'] = noround(pvpow, 2)
            self._dbusserviceCharger['/Yield/Power'] = noround(pvpow, 2)

        bavol = self.up.readReg(RegBAVol, "RegBAVol")
        if bavol != None:
            self._dbusserviceCharger['/Dc/0/Voltage'] = noround(bavol, 2)
            self._dbusserviceInverter['/Dc/0/Voltage'] = noround(bavol, 2)

        bacur_real = self.up.readReg(RegBACur, "RegBACur", signed=True) # note: no readLong here

        if pvpow != None and bavol and bacur_real != None:

            bacur_pv = (pvpow / bavol)

            # XXX anteil AC-DC-charger?

            # falls ladung, dann wird batteriestrom dem pvcharger
            # zugeschrieben:
            if bacur_pv > 0:
                self._dbusserviceCharger['/Dc/0/Current'] = round(bacur_pv, 2) # positive=charging
            else:
                self._dbusserviceCharger['/Dc/0/Current'] = 0

            bacur_inverter_computed = bacur_real - bacur_pv # bacur_pv wird über pv-lader ins "victron-system" eingespeist
            self._dbusserviceInverter['/Dc/0/Current'] = round(bacur_inverter_computed, 2) # negative, inverter is discharging the batterie

            logging.info(f"Batt current sum from up5: {bacur_real}A, without pv-charge ({bacur_pv}A): {bacur_inverter_computed}A")

        # self._dbusserviceCharger['/Load/I'] = 0

        baSoc = self.up.readReg(RegBASoc, "RegBASoc")
        if baSoc != None:
            self._dbusserviceInverter['/Soc'] = noround(baSoc*100, 2)

        # Log state bits
        #
        # AC Grid Charger
        #
        state = self.up.readReg1(RegGridChargerState , "RegGridChargerState")
        if state != None:
            logging.info(f"     * Running: {(state & 0b01) > 0}")
            logging.info(f"     * Fault  : {(state & 0b10) > 0}")
            logging.info(f"     * HOV    : {(state & 0b10000000000) > 0} (Hardware over-voltage)")

            usedbits = 0b10000000011
            unUsedbits = state & ~usedbits
            if unUsedbits:
                logging.info(f"     * Warning: unused state bits: {unUsedbits:x}")

        #
        # PV Charger
        #
        state = self.up.readReg1(RegPVChargerState , "RegPVChargerState")
        if state != None:
            logging.info(f"     * Running   : {(state & 0b01) > 0}")
            logging.info(f"     * Fault     : {(state & 0b10) > 0}")

            chargState = state & 0xC
            if chargState == 0x0:
                logging.info(f"     * Charg mode: Idle")
            elif chargState == 0x1:
                logging.info(f"     * Charg mode: Float charging")
            elif chargState == 0x2:
                logging.info(f"     * Charg mode: Boost charging")
            else:
                logging.info(f"     * Charg mode: Equalizing charging")

            inpState = state & 0xC000
            if inpState == 0x0:
                logging.info(f"     * Input Voltage: Normal")
            elif inpState == 0x1:
                logging.info(f"     * Input Voltage: Without input")
            elif inpState == 0x2:
                logging.info(f"     * Input Voltage: High input voltage")
            else:
                logging.info(f"     * Input Voltage: Error input voltage")

            usedbits = 0b1100000000001111
            unUsedbits = state & ~usedbits
            if unUsedbits:
                logging.info(f"     * Warning: unused state bits: {unUsedbits:x}")

        #
        # Battery
        #
        # @4000000064201fb202c2a464 26.03.23_12:34:16_CEST DEBUG:root:Reading register 0x3589, 'RegBattState': 3 0x3
        # @4000000064201fb202cec1f4 26.03.23_12:34:16_CEST INFO:root:     * Under voltage: True
        # @4000000064201fb202e5b10c 26.03.23_12:34:16_CEST INFO:root:     * Warning: unused state bits: 1

        state = self.up.readReg1(RegBattState, "RegBattState")
        if state != None:
            logging.info(f"     * Under voltage: {(state & 0b10) > 0}")
            logging.info(f"     * Under voltage: {(state & 0b10) > 0}")

            usedbits = 0b11
            unUsedbits = state & ~usedbits
            if unUsedbits:
                logging.info(f"     * Warning: unused state bits: {unUsedbits:x}")

        #
        # AC Load output
        #
        state = self.up.readReg1(RegLoadState , "RegLoadState")
        if state != None:
            logging.info(f"     * Running          : {(state & 0b01) > 0}")
            logging.info(f"     * Fault            : {(state & 0b10) > 0}")
            logging.info(f"     * Low input voltage: {(state & 0b0100000000000000) > 0}") # 0x4000

            # set inverter mode, inverting or passthrough
            if state & 0b01:
                self._dbusserviceInverter['/State'] =  9 # inverting
            else:
                self._dbusserviceInverter['/State'] =  8 # passthrough

            usedbits = 0b0100000000000011
            unUsedbits = state & ~usedbits
            if unUsedbits:
                logging.info(f"     * Warning: unused state bits: {unUsedbits:x}")

        logging.info('update end')
        return True

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

    def devIsOpen(self):
        return self.up.instrument.serial.is_open

    def closeRequest(self, path, closeFile):

        if closeFile and self.devIsOpen():
            # close hybrid rs485
            self.up.instrument.serial.close()
            self._dbusserviceCharger['/Modbus/ModbusOpened'] = 0

        if not closeFile and not self.devIsOpen():
            # re-open hybrid rs485
            self.up.instrument.serial.open()
            self._dbusserviceCharger['/Modbus/ModbusOpened'] = 1

        return True

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


