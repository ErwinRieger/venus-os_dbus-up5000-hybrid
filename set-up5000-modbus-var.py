from UPower import UPower
import sys, time


reg = int(sys.argv[1], 16)
value = int(sys.argv[2], 16)

up = UPower(device="/dev/ttyUSB1")
if (up.connect() < 0):
    print("Could not connect to the device")
    exit(-2)

print(f"writing {value} to register {reg}")

up.writeParam(reg, value)

