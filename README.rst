
dbus-up5000-hybrid
==================

A venus-os driver for offgridtec/epever/avian/powmr/whatever UP5000-HM8042 hybrid inverters (a Offgridtec_IC-48, in this case).

This service provides two dbus-services:

* com.victronenergy.solarcharger.<device>: emulate a victron "pv-charger"
* com.victronenergy.vebus.<device>: emulates a victron multiplus, the "inverter"

For example (dbus-spy):

::

   com.victronenergy.solarcharger.ttyUSB1                                                                                                                                                                                    UP5000 MPPT Solar Charger
   com.victronenergy.vebus.ttyUSB1                                                                                                                                                                                                     UP5000 Inverter
                                                                                                                                                                                                                                                      

It uses the rs485 modbus interface of the up5000 hybrid inverter.   


Some venus-os screenshots of a offgridtec hybrid system:

"Remote Console":

.. image:: images/img1.png
   :width: 400px
   :target: images/img1.png


.. image:: images/img2.png
   :width: 400px
   :target: images/img2.png


.. image:: images/img3.png
   :width: 400px
   :target: images/img3.png


.. image:: images/img4.png
   :width: 400px
   :target: images/img4.png


.. image:: images/img5.png
   :width: 400px
   :target: images/img5.png

.. image:: images/img6.png
   :width: 400px
   :target: images/img6.png

Victron VRM:

.. image:: images/img7.png
   :width: 500px
   :target: images/img7.png



