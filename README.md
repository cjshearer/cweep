## Overview

This project is a custom wireless split keyboard in development. The goal is to achieve a compact 34 key layout with low-profile choc switches, solar panels, and external dongle support. The long-term vision is to keep the overall footprint small and portable,

## Status

PCB Layout: Still iterating on component placement.
Firmware: Planning to use ZMK.
Case & Plate: Planning on a thin, steel backplate for magnetic mounting.
Power: Exploring solar panel options for battery charging.

## Bill of Materials (BOM)

> [!NOTE]
> This is a preliminary list of components needed for the keyboard. The final list may change as the design evolves.

### Microcontroller

| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Controller | 2 | Seeed Xiao nRF52840 | [Seeed Studio](https://www.seeedstudio.com/Seeed-XIAO-BLE-nRF52840-p-5201.html) |
| Controller Sockets | 4 x 7 | 310-87-107-41-001101 | [Octopart](https://octopart.com/310-87-107-41-001101-preci-dip-21424489) |
| Controller Pins | 28 | TODO | TODO |
| Reset/Battery Pogo Pins | 4 | 0906-0-15-20-76-14-11-0 | [Octopart](https://octopart.com/0906-0-15-20-76-14-11-0-mill-max-259418) |

### Switch Matrix
| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Kailh Choc V1 Keycaps | 34 | DDC Choc PBT Blanks | [Keebd](https://keebd.com/products/ddc-choc-pbt-blank-keycaps?variant=43210242785432) |
| Kailh Choc V1 Switches | 34 | PG1350 (e.g. [Sunset](https://cdn.shopify.com/s/files/1/0523/0847/6068/files/Choc_Sunset_datasheet.pdf))  | [Keebd](https://keebd.com/products/sunset-tactile-choc-switches?variant=41676091981976) |
| Kailh Choc Hotswap Sockets | 34 | [5118](https://cdn-shop.adafruit.com/product-files/5118/5118-Choc-Socket.pdf) | [Octopart](https://octopart.com/5118-adafruit+industries-119967299) |
| Diodes | 34 | 1N4148 | [Octopart](https://octopart.com/search?q=1n4148) |

### Battery
| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| 3.7V LiPo Battery (25mm x 15mm x 4mm) | 2 | [13853](https://cdn.sparkfun.com/datasheets/Prototyping/spe-00-DTP401525-110mah-en-1.0ver.pdf) | [Octopart](https://octopart.com/prt-13853-sparkfun-76382075) |

Solar Charger:
- 2 x solar cells (SM141K04LV)
- TODO: the other components for the solar charger circuit

## Credits

This project is inspired by the work of many in the open-source keyboard community:

- Pierre Chavalier's [Ferris](https://github.com/pierrechevalier83/ferris): for the original design and layout
- David Philip Barr's [Sweep](https://github.com/davidphilipbarr/Sweep/): inspiration to build a wireless, ferris-like keyboard using a daughter board for the microcontroller  
- GEIGEIGEIST's [TOTEM](https://github.com/GEIGEIGEIST/TOTEM): for it's excellent build guide, which helped me understand what types of components I may need for a wireless split keyboard
- Pete Johanson's [revxlp](https://gitlab.com/lpgalaxy/revxlp): for the usage and layout of pogo pins to connect a socketed Seeed Xiao's battery and reset pins to the PCB
- Xudongz's [Ergoblue](https://www.xudongz.com/blog/2020/ergoblue/): my initial inspiration for building a solar powered wireless keyboard
- NGuyen Vincent's [Aloidia](https://hackaday.io/project/189688-aloidia-wireless-split-solar-powered-keyboard): for the detailed build log and all-around excellent resource on building solar powered wireless keyboard
