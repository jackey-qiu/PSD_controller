# PSD_controller
Hamilton steprized pump (PSD/4) control system
PSD_controller is developped to achieve continuing electrolyte exchange during electrochemical measurments through driving two pairs of Hamilton syringe pumps in an automatic way. In the advance exchange mode, two pairs of syringes will alternate to allow continuing electrolyte exchange. During measurment, one set (setA) of syringe pair is connected to the EC cell for exchange, while the other one (setB) will get itself ready for next exchange cycle with one syringe being filled and the other one being drained. When the exchangable electrolyte in setA is used up, the valves will switch over accordingly to start another exchange cycle with setB. While setB is in the process of the electrolyte exchange, setA will refill/drain the associated syringe and wait for the completion of exchange at setB. This exchange alternation (setA <--> setB) will go on and on until electrolyte solution in the reservior bottle is used up.

![main_gui](https://github.com/jackey-qiu/PSD_controller/blob/master/doc/imgs/main_gui_at_starting.PNG)

## Refer to wiki page for operation tutorial.
