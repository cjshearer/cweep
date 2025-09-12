## Overview

A compact, 34 key, solar powered, split keyboard.

<img width="45%" alt="bottom" src="https://github.com/user-attachments/assets/c8329a46-f3e5-4f25-a8a2-339172839555" />
<img width="45%" alt="top" src="https://github.com/user-attachments/assets/4fc40650-b64b-4d59-8e73-ec2571f9aa10" />

<a href="https://github.com/user-attachments/assets/c26093d8-f3e7-4a7d-a30f-303f3c635c93">
  <img width="45%" alt="B_Cu" src="https://github.com/user-attachments/assets/c26093d8-f3e7-4a7d-a30f-303f3c635c93" />
</a>
<a href="https://github.com/user-attachments/assets/fa411918-0815-4199-8f95-43fc10f712b4">
  <img width="45%" alt="F_Cu" src="https://github.com/user-attachments/assets/fa411918-0815-4199-8f95-43fc10f712b4" />
</a>


<a href="https://github.com/user-attachments/assets/5da62548-fc56-4f94-b4f0-1e69b9bb80f9">
  <img width="45%" alt="top-zoom-out-3-zccw15-xcw4" src="https://github.com/user-attachments/assets/5da62548-fc56-4f94-b4f0-1e69b9bb80f9" />
</a>
<a href="https://github.com/user-attachments/assets/6fd5548f-e36d-4018-b9a2-e0769077f58f">
  <img width="45%" alt="top-zoom-out-3-zcw3-xcw3" src="https://github.com/user-attachments/assets/6fd5548f-e36d-4018-b9a2-e0769077f58f" />
</a>

<details>
  <summary>
    Schematic
  </summary>

  <img alt="schematic" src="https://github.com/user-attachments/assets/b370edf5-2cb7-4d84-97d4-b6aa28b78579" />
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
| Controller Pins | 28 | [3320-0-00-15-00-00-03-0](https://datasheet.octopart.com/3320-0-00-15-00-00-03-0-Mill-Max-datasheet-180682269.pdf) | [Octopart](https://octopart.com/3320-0-00-15-00-00-03-0-mill-max-29613931) |
| Battery/Reset Pogo Pins | 4 | 0906-0-15-20-76-14-11-0 | [Octopart](https://octopart.com/0906-0-15-20-76-14-11-0-mill-max-259418) |
| Battery | 2 | [ICR10440](https://www.powerstream.com/p/ICR10440-300mAh.pdf) | [Amazon](https://www.amazon.com/dp/B08H4RC1Y5) |
| Power Switch | 2 | [KAN-15](https://hackaday.io/project/174738-kan-15-led-tactile-switch/log/183418-switches-switches-switches#KAN-15:~:text=8016717020588253%26productId%3D4000960302909-,KAN%2D15,-Finally%2C%20I%20found) | [Amazon](https://www.amazon.com/TWTADE-Latching-Button-Switch-Flashlight/dp/B086M6P1RF) |
| Reset Button | 2 | [B3F-1020](https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3f.pdf) (adafruit 367) | [Octopart](https://octopart.com/b3f-1020-omron-46944) |
| Kailh Choc V1 Keycaps | 34 | DDC Choc PBT Blanks | [Keebd](https://keebd.com/products/ddc-choc-pbt-blank-keycaps?variant=43210242785432) |
| Kailh Choc V1 Switches | 34 | PG1350 (e.g. [Sunset](https://cdn.shopify.com/s/files/1/0523/0847/6068/files/Choc_Sunset_datasheet.pdf))  | [Keebd](https://keebd.com/products/sunset-tactile-choc-switches?variant=41676091981976) |
| Kailh Choc Hotswap Sockets | 34 | [A5118](https://cdn-shop.adafruit.com/product-files/5118/5118-Choc-Socket.pdf) | [Octopart](https://octopart.com/5118-adafruit+industries-119967299) |
| Diodes | 34 | [1N4148W](https://www.vishay.com/docs/86356/1n4148w.pdf) | [Octopart](https://octopart.com/1n4148w-e3-08-vishay-46456306) |
| Solar Cells | 2 | [SM141K04LV](https://waf-e.dubudisk.com/anysolar.dubuplus.com/techsupport@anysolar.biz/O18Ae0B/DubuDisk/www/Gen3/SM141K04LV%20DATA%20SHEET%20202007.pdf) | [Octopart](https://octopart.com/sm141k04lv-anysolar-120091681) |
| Boost Converter | 2 | [BQ25504](https://www.ti.com/document-viewer/bq25504/datasheet) | [Octopart](https://octopart.com/bq25504rgtr-texas+instruments-20530455) |
| 4.7uF Capacitor (CHV1) | 2 | [C0805C475K9PACTU](https://www.yageogroup.com/content/datasheet/asset/file/KEM_C1006_X5R_SMD) | [Octopart](https://octopart.com/c0805c475k9pactu-kemet-85989) |

## Credits

This project is inspired by the work of many in the custom keyboard community:

- Pierre Chavalier's [Ferris](https://github.com/pierrechevalier83/ferris): for the original design and layout
- David Philip Barr's [Sweep](https://github.com/davidphilipbarr/Sweep/): inspiration to build a wireless, ferris-like keyboard using a daughter board for the microcontroller  
- GEIGEIGEIST's [TOTEM](https://github.com/GEIGEIGEIST/TOTEM): for it's excellent build guide, which helped me understand what types of components I may need for a wireless split keyboard
- Pete Johanson's [revxlp](https://gitlab.com/lpgalaxy/revxlp): for the usage and layout of pogo pins to connect a socketed Seeed Xiao's battery and reset pins to the PCB
- Xudongz's [Ergoblue](https://www.xudongz.com/blog/2020/ergoblue/): my initial inspiration for building a solar powered wireless keyboard
- NGuyen Vincent's [Aloidia](https://hackaday.io/project/189688-aloidia-wireless-split-solar-powered-keyboard): for the detailed build log and all-around excellent resource on building solar powered wireless keyboard
