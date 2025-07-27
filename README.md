## Overview

A compact 34 key, solar powered, split keyboard.

<img align="center" alt="keyboard back" src="https://github.com/user-attachments/assets/03c862e9-76a9-4d78-ac7e-4f69d2b9a411" width="30%" />
<img align="center" alt="keyboard front" src="https://github.com/user-attachments/assets/12838771-191e-4807-98d7-0a500454265f" width="30%" />
<img align="center" alt="keyboard side" src="https://github.com/user-attachments/assets/019f1173-e050-47f8-b5f8-ad332712b6a1" width="30%" />

<details>
  <summary>
    PCB and Schematic
  </summary>
  
  [![schematic](https://github.com/user-attachments/assets/ef03d05c-f5cb-4878-8143-b153b7e96af6)](https://github.com/user-attachments/assets/ef03d05c-f5cb-4878-8143-b153b7e96af6)
  [![PCB](https://github.com/user-attachments/assets/2090d4e2-3f3c-40de-934b-bc438d648ae2)](https://github.com/user-attachments/assets/2090d4e2-3f3c-40de-934b-bc438d648ae2)
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
| Power Switch | 2 | [KAN-15](https://hackaday.io/project/174738-kan-15-led-tactile-switch/log/183418-switches-switches-switches#KAN-15:~:text=8016717020588253%26productId%3D4000960302909-,KAN%2D15,-Finally%2C%20I%20found) | [Amazon](https://www.amazon.com/TWTADE-Latching-Button-Switch-Flashlight/dp/B086M6P1RF) |
| Reset Button | 2 | [B3F-1020](https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3f.pdf) (adafruit 367) | [Octopart](https://octopart.com/b3f-1020-omron-46944) |

### Switch Matrix

| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Kailh Choc V1 Keycaps | 34 | DDC Choc PBT Blanks | [Keebd](https://keebd.com/products/ddc-choc-pbt-blank-keycaps?variant=43210242785432) |
| Kailh Choc V1 Switches | 34 | PG1350 (e.g. [Sunset](https://cdn.shopify.com/s/files/1/0523/0847/6068/files/Choc_Sunset_datasheet.pdf))  | [Keebd](https://keebd.com/products/sunset-tactile-choc-switches?variant=41676091981976) |
| Kailh Choc Hotswap Sockets | 34 | [A5118](https://cdn-shop.adafruit.com/product-files/5118/5118-Choc-Socket.pdf) | [Octopart](https://octopart.com/5118-adafruit+industries-119967299) |
| Diodes | 34 | 1N4148 | [Octopart](https://octopart.com/search?q=1n4148) |

### Solar Charger

| Description | Count | Value | Source |
|-------------|-------|-------|--------|
| Solar Cells | 2 | [SM141K04LV](https://waf-e.dubudisk.com/anysolar.dubuplus.com/techsupport@anysolar.biz/O18Ae0B/DubuDisk/www/Gen3/SM141K04LV%20DATA%20SHEET%20202007.pdf) | [Octopart](https://octopart.com/sm141k04lv-anysolar-120091681) |
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
