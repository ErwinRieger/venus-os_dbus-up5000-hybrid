import minimalmodbus, time
import logging

# Parameters

# When the battery voltage is higher than this value, the auxiliary charging module stops charging
# (in the mains priority case, if the battery voltage is higher than this value - the solar auxiliary charging is turned off;
#  in the solar priority case, the PV voltage is higher than this value, the mains auxiliary charging is turned off)
# V/100
UP_SysStopSubChrgVolt = 0x9605  

# When battery voltage is lower than this value, the auxiliary charging module starts charging
# (in the mains priority, the battery voltage is lower than this value - the solar auxiliary charging is turned on;
#  in the PV priority is lower, the battery voltage is lower than this value, the mains auxiliary charging is turned on)
UP_SysRecSubChrgVolt = 0x9606

# 0001H Sealed, 0002H GEL, 0003H Flooded, 0004H LiFePO4 battery, 0005H MnNiCo ternary battery , 0000H, User, user defined
UP_BatteryType = 0x9607
UP_BatteryTypes = ["User", "Sealed", "GEL", "Flooded", "LiFePO4", "MnNiCo"]
# Capacity in AH
UP_BatteryCapacity = 0x9608

# settings
UP_TotalAmpsIn = 0x9617
UP_TotalChargeMaxAmps = 0x9617

# priority mode
UP_ChargePriority = 0x9616
PriorityModes = ["","Grid Priority","Solar Priority","","Grid & Solar","","","","Solar Only"]

# on/off
ON = 1
OFF = 0

# params
# PV array
PVvolt = 0x3519
PVamps = 0x351A
PVwattL = 0x351B
PVwattH = 0x351C
PVkwhL = 0x3527
PVkwhH = 0x3528
PVtemp = 0x352C

# AC charger
ACvoltIN = 0x3500
ACvolt = 0x3505
ACamps = 0x3506
ACwattL = 0x3507
ACwattH = 0x3508
ACtemp = 0x3512

# battery
BAvolt = 0x351D
BAamps = 0x351E
BAwattL = 0x351F
BAvoltage = 0x354C
BAtemp = 0x354F
BAperc = 0x3550

#invertor and Load
IVherz = 0x353B
IVvoltIN = 0x352F
IVwattL = 0x3536
IVwattH = 0x3537
IVvolt = 0x3533
IVamps = 0x3534

#settings
STmode = 0x9616
STchrg = 0x3529
PVvolt = 0x3519
PVamps = 0x351A
PVwattL = 0x351B
PVwattH = 0x351C
PVkwhL = 0x3527
PVkwhH = 0x3528
PVtemp = 0x352C

# AC charger
ACvoltIN = 0x3500
ACvolt = 0x3505
ACamps = 0x3506
ACwattL = 0x3507
ACwattH = 0x3508
ACtemp = 0x3512

# battery
BAvolt = 0x351D
PVampOUT = 0x351E
BAwattL = 0x351F
BAvoltage = 0x354C
BAtemp = 0x354F
BAah = 0x3550

#invertor and Load
IVherz = 0x353B
IVvoltIN = 0x352F
IVwattL = 0x3536
IVwattH = 0x3537
IVvolt = 0x3533
IVamps = 0x3534

#switches
SWiv = 0x0106
SWpv = 0x010B
SWac = 0x010C
SWreset = 0x010A
########

class UPower:
        """A member of UPower communication class."""

        # connect to device
        def __init__(self, device = '/dev/ttyXRUSB0', serialid = 10):
                self.device = device
                self.id = serialid
                self.instrument = 0


        def connect(self):
            try:
                    self.instrument = minimalmodbus.Instrument(self.device, self.id)
            except minimalmodbus.serial.SerialException:
                    return -1

            self.instrument.serial.baudrate = 115200
            self.instrument.serial.bytesize = 8
            self.instrument.serial.parity   = minimalmodbus.serial.PARITY_NONE
            self.instrument.serial.stopbits = 1
            # self.instrument.serial.timeout  = 1.2
            self.instrument.serial.timeout  = 0.25
            self.instrument.mode = minimalmodbus.MODE_RTU
            return 0

        # read informational register
        def _readReg(self,register):
            try:
                    reading = self.instrument.read_register(register, 2, 4)
                    return reading
            except IOError:
                    return -2

        # read integer register (scale = 1)
        def readReg1(self,register, log="", signed=False):

            try:
                    reading = self.instrument.read_register(register, 0, 4, signed=signed)
            except IOError:
                    if log:
                        logging.debug(f"Error reading register 0x{register:x}, '{log}'")
                    return None

            if log:
                logging.debug(f"Reading register 0x{register:x}, '{log}': {reading} 0x{reading:x}")

            return reading

        # read informational register
        def readReg(self,register, log="", signed=False):

            try:
                    reading = self.instrument.read_register(register, 2, 4, signed=signed)
            except IOError:
                    if log:
                        logging.debug(f"Error reading register 0x{register:x}, '{log}'")
                    return None

            if log:
                logging.debug(f"Reading register 0x{register:x}, '{log}': {reading}")

            return reading

        # read two 16 bit, 100-scaled values and compute 32 bit long from it.
        # xxx positive values only.
        def readLong(self, register, log=""):

            low = self.readReg(register)
            high = self.readReg(register+1)

            if low == None or high == None:
                if log:
                    logging.debug(f"Error reading long register 0x{register:x}, '{log}'")
                return None

            reading = low + (high*0xffff)

            if log:
                logging.debug(f"Reading long register 0x{register:x}, '{log}': {reading}")

            return reading

        # read parameter
        def readParam(self,register,decimals=2, log=""):

            try:
                reading = self.instrument.read_register(register, decimals, 3)
            except IOError:
                if log:
                    logging.debug(f"Error reading param register 0x{register:x}, '{log}'")
                return None

            return reading

        # write parameter
        def writeParam(self,register,value):
            try:
                    reading = self.instrument.write_register(register, value, 2)
                    return 0
            except IOError:
                    return -2

        def setBatteryType(self, newBattType = "LiFePO4"):
                """Valid battery types: User, Sealed, GEL, Flooded, LiFePO4, MnNiCo"""
                try:
                        battno = UP_BatteryTypes.index(newBattType)
                except ValueError:
                        return -1
                if (self.writeParam(UP_BatteryType, int(battno)) < 0):  return -2
                return battno

        def setBatteryCapacity(self, newCapacity = 100):
                """Battery capacity in Ah"""
                if (self.writeParam(UP_BatteryCapacity, int(newCapacity/100)) < 0):     return -2
                return newCapacity

        def setChargePriority(self, newPri = "Solar Priority"):
                try:
                        prinum = PriorityModes.index(newPri)
                except ValueError:
                        return -1
                
                priValue = float(prinum)
                #if (self.writeParam(UP_ChargePriority, prinum) < 0): return -2
                return priValue

        # UPower switches
        def switchIV(self, onoff):
            ''"Inverter On/Off"""
            try:
                    self.instrument.write_bit(SWiv, onoff)
                    return onoff
            except IOError:
                    return -2


        def getIV(self):
            try:
                    reading = self.instrument.read_bits(SWiv, 1, 1)
                    return reading[0]
            except IOError:
                    return -2

        def switchAC(self, onoff):
            try:
                    self.instrument.write_bit(SWac, onoff)
                    return onoff
            except IOError:
                    return -2

        def getAC(self):
            try:
                    reading = self.instrument.read_bits(SWac, 1, 1)
                    return reading[0]
            except IOError:
                    return -2


        def reset(self):
            try:
                self.instrument.write_bit(SWreset,1)
            except IOError:
                return -2
            return 1

vl = [
("PVvolt", PVvolt),
("PVamps", PVamps),
("PVwattL", PVwattL),
("PVwattH", PVwattH),
("PVkwhL", PVkwhL),
("PVkwhH", PVkwhH),
("PVtemp", PVtemp),
("ACvoltIN", ACvoltIN),
("ACvolt", ACvolt),
("ACamps", ACamps),
("ACwattL", ACwattL),
("ACwattH", ACwattH),
("ACtemp", ACtemp),
("BAvolt", BAvolt),
("BAamps", BAamps),
("BAwattL", BAwattL),
("BAvoltage", BAvoltage),
("BAtemp", BAtemp),
("BAperc", BAperc),
("IVherz", IVherz),
("IVvoltIN", IVvoltIN),
("IVwattL", IVwattL),
("IVwattH", IVwattH),
("IVvolt", IVvolt),
("IVamps", IVamps),
("STmode", STmode),
("STchrg", STchrg),
("PVampOUT", PVampOUT),
("BAah", BAah),
("UP_SysStopSubChrgVolt", UP_SysStopSubChrgVolt),
("UP_SysRecSubChrgVolt", UP_SysRecSubChrgVolt),
("UP_BatteryType", UP_BatteryType),
("UP_BatteryCapacity", UP_BatteryCapacity),
("UP_TotalAmpsIn", UP_TotalAmpsIn),
("UP_TotalChargeMaxAmps", UP_TotalChargeMaxAmps),
("SWiv", SWiv),
("SWpv", SWpv),
("SWac", SWac),
("SWreset", SWreset),
]


if __name__ == "__main__":

    up = UPower(device="/dev/ttyUSB1")
    if (up.connect() < 0):
        print("Could not connect to the device")
        exit(-2)

    # print("volt: ", up.readReg(PVvolt))
    # print("BAvolt: ", up.readReg(BAvolt))
    for (n, reg) in vl:
        print("\nreadreg "+n+":", up.readReg(reg))
        time.sleep(0.1)
        print("readparam "+n+":", up.readParam(reg))
        time.sleep(0.1)


