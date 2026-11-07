"""Supported printer and uncalibrated material defaults."""

PROFILE = {
    'id': 'elegoo-centauri-carbon-2',
    'name': 'Elegoo Centauri Carbon 2',
    'build_volume_mm': [256, 256, 256],
    'nozzle_mm': 0.4,
    'colours': 1,
    # ElegooSlicer system presets used for slicer checks (engine/slicer.py), relative to
    # the slicer's bundled profiles/Elegoo folder. Machine matches nozzle_mm above.
    'slicer': {
        'machine': 'machine/ECC2/Elegoo Centauri Carbon 2 0.4 nozzle.json',
        'process': 'process/ECC2/0.20mm Standard @Elegoo CC2 0.4 nozzle.json',
        'filaments': {'PLA': 'filament/ECC2/Elegoo PLA @ECC2.json',
                      'PETG': 'filament/ECC2/Elegoo PETG @ECC2.json'},
    },
    'materials': {
        'PLA': {'fit_clearance_mm_per_side': {'sliding': 0.25, 'press': 0.10, 'print_in_place': 0.35},
                'calibrated': False},
        'PETG': {'fit_clearance_mm_per_side': {'sliding': 0.25, 'press': 0.10, 'print_in_place': 0.35},
                 'calibrated': False},
    },
}
