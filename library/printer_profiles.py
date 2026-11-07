"""Supported printer and uncalibrated material defaults."""

PROFILE = {
    'id': 'elegoo-centauri-carbon-2',
    'name': 'Elegoo Centauri Carbon 2',
    'build_volume_mm': [256, 256, 256],
    'nozzle_mm': 0.4,
    'colours': 1,
    'materials': {
        'PLA': {'fit_clearance_mm_per_side': {'sliding': 0.25, 'press': 0.10, 'print_in_place': 0.35},
                'calibrated': False},
        'PETG': {'fit_clearance_mm_per_side': {'sliding': 0.25, 'press': 0.10, 'print_in_place': 0.35},
                 'calibrated': False},
    },
}
