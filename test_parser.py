#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/federico/Scrivania/Git/SouthTech_Project/appdaemon/conf/apps')

from southtech_configurator_devices import DeviceConfigurationParser
import json

def test_parser():
    parser = DeviceConfigurationParser('/home/federico/Scrivania/Git/SouthTech_Project/esphome/hardware')
    devices = parser.get_all_devices()
    
    print("=== DISPOSITIVI TROVATI ===")
    for device in devices:
        print(f"\nDispositivo: {device.friendly_name}")
        print(f"Modello: {device.model}")
        print(f"File: {device.filename}")
        
        if 'relays' in device.configuration:
            print("Relè configurati:")
            for relay in device.configuration['relays']:
                print(f"  Relè {relay['number']}: {relay['name']} - Tipo: {relay['type']}")
        
        print(f"Configurazione completa:\n{json.dumps(device.to_dict(), indent=2)}")
        print("-" * 80)

if __name__ == "__main__":
    test_parser()
