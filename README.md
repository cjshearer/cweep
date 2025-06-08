## Overview

A compact 34 key, solar powered, split keyboard.

<img align="center" alt="keyboard back" src="https://github.com/user-attachments/assets/a6f44060-76dd-44ea-beb3-6cd05df484a0" width="33%" />
<img align="center" alt="keyboard front" src="https://github.com/user-attachments/assets/9f854a35-250d-4e65-bede-7c7884c4b16a" width="33%" />
<img align="center" alt="keyboard side" src="https://github.com/user-attachments/assets/529ec742-61d4-4a02-b278-078a31938a43" width="33%" />

<details>
  <summary>
    PCB and Schematic
  </summary>
  
  ![schematic](https://github.com/user-attachments/assets/6b148011-84a5-4fe5-a476-e5f340b6ac8b)
  ![PCB](https://github.com/user-attachments/assets/7d266270-ecd6-4ce9-ad74-49bbcba39a54)
</details>

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
| 3.7V LiPo Battery (25mm x 15mm x 4mm) | 2 | [13853](https://cdn.sparkfun.com/datasheets/Prototyping/spe-00-DTP401525-110mah-en-1.0ver.pdf) | [Octopart](https://octopart.com/prt-13853-sparkfun-76382075) |

### Switch Matrix

| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Kailh Choc V1 Keycaps | 34 | DDC Choc PBT Blanks | [Keebd](https://keebd.com/products/ddc-choc-pbt-blank-keycaps?variant=43210242785432) |
| Kailh Choc V1 Switches | 34 | PG1350 (e.g. [Sunset](https://cdn.shopify.com/s/files/1/0523/0847/6068/files/Choc_Sunset_datasheet.pdf))  | [Keebd](https://keebd.com/products/sunset-tactile-choc-switches?variant=41676091981976) |
| Kailh Choc Hotswap Sockets | 34 | [5118](https://cdn-shop.adafruit.com/product-files/5118/5118-Choc-Socket.pdf) | [Octopart](https://octopart.com/5118-adafruit+industries-119967299) |
| Diodes | 34 | 1N4148 | [Octopart](https://octopart.com/search?q=1n4148) |

### Solar Charger

| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Solar Cells | 2 | SM141K04LV | [Octopart](https://octopart.com/sm141k04lv-anysolar-120091681) |
| Boost Converter | 2 | [BQ25504](https://www.ti.com/document-viewer/bq25504/datasheet) | [Octopart](https://octopart.com/bq25504rgtr-texas+instruments-20530455) |

TODO: the other components for the solar charger circuit

## Credits

This project is inspired by the work of many in the custom keyboard community:

- Pierre Chavalier's [Ferris](https://github.com/pierrechevalier83/ferris): for the original design and layout
- David Philip Barr's [Sweep](https://github.com/davidphilipbarr/Sweep/): inspiration to build a wireless, ferris-like keyboard using a daughter board for the microcontroller  
- GEIGEIGEIST's [TOTEM](https://github.com/GEIGEIGEIST/TOTEM): for it's excellent build guide, which helped me understand what types of components I may need for a wireless split keyboard
- Pete Johanson's [revxlp](https://gitlab.com/lpgalaxy/revxlp): for the usage and layout of pogo pins to connect a socketed Seeed Xiao's battery and reset pins to the PCB
- Xudongz's [Ergoblue](https://www.xudongz.com/blog/2020/ergoblue/): my initial inspiration for building a solar powered wireless keyboard
- NGuyen Vincent's [Aloidia](https://hackaday.io/project/189688-aloidia-wireless-split-solar-powered-keyboard): for the detailed build log and all-around excellent resource on building solar powered wireless keyboard
