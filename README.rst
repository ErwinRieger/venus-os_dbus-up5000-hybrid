
dbus-up5000-hybrid
==================

A venus-os driver for offgridtec/epever/whatever up5000 hybrid converters (a Offgridtec_IC-24_IC-48, in this case).

This service provides two dbus-services:

* com.victronenergy.solarcharger.<device>: emulate a victron "pv-charger"
* com.victronenergy.vebus.<device>: emulates a victron multiplus, the "inverter"

For example (dbus-spy):

::

   com.victronenergy.solarcharger.ttyUSB1                                                                                                                                                                                    UP5000 MPPT Solar Charger
   com.victronenergy.vebus.ttyUSB1                                                                                                                                                                                                     UP5000 Inverter
                                                                                                                                                                                                                                                      

It uses the rs485 modbus interface of the up5000 hybrid inverter.   


todo: some screenshots of victron venus-os 

