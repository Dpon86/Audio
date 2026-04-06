# Wearable Multi-Sensor Physiological Monitoring System
## Full Step-by-Step Development & Assembly Instructions

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Bill of Materials (BOM)](#3-bill-of-materials-bom)
4. [Tools & Consumables](#4-tools--consumables)
5. [Environment & Safety Setup](#5-environment--safety-setup)
6. [Step 1 — Power System Assembly](#6-step-1--power-system-assembly)
7. [Step 2 — Microcontroller Setup](#7-step-2--microcontroller-setup)
8. [Step 3 — Sensor Integration](#8-step-3--sensor-integration)
   - 8.1 [ECG — MAX30003](#81-ecg--max30003)
   - 8.2 [Multi-lead ECG — ADS1298R (Optional)](#82-multi-lead-ecg--ads1298r-optional)
   - 8.3 [Bio-impedance + ECG — AFE4300 (Optional)](#83-bio-impedance--ecg--afe4300-optional)
   - 8.4 [SpO₂ / Heart Rate — MAX30102](#84-spo--heart-rate--max30102)
   - 8.5 [Skin Temperature — Sensirion STS40-AD](#85-skin-temperature--sensirion-sts40-ad)
   - 8.6 [6-Axis IMU — TDK ICM-42688-P](#86-6-axis-imu--tdk-icm-42688-p)
9. [Step 4 — Wearable Mechanical Integration](#9-step-4--wearable-mechanical-integration)
10. [Step 5 — Firmware Development](#10-step-5--firmware-development)
11. [Step 6 — Testing & Validation](#11-step-6--testing--validation)
12. [Step 7 — Data Logging & Wireless Streaming](#12-step-7--data-logging--wireless-streaming)
13. [Troubleshooting Guide](#13-troubleshooting-guide)
14. [Next Steps: Moving to Custom PCB](#14-next-steps-moving-to-custom-pcb)

---

## 1. Project Overview

**Project Title:** Wearable Multi-Sensor Physiological Monitoring System

**Objective:**  
Build a developmental prototype wearable device that captures high-quality physiological signals — ECG, SpO₂, heart rate, skin temperature, motion, and optional bio-impedance — using medical-grade sensors integrated into a compression garment or arm/wrist band.

**Signals Captured:**

| Signal | Sensor | Interface |
|---|---|---|
| ECG (single-lead) | MAX30003 | SPI |
| ECG (multi-lead, optional) | ADS1298R | SPI |
| Bio-impedance (optional) | AFE4300 | SPI |
| SpO₂ + Heart Rate (PPG) | MAX30102 | I²C |
| Skin Temperature | Sensirion STS40-AD | I²C |
| 6-axis Motion (Accel + Gyro) | TDK ICM-42688-P | SPI or I²C |

**Intended Use:**
- Early-stage R&D and feasibility testing
- Biosignal algorithm development
- Clinical signal quality evaluation
- Wearable product prototyping

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Li-ion Battery (500–1000 mAh)          │
│                         │                               │
│                  BQ25895 Charger                         │
│                         │                               │
│               3.3 V LDO Regulator                        │
│                         │                               │
│         ┌───────────────┼───────────────┐                │
│         │               │               │                │
│   MCU (nRF5340 DK   or ESP32-S3)        │                │
│   ├── SPI Bus                           │                │
│   │   ├── MAX30003 (ECG)                │                │
│   │   ├── ADS1298R (multi-lead ECG*)    │                │
│   │   ├── AFE4300  (bio-impedance*)     │                │
│   │   └── ICM-42688-P (IMU)            │                │
│   └── I²C Bus                          │                │
│       ├── MAX30102 (SpO₂/HR)           │                │
│       └── STS40-AD (Temperature)       │                │
│                                        │                │
│   BLE 5.x ──────────────────────────► Mobile App /     │
│   (optional SD card logging)           Cloud Dashboard  │
└─────────────────────────────────────────────────────────┘

* Optional sensors
```

**Communication Buses:**
- **SPI** — used for high-speed sensors (ECG AFEs, IMU)
- **I²C** — used for lower-bandwidth sensors (PPG, temperature)
- **BLE** — wireless data streaming at up to 2 Mbps PHY

---

## 3. Bill of Materials (BOM)

### 3.1 Core Sensor Breakout Boards

| # | Component | Part Number | Function | Qty |
|---|---|---|---|---|
| 1 | Single-lead ECG AFE | MAX30003 breakout | ECG acquisition | 1 |
| 2 | Multi-lead ECG AFE *(optional)* | ADS1298R breakout | 8-channel ECG | 1 |
| 3 | Bio-impedance AFE *(optional)* | AFE4300 breakout | BIA + ECG combo | 1 |
| 4 | SpO₂ + Heart Rate | MAX30102 breakout | Optical PPG | 1 |
| 5 | Skin Temperature | STS40-AD breakout | Body temp | 1 |
| 6 | 6-axis IMU | ICM-42688-P breakout | Motion + gyro | 1 |

### 3.2 Microcontroller / Wireless

| # | Component | Notes |
|---|---|---|
| A | Nordic nRF5340 DK | Preferred for medical BLE — dual-core, BLE 5.3, ultra-low noise |
| B | Espressif ESP32-S3 DevKit | Alternative — dual-core, BLE + Wi-Fi, good for cloud |

> **Recommendation:** Use the nRF5340 DK for prototyping medical-grade signal streaming. Switch to ESP32-S3 only if Wi-Fi connectivity or edge ML is required.

### 3.3 Power Components

| # | Component | Spec |
|---|---|---|
| 1 | Li-ion Battery | 500–1000 mAh, 3.7 V nominal, JST-PH 2-pin |
| 2 | Battery Charger Module | BQ25895 (I²C-configurable, up to 5 A) |
| 3 | LDO Voltage Regulator | 3.3 V output, ≥300 mA, low-noise (e.g. MCP1700 or AP2112) |
| 4 | Power Switch | SPDT slide switch or tactile with latch |
| 5 | JST Connectors | JST-PH 2-pin (battery), JST-SH 4-pin (I²C/SPI breakouts) |
| 6 | Bypass Capacitors | 100 nF + 10 µF per power rail node |

### 3.4 Wiring & Interconnects

| Item | Purpose |
|---|---|
| Silicone-insulated jumper wires (28–30 AWG) | Flexible, body-safe inter-board wiring |
| Shielded ECG lead wires | Reduce EMI pickup on ECG electrode lines |
| JST-PH crimp connectors | Secure battery connections |
| Breadboard / proto-board | Initial bench testing |
| Heat-shrink tubing (2 mm, 4 mm) | Insulation and strain relief |

### 3.5 Electrodes & Wearable Hardware

| Item | Purpose |
|---|---|
| Disposable Ag/AgCl ECG snap electrodes | Body surface ECG contacts |
| ECG snap-to-wire adapters | Connect shielded lead wires to electrode snaps |
| Compression sleeve or arm band | Wearable platform |
| 3D-printed enclosure (PLA or PETG) | Houses MCU, power, connectors |

---

## 4. Tools & Consumables

| Tool | Purpose |
|---|---|
| Soldering iron (temperature-controlled, ≤350 °C) | Header pin soldering |
| Solder (60/40 or lead-free, 0.5–0.8 mm) | Electrical joints |
| Flux pen | Clean solder joints on fine-pitch pads |
| Digital multimeter | Continuity checks, voltage measurement |
| Oscilloscope (≥20 MHz, 2-channel preferred) | Signal waveform verification |
| Logic analyzer (8-channel) | SPI/I²C bus debugging |
| Bench power supply (3.3 V / 1 A adjustable) | Safe initial power-up |
| Anti-static wrist strap | ESD protection |
| Tweezers, wire strippers, flush cutters | Assembly |
| Isopropyl alcohol (IPA 99%) + cotton swabs | PCB/board cleaning |
| USB-to-UART adapter | Serial debug console |

---

## 5. Environment & Safety Setup

1. **Work surface:** Use an anti-static mat connected to earth ground.
2. **ESD protection:** Wear an anti-static wrist strap at all times when handling breakout boards.
3. **Ventilation:** Solder in a ventilated area or use a fume extractor.
4. **First power-up:** Always use a bench power supply with current limiting set to 200 mA before connecting the Li-ion battery to prevent damage from wiring errors.
5. **Battery safety:** Never short Li-ion battery terminals. Keep away from metal tools when handling unprotected cells.
6. **Human testing:** This is a developmental prototype — **do not use for diagnosis or clinical decision-making**. Apply only to the skin surface with appropriate electrodes; never apply electrical stimulus to a subject.

---

## 6. Step 1 — Power System Assembly

### 6.1 Overview

The power chain is:  
`Li-ion Battery → BQ25895 Charger → 3.3 V LDO → MCU + All Sensors`

---

### 6.2 Wiring the BQ25895 Charger

1. Solder male header pins to the BQ25895 breakout board if not already populated.
2. Connect the USB Micro-B or USB-C port on the BQ25895 to your power source (5 V).
3. Connect `VBAT` and `GND` pins on the BQ25895 to the positive and negative terminals of the Li-ion battery via a JST-PH 2-pin connector.
4. Connect `SYS` (or `VSYS`) output on the BQ25895 to the input of the 3.3 V LDO regulator.
5. Connect `SCL` and `SDA` on the BQ25895 to the MCU I²C bus if you want software-configurable charging parameters (optional for basic prototyping).

> **Note:** The BQ25895 automatically begins charging when a valid input voltage (USB 5 V) is detected. Default charge current is approximately 2 A — verify the breakout board's current-sense resistor and set a safe charge current via I²C if modifying.

---

### 6.3 Wiring the 3.3 V LDO Regulator

1. Connect `VIN` of the LDO to `SYS` output of the BQ25895.
2. Connect `GND` of the LDO to common ground.
3. Place a **100 nF ceramic capacitor** between `VIN` and `GND` (as close to the LDO input pin as possible).
4. Place a **10 µF electrolytic or tantalum capacitor** and a **100 nF ceramic capacitor** between `VOUT` and `GND`.
5. Route `VOUT` (3.3 V) to a common power bus rail used by the MCU and all sensors.

---

### 6.4 Power-Up Verification

1. Set bench power supply to **5.0 V, 200 mA current limit**.
2. Connect bench supply to the USB input of the BQ25895 breakout (without battery connected yet).
3. Measure voltage at `VOUT` of the LDO → should read **3.3 V ± 0.1 V**.
4. Measure ripple on the 3.3 V rail with an oscilloscope → should be **< 10 mVpp**.
5. Once verified, connect the Li-ion battery.

---

## 7. Step 2 — Microcontroller Setup

### 7.1 Installing the Development Environment

#### Option A — nRF5340 DK (Nordic SDK)

```bash
# Install nRF Connect SDK via nRF Connect for Desktop
# https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-Desktop

# Install Zephyr RTOS dependencies
pip install west
west init -m https://github.com/nrfconnect/sdk-nrf --mr main nrf
cd nrf && west update
west zephyr-export

# Verify toolchain
west build --version
```

Install **nRF Connect for VS Code** extension for IDE support.

#### Option B — ESP32-S3 (ESP-IDF)

```bash
# Install ESP-IDF
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
. ./export.sh

# Verify toolchain
idf.py --version
```

---

### 7.2 Flashing Test Firmware

#### nRF5340 — BLE Peripheral Sample

```bash
cd nrf/samples/bluetooth/peripheral_hr
west build -b nrf5340dk_nrf5340_cpuapp
west flash
```

#### ESP32-S3 — BLE GATT Server Sample

```bash
cd esp-idf/examples/bluetooth/nimble/bleprph
idf.py set-target esp32s3
idf.py build flash monitor
```

---

### 7.3 Verifying Communication Buses

After flashing, verify each bus is functional:

**I²C scan (Zephyr — nRF5340):**
```c
// In your Zephyr application main.c
#include <zephyr/drivers/i2c.h>

const struct device *i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));

void i2c_scan(void) {
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        uint8_t dummy;
        if (i2c_read(i2c_dev, &dummy, 0, addr) == 0) {
            printk("I2C device found at 0x%02X\n", addr);
        }
    }
}
```

**SPI loopback test (Zephyr):**
```c
#include <zephyr/drivers/spi.h>

const struct device *spi_dev = DEVICE_DT_GET(DT_NODELABEL(spi1));

static const struct spi_config spi_cfg = {
    .frequency = 1000000,
    .operation = SPI_OP_MODE_MASTER | SPI_WORD_SET(8),
};

// Connect MOSI to MISO for loopback test
uint8_t tx_buf[] = {0xAA, 0x55};
uint8_t rx_buf[2] = {0};
struct spi_buf tx = {.buf = tx_buf, .len = 2};
struct spi_buf rx = {.buf = rx_buf, .len = 2};
struct spi_buf_set tx_set = {.buffers = &tx, .count = 1};
struct spi_buf_set rx_set = {.buffers = &rx, .count = 1};

spi_transceive(spi_dev, &spi_cfg, &tx_set, &rx_set);
// rx_buf should equal tx_buf if loopback is correct
```

---

### 7.4 Pin Assignments

The following table shows recommended pin assignments for the nRF5340 DK:

| Signal | nRF5340 DK Pin | Sensor |
|---|---|---|
| SPI1 MOSI | P0.26 | MAX30003, ADS1298R, ICM-42688-P |
| SPI1 MISO | P0.27 | MAX30003, ADS1298R, ICM-42688-P |
| SPI1 CLK | P0.25 | MAX30003, ADS1298R, ICM-42688-P |
| SPI1 CS0 | P0.24 | MAX30003 |
| SPI1 CS1 | P0.23 | ICM-42688-P |
| SPI1 CS2 | P0.22 | ADS1298R / AFE4300 |
| I²C0 SDA | P0.06 | MAX30102, STS40-AD |
| I²C0 SCL | P0.07 | MAX30102, STS40-AD |
| MAX30003 INT | P0.20 | ECG data-ready interrupt |
| ICM-42688 INT | P0.19 | IMU data-ready interrupt |
| BQ25895 INT | P0.18 | Charger status interrupt |
| GND | GND | All sensors |
| 3.3 V | 3V3 | All sensors |

> Adapt pin assignments as needed for the ESP32-S3 DevKit GPIO map.

---

## 8. Step 3 — Sensor Integration

### 8.1 ECG — MAX30003

**Interface:** SPI (up to 10 MHz)  
**Supply:** 1.8 V (digital) + 1.8–3.6 V (analog) — many breakout boards include a level-shifter and regulator for 3.3 V operation.

#### Wiring

| MAX30003 Pin | MCU Pin | Notes |
|---|---|---|
| MOSI (SDI) | SPI MOSI | |
| MISO (SDO) | SPI MISO | |
| SCLK | SPI CLK | |
| /CS | GPIO CS0 | Active-low |
| INT | GPIO INT | Data-ready interrupt |
| VCAP1, VCAP2 | — | 4.7 µF cap to GND each |
| VECO | — | 100 nF cap to GND |
| ECGP, ECGN | ECG lead wires | Right arm (RA) and left arm (LA) |
| RBIAS | — | 200 MΩ pull-up to VMID (see datasheet) |
| GND | GND | |
| 3.3 V | 3.3 V | |

#### Electrode Placement (Single-Lead)

```
Right Arm (RA) ──── ECGP ─── MAX30003
Left Arm (LA)  ──── ECGN ─── MAX30003

Placement on body:
  RA electrode → Right subclavian / infraclavicular area
  LA electrode → Left lower chest / V5 position
  (Refer to Lead I configuration)
```

#### Initialization Code (Zephyr SPI — simplified)

```c
#define MAX30003_SYNCH     0x09
#define MAX30003_CNFG_GEN  0x10
#define MAX30003_CNFG_ECG  0x15

// Write register
void max30003_write_reg(uint8_t reg, uint32_t val) {
    uint8_t tx[4] = {
        (reg << 1) | 0x00,  // write
        (val >> 16) & 0xFF,
        (val >>  8) & 0xFF,
        (val      ) & 0xFF,
    };
    // assert CS, send tx, deassert CS
}

// Example: Set 512 Hz ECG, 0.5 Hz HPF, gain = ×20
max30003_write_reg(MAX30003_CNFG_ECG, 0x805000);
max30003_write_reg(MAX30003_SYNCH, 0x000000);
```

---

### 8.2 Multi-lead ECG — ADS1298R (Optional)

**Interface:** SPI (up to 20 MHz)  
**Supply:** 3.3 V or 5 V analog, 1.8 V digital IO (level-shifted on most breakouts)

The ADS1298R provides 8 simultaneous 24-bit ECG channels — ideal for 3-lead or 12-lead acquisition.

#### Key Wiring Points

- Connect `CLKSEL` to 3.3 V to use internal 2.048 MHz oscillator.
- Connect `START` pin to a GPIO to begin continuous conversion.
- Use the `DRDY` interrupt pin to trigger SPI burst reads.
- Power `AVDD` and `DVDD` from separate, clean 3.3 V supplies if possible (use ferrite bead isolation on breakout if available).

#### Channel-to-Electrode Mapping (Example — 3-Lead)

| ADS1298R Channel | Electrode | Limb Lead |
|---|---|---|
| IN1P / IN1N | RA / LA | Lead I |
| IN2P / IN2N | RA / LL | Lead II |
| IN3P / IN3N | LA / LL | Lead III |

---

### 8.3 Bio-impedance + ECG — AFE4300 (Optional)

**Interface:** SPI  
**Supply:** 3.3 V

The AFE4300 combines ECG acquisition and bio-impedance analysis (BIA) for hydration and body composition estimation.

- Configure the AFE4300 in **BIA mode** by setting `AFE_CTL` register bits appropriately.
- Apply a low-level AC excitation signal (typically 50 kHz, < 1 mA rms) between `IOUTP`/`IOUTN` electrodes.
- Measure the resulting voltage between `VINP`/`VINN` sensing electrodes.
- For combined ECG + BIA, use the time-multiplexed mode.

> Refer to the [AFE4300 datasheet](https://www.ti.com/lit/ds/symlink/afe4300.pdf) for full register map and BIA electrode configuration.

---

### 8.4 SpO₂ / Heart Rate — MAX30102

**Interface:** I²C (400 kHz Fast Mode)  
**I²C Address:** `0x57`  
**Supply:** 3.3 V (VDD), 5 V or 3.3 V (LED supply VLED — check breakout)

#### Wiring

| MAX30102 Pin | MCU Pin |
|---|---|
| SDA | I²C SDA |
| SCL | I²C SCL |
| INT | GPIO (optional, for FIFO threshold) |
| VDD | 3.3 V |
| VLED | 3.3 V–5 V (check breakout) |
| GND | GND |

#### Initialization Code

```c
#include <zephyr/drivers/i2c.h>

#define MAX30102_ADDR     0x57
#define REG_MODE_CONFIG   0x09
#define REG_SPO2_CONFIG   0x0A
#define REG_LED1_PA       0x0C  // Red LED
#define REG_LED2_PA       0x0D  // IR LED

void max30102_init(const struct device *i2c_dev) {
    // Reset
    i2c_reg_write_byte(i2c_dev, MAX30102_ADDR, 0x09, 0x40);
    k_msleep(50);

    // SpO2 mode (RED + IR), 100 sps, 411 µs pulse width
    i2c_reg_write_byte(i2c_dev, MAX30102_ADDR, REG_MODE_CONFIG, 0x03);
    i2c_reg_write_byte(i2c_dev, MAX30102_ADDR, REG_SPO2_CONFIG, 0x27);

    // LED current: ~6.4 mA each
    i2c_reg_write_byte(i2c_dev, MAX30102_ADDR, REG_LED1_PA, 0x20);
    i2c_reg_write_byte(i2c_dev, MAX30102_ADDR, REG_LED2_PA, 0x20);
}
```

#### Skin Placement

- The MAX30102 **must be flush against the skin** with no gaps.
- Apply light pressure (compression sleeve contact).
- Ideal location: fingertip, earlobe, or inner wrist over radial artery.
- Avoid placement over tendons or bony prominences.

---

### 8.5 Skin Temperature — Sensirion STS40-AD

**Interface:** I²C (400 kHz or 1 MHz)  
**I²C Address:** `0x44` (default)  
**Supply:** 1.8–3.6 V

#### Wiring

| STS40 Pin | MCU Pin |
|---|---|
| SDA | I²C SDA |
| SCL | I²C SCL |
| VDD | 3.3 V |
| GND | GND |

#### Reading Temperature

```c
#define STS40_ADDR         0x44
#define CMD_MEAS_HIGH_REP  0xFD  // high repeatability, no clock stretching

void sts40_read_temperature(const struct device *i2c_dev, float *temp_c) {
    uint8_t cmd = CMD_MEAS_HIGH_REP;
    uint8_t data[6];

    i2c_write(i2c_dev, &cmd, 1, STS40_ADDR);
    k_msleep(10);  // measurement time ~8.5 ms
    i2c_read(i2c_dev, data, 6, STS40_ADDR);

    uint16_t raw_temp = (data[0] << 8) | data[1];
    *temp_c = -45.0f + 175.0f * ((float)raw_temp / 65535.0f);
}
```

#### Placement

- Mount the STS40 on a **flexible substrate** that rests directly against the skin.
- Ensure thermal contact — avoid air gaps between the sensor and skin.

---

### 8.6 6-Axis IMU — TDK ICM-42688-P

**Interface:** SPI (up to 24 MHz) or I²C  
**Supply:** 1.71–3.6 V

#### Wiring (SPI mode — recommended for high data rates)

| ICM-42688 Pin | MCU Pin |
|---|---|
| SDI (MOSI) | SPI MOSI |
| SDO (MISO) | SPI MISO |
| SCLK | SPI CLK |
| CS | GPIO CS1 |
| INT1 | GPIO INT |
| VDD, VDDIO | 3.3 V |
| GND | GND |

> To select SPI mode, pull `CS` low before or during power-on. Leave `AP_AD0` floating or tied to GND.

#### Initialization Code

```c
#define ICM_REG_PWR_MGMT0     0x4E
#define ICM_REG_ACCEL_CONFIG0 0x50
#define ICM_REG_GYRO_CONFIG0  0x4F

void icm42688_init(void) {
    // Exit sleep, enable accel + gyro
    icm42688_write_reg(ICM_REG_PWR_MGMT0, 0x0F);
    k_msleep(1);

    // Accel: ±8 g, 1 kHz ODR
    icm42688_write_reg(ICM_REG_ACCEL_CONFIG0, 0x26);

    // Gyro: ±2000 dps, 1 kHz ODR
    icm42688_write_reg(ICM_REG_GYRO_CONFIG0, 0x06);
}
```

#### Placement

- Mount the IMU on the **most rigid part** of the wearable (e.g., the enclosure shell, not fabric).
- Align axes with the anatomical reference frame (X = medial-lateral, Y = anterior-posterior, Z = vertical).
- Record the mounting orientation in firmware for correct coordinate transformation.

---

## 9. Step 4 — Wearable Mechanical Integration

### 9.1 Choose Your Platform

#### Option A — 3D-Printed Enclosure

1. Design the enclosure in FreeCAD, Fusion 360, or OnShape.
2. Include:
   - MCU mounting boss and screw holes.
   - Cutouts for USB charging port and power switch.
   - Sensor window for PPG (clear/transparent insert or open slot against skin).
   - Channels for ECG lead wire routing.
3. Print in **PETG** (preferred for skin-contact — more flexible and chemical-resistant than PLA).
4. Sand internal surfaces smooth; clean with IPA before use.
5. Attach enclosure to a wrist or arm strap using rivets, screws, or hook-and-loop (Velcro).

#### Option B — Compression Sleeve Integration

1. Select a lycra/neoprene compression sleeve in the correct anatomical size.
2. Sew or bond **sensor windows** (circular cutouts, ~15 mm diameter) in the PPG sensor location.
3. Insert **ECG snap receptacles** into the sleeve at electrode positions.
4. Route shielded ECG wires through sewn channels along the sleeve seams.
5. Create a rigid **sensor pod** (small 3D-printed clip) to hold the MCU breakout board.
6. Attach the sensor pod to the compression sleeve using Velcro or snaps.

---

### 9.2 ECG Electrode Placement Diagram

```
Front View (left side of body):

  [RA electrode]         [LA electrode]
  Right subclavicular    Left V5 / lower chest
        │                       │
        └──── Shielded wire ─────┘
                    │
              MAX30003 / ADS1298R
```

**Electrode application:**
1. Clean skin with alcohol wipe.
2. Allow to dry completely (10–15 seconds).
3. Remove adhesive backing from Ag/AgCl electrode.
4. Apply firmly, pressing center first then edges.
5. Attach ECG snap lead connector.

---

### 9.3 PPG Sensor Placement

- The MAX30102 should be positioned over the **radial artery at the inner wrist**, or on the inner aspect of the forearm.
- Use a foam gasket (2–3 mm thickness) cut in a ring shape to surround the sensor and prevent ambient light leakage.
- Secure with a silicone wrist band that maintains constant 20–30 g of pressure.

---

### 9.4 IMU Placement

- Mount the ICM-42688-P on the **dorsal (back) surface** of the wrist or the lateral surface of the forearm enclosure.
- Use a thin adhesive foam pad to isolate from vibration transmitted through the PCB/enclosure mounting surface.

---

## 10. Step 5 — Firmware Development

### 10.1 Firmware Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐ │
│  │ BLE GATT │  │ Data Logger│  │  Signal Processor    │ │
│  │ Service  │  │ (SD/Flash) │  │  (filter, HR, SpO₂) │ │
│  └────┬─────┘  └─────┬──────┘  └──────────┬───────────┘ │
│       │               │                    │              │
│  ┌────┴───────────────┴────────────────────┴───────────┐ │
│  │               Sensor Manager / RTOS Tasks            │ │
│  └────┬──────────┬──────────┬──────────┬───────────────┘ │
│       │          │          │          │                  │
│  ┌────┴───┐ ┌────┴───┐ ┌───┴────┐ ┌───┴────┐            │
│  │MAX30003│ │MAX30102│ │STS40  │ │ICM42688│            │
│  │ Driver │ │ Driver │ │ Driver│ │ Driver │            │
│  └────────┘ └────────┘ └───────┘ └────────┘            │
└─────────────────────────────────────────────────────────┘
```

### 10.2 RTOS Task Structure (Zephyr)

```c
// Define task priorities and stack sizes
#define ECG_TASK_PRIORITY     2
#define PPG_TASK_PRIORITY     3
#define IMU_TASK_PRIORITY     4
#define BLE_TASK_PRIORITY     5
#define LOGGER_TASK_PRIORITY  6

// ECG acquisition task (triggered by MAX30003 INT)
void ecg_task(void *p1, void *p2, void *p3) {
    while (1) {
        k_sem_take(&ecg_data_ready, K_FOREVER);
        max30003_read_fifo(ecg_buffer, ECG_FIFO_DEPTH);
        add_timestamp(ecg_buffer);
        k_msgq_put(&ecg_queue, ecg_buffer, K_NO_WAIT);
    }
}

// PPG / SpO2 task (100 Hz polling)
void ppg_task(void *p1, void *p2, void *p3) {
    while (1) {
        max30102_read_fifo(ppg_buffer);
        k_msgq_put(&ppg_queue, ppg_buffer, K_NO_WAIT);
        k_msleep(10);  // 100 Hz
    }
}

// IMU task (1 kHz, triggered by ICM INT)
void imu_task(void *p1, void *p2, void *p3) {
    while (1) {
        k_sem_take(&imu_data_ready, K_FOREVER);
        icm42688_read_accel_gyro(&imu_sample);
        k_msgq_put(&imu_queue, &imu_sample, K_NO_WAIT);
    }
}

K_THREAD_DEFINE(ecg_tid, 1024, ecg_task, NULL, NULL, NULL, ECG_TASK_PRIORITY, 0, 0);
K_THREAD_DEFINE(ppg_tid, 1024, ppg_task, NULL, NULL, NULL, PPG_TASK_PRIORITY, 0, 0);
K_THREAD_DEFINE(imu_tid, 1024, imu_task, NULL, NULL, NULL, IMU_TASK_PRIORITY, 0, 0);
```

---

### 10.3 Timestamping

Use the MCU's hardware timer to generate microsecond-resolution timestamps for each sample:

```c
#include <zephyr/drivers/counter.h>

const struct device *timer = DEVICE_DT_GET(DT_NODELABEL(timer0));
uint32_t get_timestamp_us(void) {
    uint32_t ticks;
    counter_get_value(timer, &ticks);
    return counter_ticks_to_us(timer, ticks);
}
```

Store each sample as:
```c
typedef struct {
    uint32_t timestamp_us;
    uint8_t  sensor_id;
    uint8_t  data[MAX_PAYLOAD_LEN];
} sensor_packet_t;
```

---

### 10.4 BLE GATT Service Design

Define custom GATT characteristics for each signal stream:

| Characteristic | UUID (16-bit example) | Properties | Format |
|---|---|---|---|
| ECG Stream | 0xAA01 | Notify | int16[N], 512 Hz |
| PPG Red Stream | 0xAA02 | Notify | int32[N], 100 Hz |
| PPG IR Stream | 0xAA03 | Notify | int32[N], 100 Hz |
| SpO₂ | 0xAA04 | Notify | uint8, 1 Hz |
| Heart Rate | 0x2A37 | Notify | uint8 (standard HR UUID) |
| Temperature | 0x2A1C | Notify | int16 (0.01 °C resolution) |
| IMU Accel | 0xAA05 | Notify | int16[3], 100 Hz |
| IMU Gyro | 0xAA06 | Notify | int16[3], 100 Hz |
| Battery Level | 0x2A19 | Read/Notify | uint8 (%) |

**BLE MTU:** Request MTU of 247 bytes and use packet batching to achieve adequate throughput at 2 Mbps PHY.

---

### 10.5 SD Card Data Logging (Optional)

If an SD card module is attached via SPI:

```c
#include <zephyr/fs/fs.h>
#include <ff.h>

// Write binary data to timestamped file
void log_sample(sensor_packet_t *pkt) {
    static struct fs_file_t log_file;
    fs_write(&log_file, pkt, sizeof(sensor_packet_t));
}
```

File format recommendation: **Binary packed structs** (not JSON) to minimize write latency and storage size. Post-process to CSV or EDF on the host.

---

## 11. Step 6 — Testing & Validation

### 11.1 Bench Testing Checklist

Before attaching to a human subject, complete all bench tests:

- [ ] Power rail voltages verified (3.3 V ± 0.1 V)
- [ ] Power rail ripple < 10 mVpp on oscilloscope
- [ ] I²C bus scan confirms MAX30102 at `0x57`, STS40 at `0x44`
- [ ] SPI communication verified with each sensor (read device ID registers)
- [ ] MAX30003 returns ECG FIFO data at expected rate (512 Hz)
- [ ] MAX30102 returns RED and IR counts (> 50,000 counts in good contact)
- [ ] STS40 returns plausible temperature (22–26 °C at room temperature)
- [ ] ICM-42688-P returns accel values ≈ ±1 g on Z axis when flat
- [ ] BLE advertising visible on a mobile phone
- [ ] BLE GATT connection and characteristic notification working

---

### 11.2 ECG Signal Quality Test

1. Connect ECG electrodes to your forearms (standard Lead I placement).
2. Stream ECG data over BLE to a laptop/PC.
3. Plot ECG waveform in real time (Python + matplotlib, or use nRF Connect app).
4. Verify:
   - P, QRS, T waves visible.
   - Baseline noise < 50 µV rms (< 0.5 mV peak-to-peak).
   - No 50/60 Hz power line interference (should be suppressed by MAX30003 analog filter + digital notch).
   - Heart rate detectable via R-R interval.

**Expected waveform:**
```
   R
   │
  ╱│╲
 ╱ │ ╲
P  │  T
╱  │   ╲___
───┘
   Q  S
```

---

### 11.3 PPG / SpO₂ Signal Quality Test

1. Place MAX30102 against the fingertip (bench test only).
2. Verify RED and IR raw signals show pulsatile waveforms at resting heart rate (50–100 BPM).
3. Calculate AC/DC ratio for each channel:
   - `AC_RED / DC_RED` and `AC_IR / DC_IR`
   - Ratio of Ratios `R = (AC_RED/DC_RED) / (AC_IR/DC_IR)`
   - SpO₂ ≈ 110 − 25 × R (simplified Masimo-like formula for development purposes only)
4. Compare SpO₂ reading against a clinical pulse oximeter (target: within ±2% of reference).

---

### 11.4 Motion Artifact Testing

1. Collect ECG and PPG signals while the subject is at rest (baseline).
2. Collect signals while the subject performs slow arm movements, walking, and rapid wrist movements.
3. Evaluate SNR degradation during motion.
4. Use IMU data to detect motion epochs and flag or discard corrupted signal segments.

---

### 11.5 Battery Life Test

1. Charge battery to 100%.
2. Enable all sensors, BLE streaming at 2 Mbps, SD logging.
3. Record time to battery cutoff voltage (3.0 V).
4. Expected runtime (estimate):
   - nRF5340 + all sensors + BLE: **8–16 hours** on 500 mAh at 30–60 mA average draw.
   - Optimize by reducing sensor ODRs, using BLE connection events, and MCU sleep modes.

---

### 11.6 BLE Throughput Test

1. Enable all BLE notifications at maximum data rate.
2. Measure actual throughput using a BLE sniffer (Wireshark + nRF Sniffer adapter).
3. Target: > 200 kbps sustained for full ECG + PPG + IMU streaming.
4. If throughput is insufficient, increase BLE connection interval, use 2 Mbps PHY, or increase MTU.

---

## 12. Step 7 — Data Logging & Wireless Streaming

### 12.1 Mobile App Integration

**Option A — nRF Connect App (Nordic)**
- Available for iOS and Android.
- Connects to BLE GATT and displays raw characteristic values.
- Export data as CSV for offline analysis.

**Option B — Custom App (React Native / Flutter)**
- Subscribe to BLE notifications using platform BLE libraries.
- Display real-time waveforms (ECG, PPG) using scrolling chart components.
- Store data locally and optionally upload to cloud (AWS IoT / Firebase).

**Option C — Python Desktop Tool (Development)**
```python
import asyncio
from bleak import BleakClient

ECG_CHAR_UUID  = "0000aa01-0000-1000-8000-00805f9b34fb"
DEVICE_ADDRESS = "XX:XX:XX:XX:XX:XX"  # Replace with your device MAC

def ecg_callback(sender, data):
    samples = [int.from_bytes(data[i:i+2], 'little', signed=True)
               for i in range(0, len(data), 2)]
    print(f"ECG samples: {samples}")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        await client.start_notify(ECG_CHAR_UUID, ecg_callback)
        await asyncio.sleep(60)  # Stream for 60 seconds

asyncio.run(main())
```

---

### 12.2 Signal Post-Processing Pipeline

After data capture, process signals offline with the following pipeline:

```
Raw ECG
  → 0.5–40 Hz bandpass filter (Butterworth 4th order)
  → 50/60 Hz notch filter
  → Pan-Tompkins QRS detector
  → R-R interval extraction
  → Heart rate variability (HRV) metrics

Raw PPG
  → 0.5–10 Hz bandpass filter
  → AC/DC decomposition
  → SpO2 calculation (R-of-Ratios)
  → Pulse rate extraction

IMU
  → Complementary filter (accel + gyro)
  → Posture detection (angle thresholds)
  → Motion artifact flag (when |acceleration| > 1.2 g)
```

---

## 13. Troubleshooting Guide

| Symptom | Likely Cause | Solution |
|---|---|---|
| No 3.3 V rail | LDO not powered or wiring error | Check BQ25895 SYS output; verify LDO input connections |
| Sensor not found on I²C scan | Wrong address, missing pull-ups, or wiring error | Verify 4.7 kΩ pull-up on SDA/SCL; check I²C address in datasheet |
| ECG waveform flatline | No skin contact, electrode detached, or CS wiring error | Re-attach electrodes; probe MAX30003 INT pin for toggling |
| ECG excessive noise / 60 Hz | Unshielded lead wires; missing right-leg drive (RLD) | Use shielded leads; add driven-right-leg circuit for noise rejection |
| PPG: no pulsatile signal | Sensor not against skin, excessive ambient light | Improve optical contact; add foam light shield |
| PPG: SpO₂ always ~85% | IR and RED LEDs may be swapped | Verify RED = register 0x0C, IR = register 0x0D on MAX30102 |
| IMU: all zeros | SPI mode not enabled (I²C default) | Pull CS low at power-on; verify SPI wiring |
| BLE not advertising | Firmware not started, antenna blocked | Check firmware startup; move device away from metal surfaces |
| BLE drops connection | Interference or too-short connection interval | Move device to 2.4 GHz-clear environment; increase connection interval |
| Battery draining in < 2 hrs | All sensors at full ODR, BLE at max duty | Reduce IMU ODR; use BLE sleep modes; disable unused sensors |
| Short circuit on power rail | Solder bridge or wrong wire connection | Inspect under magnifier; measure rail impedance to GND with power off |

---

## 14. Next Steps: Moving to Custom PCB

Once the prototype is validated and signal quality meets requirements, the next phase is a custom-designed PCB:

### 14.1 PCB Design Guidelines

1. **Analog ground plane separation** — separate AGND (ECG AFE, PPG) from DGND (MCU, SPI bus), joined at a single star point.
2. **Power supply filtering** — use ferrite beads + capacitors between digital and analog power rails.
3. **ECG input protection** — add 1 MΩ series resistors and TVS diodes on ECG input lines.
4. **Shielding** — place copper pour guard ring around ECG AFE and PPG sensor areas.
5. **Component placement** — keep ECG AFE as far as possible from switching regulators and clock sources.
6. **Flex PCB or rigid-flex** — consider a two-part design: rigid MCU board + flexible sensor strip.

### 14.2 Recommended EDA Tools

| Tool | License | Notes |
|---|---|---|
| KiCad | Free/Open Source | Full schematic + PCB layout |
| Altium Designer | Commercial | Industry standard |
| EasyEDA / LCSC | Free (with JLCPCB) | Fast prototyping, low cost |

### 14.3 Pre-Production Checklist

- [ ] PCB design rule check (DRC) passed
- [ ] Schematic review against all sensor datasheets
- [ ] Signal integrity simulation (ECG analog front end)
- [ ] EMC pre-compliance testing
- [ ] IEC 60601-1 safety review (if pursuing medical certification)
- [ ] Environmental testing: temperature cycling, humidity
- [ ] User study: comfort, wearability, motion artifact in field conditions

---

## Appendix A — Useful Resources

| Resource | URL |
|---|---|
| MAX30003 Datasheet | https://www.analog.com/media/en/technical-documentation/data-sheets/max30003.pdf |
| ADS1298R Datasheet | https://www.ti.com/lit/ds/symlink/ads1298r.pdf |
| AFE4300 Datasheet | https://www.ti.com/lit/ds/symlink/afe4300.pdf |
| MAX30102 Datasheet | https://www.analog.com/media/en/technical-documentation/data-sheets/max30102.pdf |
| STS40-AD Datasheet | https://sensirion.com/media/documents/2FE3F2B4/61641F3A/Sensirion_Datasheet_STS4x.pdf |
| ICM-42688-P Datasheet | https://invensense.tdk.com/download-pdf/icm-42688-p-datasheet/ |
| BQ25895 Datasheet | https://www.ti.com/lit/ds/symlink/bq25895.pdf |
| Nordic nRF5340 DK | https://www.nordicsemi.com/Products/Development-hardware/nRF5340-DK |
| ESP32-S3 DevKit | https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/ |
| nRF Connect SDK | https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/index.html |
| Bleak (Python BLE) | https://bleak.readthedocs.io |

---

## Appendix B — Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | 2026-04-06 | — | Initial release — developmental prototype guide |

---

*This document describes a developmental prototype intended for R&D purposes only. It is not a certified medical device. Do not use for clinical diagnosis or treatment decisions.*
