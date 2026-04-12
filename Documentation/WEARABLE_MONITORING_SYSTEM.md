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
13. [Step 8 — AI / Machine Learning Integration](#13-step-8--ai--machine-learning-integration)
    - 13.1 [AI Architecture Overview](#131-ai-architecture-overview)
    - 13.2 [Phase 1 — Data Collection & Labelling](#132-phase-1--data-collection--labelling)
    - 13.3 [Phase 2 — Feature Engineering](#133-phase-2--feature-engineering)
    - 13.4 [Phase 3 — Model Training](#134-phase-3--model-training)
    - 13.5 [Phase 4 — On-Device Inference (Edge AI)](#135-phase-4--on-device-inference-edge-ai)
    - 13.6 [Phase 5 — Cloud AI Pipeline](#136-phase-5--cloud-ai-pipeline)
    - 13.7 [AI Use Cases & Target Models](#137-ai-use-cases--target-models)
    - 13.8 [AI Validation & Testing](#138-ai-validation--testing)
    - 13.9 [AI Development Checklist](#139-ai-development-checklist)
14. [Troubleshooting Guide](#14-troubleshooting-guide)
15. [Next Steps: Moving to Custom PCB](#15-next-steps-moving-to-custom-pcb)

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
┌─────────────────────────────────────────────────────────────────┐
│                   Li-ion Battery (500–1000 mAh)                  │
│                         │                                        │
│                  BQ25895 Charger                                  │
│                         │                                        │
│               3.3 V LDO Regulator                                 │
│                         │                                        │
│         ┌───────────────┼───────────────┐                         │
│         │               │               │                         │
│   MCU (nRF5340 DK   or ESP32-S3)        │                         │
│   ├── SPI Bus                           │                         │
│   │   ├── MAX30003 (ECG)                │                         │
│   │   ├── ADS1298R (multi-lead ECG*)    │                         │
│   │   ├── AFE4300  (bio-impedance*)     │                         │
│   │   └── ICM-42688-P (IMU)            │                         │
│   └── I²C Bus                          │                         │
│       ├── MAX30102 (SpO₂/HR)           │                         │
│       └── STS40-AD (Temperature)       │                         │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │            Edge AI Layer (On-Device Inference)           │    │
│   │  TFLite Micro / Edge Impulse runtime                     │    │
│   │  ├── Arrhythmia detector  (ECG CNN/LSTM)                 │    │
│   │  ├── SpO₂ anomaly flag    (PPG threshold + ML)           │    │
│   │  ├── Activity classifier  (IMU CNN)                      │    │
│   │  ├── Fall detector        (IMU threshold + ML)           │    │
│   │  └── Motion artifact gate (IMU → ECG/PPG quality)       │    │
│   └──────────────────────────┬──────────────────────────────┘    │
│                               │                                   │
│   BLE 5.x ────────────────────┴──────────────────►               │
│   (raw signals + AI inference results + SD logging)               │
│                               │                                   │
│                     ┌─────────┴──────────┐                        │
│                     │   Mobile App        │                        │
│                     │ (real-time display) │                        │
│                     └─────────┬──────────┘                        │
│                               │  Wi-Fi / LTE                      │
│                     ┌─────────┴──────────┐                        │
│                     │  Cloud AI Pipeline  │                        │
│                     │ (retraining, fleet  │                        │
│                     │  analytics, alerts) │                        │
│                     └────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘

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
  → AI model input (see Section 13)

Raw PPG
  → 0.5–10 Hz bandpass filter
  → AC/DC decomposition
  → SpO2 calculation (R-of-Ratios)
  → Pulse rate extraction
  → AI model input (see Section 13)

IMU
  → Complementary filter (accel + gyro)
  → Posture detection (angle thresholds)
  → Motion artifact flag (when |acceleration| > 1.2 g)
  → Activity classification AI model input (see Section 13)
```

> For on-device real-time AI inference and the full cloud AI training pipeline, see **[Step 8 — AI / Machine Learning Integration](#13-step-8--ai--machine-learning-integration)**.

---

## 13. Step 8 — AI / Machine Learning Integration

### 13.1 AI Architecture Overview

The AI layer sits between raw sensor data and clinical/user-facing outputs. It operates at two levels:

```
┌──────────────────────────────────────────────────────────────┐
│  LEVEL 1 — Edge AI (On-Device, Real-Time)                     │
│  Runs directly on the nRF5340 / ESP32-S3                      │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Motion Artifact│  │ Activity / Fall   │  │ Arrhythmia   │ │
│  │ Gate           │  │ Classifier (IMU)  │  │ Screener     │ │
│  │ (IMU → ECG/PPG)│  │ TFLite Micro      │  │ (ECG LSTM)   │ │
│  └────────────────┘  └──────────────────┘  └───────────────┘ │
└──────────────────────────────┬───────────────────────────────┘
                                │  BLE — labeled inferences
┌──────────────────────────────┴───────────────────────────────┐
│  LEVEL 2 — Cloud AI (Server / Mobile, Offline + Online)       │
│  Runs on mobile app backend or cloud server                   │
│  ┌────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ SpO₂ Trend     │  │ HRV / Stress     │  │ Model Re-     │ │
│  │ Anomaly Detect │  │ Analysis         │  │ training Loop │ │
│  └────────────────┘  └──────────────────┘  └───────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Design principle:** Keep latency-critical, safety-critical inferences (motion artifact gating, arrhythmia screening) on-device. Push compute-heavy, personalization, and trend analysis to the cloud.

---

### 13.2 Phase 1 — Data Collection & Labelling

Before training any model you need a labelled dataset. Use the prototype itself to collect data.

#### 13.2.1 Data Collection Setup

1. Set up the Python BLE streaming tool from Section 12.1 to record raw binary packets to disk.
2. Record sessions covering all target conditions:

| Condition | Duration | Notes |
|---|---|---|
| Resting (sitting) | 5 min | Baseline ECG, PPG, temperature |
| Resting (supine) | 5 min | Baseline + postural comparison |
| Walking (3–5 km/h) | 5 min | Motion artifact source |
| Running (8–10 km/h) | 5 min | High-intensity motion artifact |
| Stair climbing | 3 min | Sudden acceleration events |
| Simulated arrhythmia* | — | Use synthetic ECG signal injector |
| Low SpO₂ simulation* | — | Breath-holding (see note below) |

> **Safety note:** Do not deliberately induce hypoxia for data collection. Use public open-access datasets for SpO₂ anomaly ground truth (PhysioNet MIMIC, MESA).

#### 13.2.2 Open-Access Datasets

Supplement your own recordings with established benchmark datasets:

| Dataset | Signals | URL |
|---|---|---|
| PhysioNet MIT-BIH Arrhythmia | ECG | https://physionet.org/content/mitdb/ |
| PhysioNet MESA | ECG, SpO₂, IMU | https://sleepdata.org/datasets/mesa |
| PTB-XL | 12-lead ECG | https://physionet.org/content/ptb-xl/ |
| BIDMC PPG + Resp | PPG, ECG, SpO₂ | https://physionet.org/content/bidmc/ |
| UCI HAR (Activity) | IMU (Accel + Gyro) | https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones |
| MoRe-Fall (Fall Detection) | IMU | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6406321/ |

#### 13.2.3 Data Labelling

Use annotation tools to label segments:

| Tool | Purpose | URL |
|---|---|---|
| Label Studio | General time-series labelling | https://labelstud.io |
| WFDB Viewer | ECG waveform annotation | https://physionet.org/content/wfdb-python/ |
| SigViewer | ECG / BioSignal annotation | https://github.com/cbrnr/sigviewer |

Label at minimum:
- ECG: **Normal sinus rhythm**, **Atrial fibrillation**, **Premature ventricular contraction (PVC)**, **Noise/artifact**
- PPG: **Good contact**, **Motion artifact**, **Low perfusion**
- IMU: **Stationary**, **Walking**, **Running**, **Stair climbing**, **Fall**, **Unknown**

---

### 13.3 Phase 2 — Feature Engineering

Extract features from the labelled signals before model training.

#### 13.3.1 ECG Features

```python
import numpy as np
import neurokit2 as nk

def extract_ecg_features(ecg_signal, fs=512):
    """Extract time-domain and frequency-domain HRV features from ECG."""
    # Clean and find R-peaks
    ecg_cleaned = nk.ecg_clean(ecg_signal, sampling_rate=fs)
    _, rpeaks = nk.ecg_peaks(ecg_cleaned, sampling_rate=fs)

    # HRV time-domain features
    hrv_time = nk.hrv_time(rpeaks, sampling_rate=fs)

    # HRV frequency-domain features
    hrv_freq = nk.hrv_frequency(rpeaks, sampling_rate=fs)

    # Morphology features (QRS width, PR interval, QT interval)
    _, waves = nk.ecg_delineate(ecg_cleaned, rpeaks, sampling_rate=fs)

    features = {
        "mean_rr":   hrv_time["HRV_MeanNN"].values[0],
        "sdnn":      hrv_time["HRV_SDNN"].values[0],
        "rmssd":     hrv_time["HRV_RMSSD"].values[0],
        "pnn50":     hrv_time["HRV_pNN50"].values[0],
        "lf_power":  hrv_freq["HRV_LF"].values[0],
        "hf_power":  hrv_freq["HRV_HF"].values[0],
        "lf_hf":     hrv_freq["HRV_LFHF"].values[0],
    }
    return features
```

#### 13.3.2 PPG Features

```python
def extract_ppg_features(red_signal, ir_signal, fs=100):
    """Extract SpO2, pulse rate, perfusion index from raw PPG."""
    # AC/DC decomposition
    from scipy.signal import butter, filtfilt

    def bandpass(sig, low=0.5, high=10, fs=fs):
        b, a = butter(4, [low/(fs/2), high/(fs/2)], btype='band')
        return filtfilt(b, a, sig)

    red_ac = bandpass(red_signal)
    ir_ac  = bandpass(ir_signal)

    red_dc = np.mean(red_signal)
    ir_dc  = np.mean(ir_signal)

    # Ratio of ratios → SpO2 (calibration needed for clinical accuracy)
    R = (np.std(red_ac) / red_dc) / (np.std(ir_ac) / ir_dc)
    spo2_estimate = 110.0 - 25.0 * R  # simplified formula for R&D only

    # Perfusion index
    pi = (np.ptp(ir_ac) / ir_dc) * 100

    return {"spo2_estimate": spo2_estimate, "perfusion_index": pi}
```

#### 13.3.3 IMU Features (Activity Classification)

```python
def extract_imu_features(accel_xyz, gyro_xyz, fs=100, window_sec=2.56):
    """Extract statistical features from a sliding IMU window."""
    n = int(window_sec * fs)
    features = {}

    for i, axis in enumerate(['x', 'y', 'z']):
        a = accel_xyz[:n, i]
        g = gyro_xyz[:n, i]

        features[f"accel_{axis}_mean"]  = np.mean(a)
        features[f"accel_{axis}_std"]   = np.std(a)
        features[f"accel_{axis}_max"]   = np.max(np.abs(a))
        features[f"accel_{axis}_energy"]= np.sum(a**2) / n

        features[f"gyro_{axis}_mean"]   = np.mean(g)
        features[f"gyro_{axis}_std"]    = np.std(g)

    # Signal magnitude area (SMA) — motion intensity metric
    features["sma"] = np.sum(
        np.abs(accel_xyz[:n, 0]) +
        np.abs(accel_xyz[:n, 1]) +
        np.abs(accel_xyz[:n, 2])
    ) / n

    return features
```

---

### 13.4 Phase 3 — Model Training

#### 13.4.1 Recommended Frameworks & Tools

| Tool | Purpose | Notes |
|---|---|---|
| **Edge Impulse Studio** | End-to-end edge ML platform | Drag-and-drop pipeline; direct export to TFLite Micro / nRF SDK |
| **TensorFlow / Keras** | Model training | Full flexibility; export to TFLite for deployment |
| **PyTorch + ONNX** | Research-grade training | Export via ONNX → TFLite conversion |
| **scikit-learn** | Classical ML (SVM, RF, XGBoost) | Fast baselines; feature-based models |
| **NeuroKit2** | ECG/PPG signal processing | Python library for physiological signal feature extraction |
| **Weights & Biases** | Experiment tracking | Log training runs, hyperparameters, metrics |

#### 13.4.2 ECG Arrhythmia Screener — CNN-LSTM Model

```python
import tensorflow as tf
from tensorflow import keras

def build_ecg_cnn_lstm(input_len=1024, n_classes=4):
    """
    1D CNN + LSTM for ECG rhythm classification.
    Input:  (batch, input_len, 1) — 2-second ECG window at 512 Hz
    Output: (batch, n_classes)    — [Normal, AF, PVC, Noise]
    """
    inp = keras.Input(shape=(input_len, 1))

    # 1D CNN feature extraction
    x = keras.layers.Conv1D(32, kernel_size=7, activation='relu', padding='same')(inp)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.MaxPooling1D(2)(x)

    x = keras.layers.Conv1D(64, kernel_size=5, activation='relu', padding='same')(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.MaxPooling1D(2)(x)

    x = keras.layers.Conv1D(128, kernel_size=3, activation='relu', padding='same')(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.MaxPooling1D(2)(x)

    # LSTM temporal modelling
    x = keras.layers.LSTM(64, return_sequences=False)(x)
    x = keras.layers.Dropout(0.3)(x)

    out = keras.layers.Dense(n_classes, activation='softmax')(x)

    model = keras.Model(inp, out)
    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    return model

model = build_ecg_cnn_lstm()
model.summary()
```

**Target performance (MIT-BIH benchmark):**
- Sensitivity (AF): > 95%
- Specificity (Normal): > 97%
- Latency on nRF5340: < 20 ms per 2-second window

---

#### 13.4.3 Activity / Fall Classifier — IMU CNN

```python
def build_imu_cnn(input_len=256, n_axes=6, n_classes=6):
    """
    1D CNN for activity recognition from IMU data.
    Input:  (batch, input_len, n_axes) — 2.56 s window, 100 Hz, 6-axis
    Output: (batch, n_classes)         — [Stationary, Walk, Run, Stairs, Fall, Unknown]
    """
    inp = keras.Input(shape=(input_len, n_axes))

    x = keras.layers.Conv1D(64, kernel_size=5, activation='relu', padding='same')(inp)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.MaxPooling1D(2)(x)

    x = keras.layers.Conv1D(128, kernel_size=3, activation='relu', padding='same')(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.GlobalAveragePooling1D()(x)

    x = keras.layers.Dense(64, activation='relu')(x)
    x = keras.layers.Dropout(0.25)(x)
    out = keras.layers.Dense(n_classes, activation='softmax')(x)

    model = keras.Model(inp, out)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model
```

#### 13.4.4 HRV / Stress Regression Model

```python
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Feature vector: [sdnn, rmssd, pnn50, lf_power, hf_power, lf_hf, spo2, skin_temp]
# Target: validated stress score (e.g., from PSS questionnaire labels)

stress_model = Pipeline([
    ('scaler', StandardScaler()),
    ('regressor', GradientBoostingRegressor(n_estimators=200, max_depth=4))
])

# stress_model.fit(X_train, y_train)
```

---

#### 13.4.5 Model Quantization (Float32 → INT8 for Edge Deployment)

```python
import tensorflow as tf

def quantize_model(keras_model, representative_dataset_fn):
    """
    Post-training INT8 quantization for TFLite Micro deployment.
    representative_dataset_fn: generator yielding sample input batches.
    """
    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_dataset_fn
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type  = tf.int8
    converter.inference_output_type = tf.int8

    tflite_model = converter.convert()
    with open('ecg_arrhythmia_int8.tflite', 'wb') as f:
        f.write(tflite_model)

    print(f"Model size: {len(tflite_model) / 1024:.1f} KB")
    return tflite_model
```

**Memory budget targets for nRF5340 (512 KB RAM, 1 MB Flash):**

| Model | Flash (quantized) | RAM (activations) | Inference time |
|---|---|---|---|
| ECG arrhythmia CNN-LSTM | ~80–120 KB | ~40 KB | ~15 ms |
| IMU activity classifier CNN | ~30–50 KB | ~15 KB | ~5 ms |
| Motion artifact gate | ~10 KB | ~5 KB | ~1 ms |

---

### 13.5 Phase 4 — On-Device Inference (Edge AI)

#### 13.5.1 Option A — Edge Impulse (Recommended for Rapid Prototyping)

Edge Impulse provides a full end-to-end pipeline from data collection to on-device deployment with direct nRF5340 and ESP32-S3 board support.

**Workflow:**

```
1. Create project at studio.edgeimpulse.com
2. Connect device via Edge Impulse CLI:
   npm install -g edge-impulse-cli
   edge-impulse-daemon
3. Upload labelled sensor data from CSV/binary files
4. Configure Impulse:
   - Input block:  Raw data (ECG 512 Hz, IMU 100 Hz)
   - Processing:   Spectral features / raw
   - Learning:     Classification (Neural Network)
5. Train and validate in browser
6. Deploy → Arduino library / Zephyr module / C++ library
7. Integrate generated library into your Zephyr project
```

**Zephyr integration (Edge Impulse C++ library):**
```c
#include "edge-impulse-sdk/classifier/ei_run_classifier.h"

static float ecg_features[EI_CLASSIFIER_DSP_INPUT_FRAME_SIZE];

void run_ecg_inference(int16_t *ecg_samples, size_t n) {
    // Normalise samples to float [-1, 1]
    for (size_t i = 0; i < n; i++) {
        ecg_features[i] = ecg_samples[i] / 32768.0f;
    }

    signal_t signal;
    numpy::signal_from_buffer(ecg_features, n, &signal);

    ei_impulse_result_t result;
    EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
    if (err != EI_IMPULSE_OK) return;

    printk("ECG classification:\n");
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
        printk("  %s: %.2f\n", ei_classifier_inferencing_categories[i],
               result.classification[i].value);
    }
}
```

---

#### 13.5.2 Option B — TensorFlow Lite Micro (Manual Pipeline)

If you need full control over the model architecture and inference pipeline:

**Step 1 — Convert model to C array:**
```bash
# Convert .tflite binary to C source file
xxd -i ecg_arrhythmia_int8.tflite > ecg_model_data.cc
```

**Step 2 — Add TFLite Micro to Zephyr project (`CMakeLists.txt`):**
```cmake
# Add TFLite Micro as an external module
list(APPEND ZEPHYR_EXTRA_MODULES
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/tflite-micro
)
```

**Step 3 — Inference in firmware (C++):**
```cpp
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "ecg_model_data.h"  // generated from xxd

// Tensor arena (tune size based on model requirements)
constexpr int kTensorArenaSize = 60 * 1024;
alignas(16) uint8_t tensor_arena[kTensorArenaSize];

tflite::MicroMutableOpResolver<6> resolver;
resolver.AddConv2D();
resolver.AddDepthwiseConv2D();
resolver.AddMaxPool2D();
resolver.AddFullyConnected();
resolver.AddSoftmax();
resolver.AddReshape();

const tflite::Model* model = tflite::GetModel(ecg_model_data);
tflite::MicroInterpreter interpreter(model, resolver, tensor_arena,
                                     kTensorArenaSize);
interpreter.AllocateTensors();

TfLiteTensor* input  = interpreter.input(0);
TfLiteTensor* output = interpreter.output(0);

// Fill input tensor with ECG samples (quantized INT8)
memcpy(input->data.int8, ecg_int8_buffer, input->bytes);

interpreter.Invoke();

// Read output probabilities
int8_t* probs = output->data.int8;
int predicted_class = std::max_element(probs, probs + 4) - probs;
// 0=Normal, 1=AF, 2=PVC, 3=Noise
```

---

#### 13.5.3 Motion Artifact Gate

Before running ECG or PPG models, gate inference based on IMU motion level:

```c
#define MOTION_THRESHOLD_G  0.5f  // g — tune empirically

bool is_motion_artifact(imu_sample_t *imu) {
    float mag = sqrtf(
        imu->accel_x * imu->accel_x +
        imu->accel_y * imu->accel_y +
        imu->accel_z * imu->accel_z
    );
    // Subtract gravity component (1.0 g when stationary)
    return fabsf(mag - 1.0f) > MOTION_THRESHOLD_G;
}

void inference_manager_tick(void) {
    if (is_motion_artifact(&latest_imu)) {
        flag_sample_as_corrupted();
        return;  // skip ECG/PPG inference during high motion
    }
    run_ecg_inference(ecg_buffer, ECG_WINDOW_SAMPLES);
    run_ppg_inference(ppg_buffer, PPG_WINDOW_SAMPLES);
}
```

---

### 13.6 Phase 5 — Cloud AI Pipeline

Use the cloud for model retraining, fleet analytics, and deep trend analysis that exceeds on-device compute.

#### 13.6.1 Data Ingestion Architecture

```
Wearable Device
    │ BLE
    ▼
Mobile App (iOS/Android)
    │ HTTPS / MQTT
    ▼
Cloud Broker (AWS IoT Core / MQTT broker)
    │
    ├──► Time-Series DB (InfluxDB / AWS Timestream)
    │         └──► Grafana dashboard (real-time monitoring)
    │
    ├──► Object Storage (S3 / GCS) ← raw binary recordings
    │         └──► Batch ML Training pipeline
    │
    └──► Stream Processor (AWS Kinesis / Apache Flink)
              └──► Real-time anomaly detection microservice
```

#### 13.6.2 Anomaly Detection Microservice (Python / FastAPI)

```python
from fastapi import FastAPI
import numpy as np
import tflite_runtime.interpreter as tflite

app = FastAPI()
interpreter = tflite.Interpreter(model_path="ecg_arrhythmia_int8.tflite")
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

@app.post("/infer/ecg")
async def infer_ecg(payload: dict):
    """Receive ECG window, return arrhythmia classification."""
    samples = np.array(payload["samples"], dtype=np.float32).reshape(1, -1, 1)

    interpreter.set_tensor(input_details[0]['index'], samples)
    interpreter.invoke()

    probs = interpreter.get_tensor(output_details[0]['index'])[0]
    labels = ["Normal", "AF", "PVC", "Noise"]
    result = {labels[i]: float(probs[i]) for i in range(len(labels))}

    # Alert if AF probability exceeds threshold
    if result["AF"] > 0.85:
        trigger_alert(payload["device_id"], "Possible AF detected")

    return result

def trigger_alert(device_id: str, message: str):
    # Send push notification via FCM / APNs
    pass
```

#### 13.6.3 Continuous Model Retraining Loop

```
1. Collect new labelled data from fleet devices (opt-in users)
2. Merge with existing training set in S3
3. Trigger retraining job (AWS SageMaker / GCP Vertex AI)
4. Validate new model against held-out test set
5. If metrics improve AND pass safety checks:
   a. Quantize to INT8
   b. Package as OTA firmware update
   c. Stage-roll to 5% of fleet → monitor → expand
6. Log model version + SHA256 hash in database for audit trail
```

---

### 13.7 AI Use Cases & Target Models

| Use Case | Signals Used | Model Type | Deployment |
|---|---|---|---|
| **Arrhythmia screening** | ECG | 1D CNN-LSTM | On-device (TFLite Micro) |
| **AF detection** | ECG (RR intervals) | Threshold + SVM | On-device |
| **SpO₂ trend anomaly** | PPG, SpO₂ history | Autoencoder / z-score | Cloud |
| **Activity classification** | IMU (6-axis) | 1D CNN | On-device (TFLite Micro) |
| **Fall detection** | IMU (6-axis) | Threshold + lightweight SVM | On-device |
| **Stress / HRV analysis** | ECG (HRV features) | Gradient Boosting / LSTM | Cloud |
| **Sleep staging** | ECG, PPG, IMU | Multi-modal CNN-LSTM | Cloud |
| **Motion artifact removal** | ECG, PPG, IMU | Adaptive filter + ML gate | On-device |
| **Hydration status (BIA)** | Bio-impedance (AFE4300) | Ridge regression | Cloud |
| **Personalized baseline adaptation** | All signals | Online learning | Cloud |

---

### 13.8 AI Validation & Testing

#### 13.8.1 Model Performance Metrics

For classification models:

```python
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

def evaluate_model(y_true, y_pred, labels):
    print(classification_report(y_true, y_pred, target_names=labels))

    cm = confusion_matrix(y_true, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', xticklabels=labels, yticklabels=labels)
    plt.title("Confusion Matrix")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()
    plt.savefig("confusion_matrix.png", dpi=150)
```

**Minimum acceptable performance targets:**

| Model | Sensitivity | Specificity | F1-Score |
|---|---|---|---|
| Arrhythmia screener (AF) | ≥ 95% | ≥ 97% | ≥ 0.96 |
| Activity classifier | ≥ 90% (all classes) | — | ≥ 0.90 |
| Fall detector | ≥ 98% | ≥ 90% | ≥ 0.94 |
| Motion artifact gate | ≥ 95% | ≥ 85% | ≥ 0.90 |

#### 13.8.2 On-Device Validation

Before deploying a new model to the device, verify:

```bash
# Benchmark TFLite model on target hardware using Edge Impulse profiler
edge-impulse-run-impulse --debug

# Or use TFLite benchmark tool cross-compiled for ARM Cortex-M33 (nRF5340)
./benchmark_model \
  --graph=ecg_arrhythmia_int8.tflite \
  --num_runs=100 \
  --warmup_runs=5
```

Key metrics to capture and document:
- Average inference latency (ms)
- Peak RAM usage (KB)
- Flash storage footprint (KB)
- Power consumption during inference (mA) — measure with a current probe

#### 13.8.3 Subject-Independent Cross-Validation

To avoid over-fitting to specific individuals:

```python
from sklearn.model_selection import GroupKFold

# Groups = subject IDs — ensures no subject appears in both train and test
gkf = GroupKFold(n_splits=5)
for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=subject_ids)):
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    # train and evaluate ...
```

---

### 13.9 AI Development Checklist

**Data Collection**
- [ ] Minimum 30 minutes of labelled ECG per rhythm class per subject
- [ ] At least 10 subjects for initial model training
- [ ] Open-access dataset (MIT-BIH or PTB-XL) included in training set
- [ ] All data de-identified and stored securely

**Model Training**
- [ ] Baseline classical ML model trained and evaluated (SVM / Random Forest)
- [ ] Deep learning model trained with cross-validation
- [ ] Subject-independent evaluation confirmed (GroupKFold)
- [ ] No data leakage between train/test splits

**Quantization & Deployment**
- [ ] INT8 quantization applied with representative dataset
- [ ] Model accuracy drop after quantization < 1%
- [ ] Model fits within memory budget (Flash + RAM)
- [ ] Inference latency meets real-time requirement

**On-Device Integration**
- [ ] TFLite Micro / Edge Impulse runtime integrated into Zephyr build
- [ ] Inference task runs without starving sensor acquisition tasks
- [ ] Motion artifact gate active before ECG/PPG inference
- [ ] Inference results transmitted over BLE GATT

**Cloud Pipeline**
- [ ] Raw data ingestion to time-series DB verified
- [ ] Anomaly detection microservice deployed and tested
- [ ] Alert pipeline (push notification) tested end-to-end
- [ ] Model versioning and audit log in place

**Validation**
- [ ] Sensitivity and specificity meet targets (Section 13.8.1)
- [ ] On-device latency and memory budget confirmed
- [ ] Subject-independent cross-validation completed
- [ ] Comparison against clinical reference device documented

---

## 14. Troubleshooting Guide

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
| AI model always predicts one class | Class imbalance in training data | Apply class weights or oversample minority class (SMOTE) |
| AI inference causes BLE drops | Inference task starving BLE stack | Lower inference task priority; run inference in low-priority idle thread |

---

## 15. Next Steps: Moving to Custom PCB

Once the prototype is validated and signal quality meets requirements, the next phase is a custom-designed PCB:

### 15.1 PCB Design Guidelines

1. **Analog ground plane separation** — separate AGND (ECG AFE, PPG) from DGND (MCU, SPI bus), joined at a single star point.
2. **Power supply filtering** — use ferrite beads + capacitors between digital and analog power rails.
3. **ECG input protection** — add 1 MΩ series resistors and TVS diodes on ECG input lines.
4. **Shielding** — place copper pour guard ring around ECG AFE and PPG sensor areas.
5. **Component placement** — keep ECG AFE as far as possible from switching regulators and clock sources.
6. **Flex PCB or rigid-flex** — consider a two-part design: rigid MCU board + flexible sensor strip.

### 15.2 Recommended EDA Tools

| Tool | License | Notes |
|---|---|---|
| KiCad | Free/Open Source | Full schematic + PCB layout |
| Altium Designer | Commercial | Industry standard |
| EasyEDA / LCSC | Free (with JLCPCB) | Fast prototyping, low cost |

### 15.3 Pre-Production Checklist

- [ ] PCB design rule check (DRC) passed
- [ ] Schematic review against all sensor datasheets
- [ ] Signal integrity simulation (ECG analog front end)
- [ ] EMC pre-compliance testing
- [ ] IEC 60601-1 safety review (if pursuing medical certification)
- [ ] Environmental testing: temperature cycling, humidity
- [ ] User study: comfort, wearability, motion artifact in field conditions

---

## Appendix A — Useful Resources

### Hardware Datasheets

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

### AI / Machine Learning Resources

| Resource | URL |
|---|---|
| Edge Impulse Studio | https://studio.edgeimpulse.com |
| Edge Impulse CLI Docs | https://docs.edgeimpulse.com/docs/tools/edge-impulse-cli |
| TensorFlow Lite Micro | https://www.tensorflow.org/lite/microcontrollers |
| TFLite Model Optimization | https://www.tensorflow.org/lite/performance/post_training_quantization |
| NeuroKit2 (ECG/PPG processing) | https://neuropsychology.github.io/NeuroKit/ |
| PyTorch + ONNX export | https://pytorch.org/docs/stable/onnx.html |
| Weights & Biases | https://wandb.ai |
| Label Studio | https://labelstud.io |
| WFDB Python (ECG annotation) | https://wfdb.readthedocs.io |

### Open-Access Biosignal Datasets

| Dataset | Signals | URL |
|---|---|---|
| PhysioNet MIT-BIH Arrhythmia | ECG | https://physionet.org/content/mitdb/ |
| PTB-XL (12-lead ECG) | ECG | https://physionet.org/content/ptb-xl/ |
| BIDMC PPG + Resp | PPG, ECG, SpO₂ | https://physionet.org/content/bidmc/ |
| PhysioNet MESA | ECG, SpO₂, IMU | https://sleepdata.org/datasets/mesa |
| UCI HAR (Activity) | IMU | https://archive.ics.uci.edu/dataset/240 |

---

## Appendix B — Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | 2026-04-06 | — | Initial release — developmental prototype guide |
| 1.1 | 2026-04-12 | — | Added Step 8: full AI/ML integration section (data collection, feature engineering, model training, on-device TFLite Micro / Edge Impulse inference, cloud pipeline, validation checklist) |

---

*This document describes a developmental prototype intended for R&D purposes only. It is not a certified medical device. Do not use for clinical diagnosis or treatment decisions.*
