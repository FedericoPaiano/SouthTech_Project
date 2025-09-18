#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/federico/Scrivania/Git/SouthTech_Project/appdaemon/conf/apps')

from southtech_configurator_devices import DeviceConfigurationParser
import json

def test_climate():
    parser = DeviceConfigurationParser('/home/federico/Scrivania/Git/SouthTech_Project/esphome/hardware')
    devices = parser.get_all_devices()
    
    for device in devices:
        print(f"\n=== {device.friendly_name} ===")
        if 'relays' in device.configuration:
            for relay in device.configuration['relays']:
                if relay['type'] == 'climate':
                    print(f"TROVATO CLIMATE:")
                    print(f"  Numero: {relay['number']}")
                    print(f"  Nome: {relay['name']}")
                    print(f"  Tipo: {relay['type']}")
                    print(f"  ID: {relay['id']}")
                    print(f"  Pin: {relay['pin']}")
                    print(f"  Internal: {relay['internal']}")
                    print(f"  JSON completo: {json.dumps(relay, indent=2)}")

if __name__ == "__main__":
    test_climate()
