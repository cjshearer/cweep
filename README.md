## Overview

This project is a custom wireless split keyboard in development, inspired by various open-source designs like the [Sweep](https://github.com/davidphilipbarr/Sweep/), [LambBT](https://github.com/johnlamb/LambBT), [TOTEM](https://github.com/GEIGEIGEIST/TOTEM), and [revxlp](https://gitlab.com/lpgalaxy/revxlp). The goal is to achieve a compact 34 key layout with low-profile choc switches, solar panels, and external dongle support. The long-term vision is to keep the overall footprint small and portable, while accommodating future enhancements.

## Bill of Materials

> [!NOTE]
> This is a preliminary list of components needed for the keyboard. The final list may change as the design evolves.

Microcontroller:
- 2 × Seeed Xiao nRF52840
- 2 × 3.7V LiPo batteries (13853)
  - ~6 week battery life (ignoring solar charging)
  - built-in over/under voltage and current protection
  - fits in 25mm x 15mm x 4mm space
- 4 × 7-Pin straight socket connectors (310-87-107-41-001101)
- 4 x 7 Mill-Max Low Profile Controller Pins (TODO: find part number and ensure pin thickness is compatible with socket)
- 4 x pogo pins (0906-0-15-20-76-14-11-0)
- 2 × 3-Pin 2-Position Switches (TODO: find part number)
- 2 reset buttons (TODO: find part number)
- Optional additional dongle for host devices without native BLE

Switch Matrix:
- 34 × Kailh Low Profile Choc Switches (e.g., Sunset Tactile)
- 34 × Kailh Choc Hotswap Sockets
- 34 × 1U Kailh Choc Keycaps (e.g DDC Choc PBT Blanks)
- 34 × 1N4148 Diodes (through-hole)

Solar Charger:
- 2 x solar cells (SM141K04LV)
- TODO: the other components for the solar charger circuit

## Project Status

PCB Layout: Still iterating on component placement.
Firmware: Planning to use ZMK.
Case & Plate: Planning on a thin, steel backplate for magnetic mounting.
Power: Exploring solar panel options for battery charging.

## Contributing

Pull requests and feedback are welcomed. Please open an issue or PR for suggestions or improvements.
