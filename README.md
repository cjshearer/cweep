## Overview

This project is a custom wireless split keyboard in development, inspired by various open-source designs like the [Sweep](https://github.com/davidphilipbarr/Sweep/), [LambBT](https://github.com/johnlamb/LambBT), [TOTEM](https://github.com/GEIGEIGEIST/TOTEM), and [revxlp](https://gitlab.com/lpgalaxy/revxlp). The goal is to achieve a compact 34 key layout with low-profile choc switches, solar panels, and external dongle support. The long-term vision is to keep the overall footprint small and portable, while accommodating future enhancements.

## Bill of Materials

> [!NOTE]
> This is a preliminary list of components needed for the keyboard. The final list may change as the design evolves.

- 2 × Seeed Xiao nRF52840
- Optional additional dongle for host devices without native BLE
- 34 × Kailh Low Profile Choc Switches (e.g., Sunset Tactile)
- 34 × Kailh Choc Hotswap Sockets
- 34 × 1U Kailh Choc Keycaps (e.g DDC Choc PBT Blanks)
- 34 × 1N4148 Diodes (through-hole)
- 4 × 7-Pin Machined IC Female Header Strips (buy larger strips and break to size)
- 4 x 7 Mill-Max Low Profile Controller Pins (for MCU and female header strips)
- 2 × 3-Pin 2-Position Switches
- 4 x Mill-Max 0906-0-15-20-76-14-11-0 pogo pins (for battery and reset pads)
- 2 × LiPo Batteries (e.g., ~15×22×7.5 mm)
- 2 x Solar panel(s) sized to fit above the MCU

## Project Status

PCB Layout: Still iterating on component placement.
Firmware: Planning to use ZMK.
Case & Plate: Planning on a thin, steel backplate for magnetic mounting.
Power: Exploring solar panel options for battery charging.

## Contributing

Pull requests and feedback are welcomed. Please open an issue or PR for suggestions or improvements.
