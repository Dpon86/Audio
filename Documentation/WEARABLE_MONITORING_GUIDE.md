# 🩺 Wearable Multi-Sensor Physiological Monitoring System
## Complete Build Guide, To-Do List & Code Implementation

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Complete Parts List (BOM)](#complete-parts-list-bom)
3. [Required Tools & Equipment](#required-tools--equipment)
4. [Master To-Do Checklist](#master-to-do-checklist)
5. [Step-by-Step Assembly Guide](#step-by-step-assembly-guide)
6. [Wiring & Pinout Reference](#wiring--pinout-reference)
7. [Firmware Architecture & Code Examples](#firmware-architecture--code-examples)
8. [Testing & Validation](#testing--validation)
9. [Troubleshooting](#troubleshooting)

---

## Project Overview

This guide walks you through building a developmental wearable prototype that captures:

| Signal | Sensor | Interface |
|--------|--------|-----------|
| ECG (single-lead) | MAX30003 | SPI |
| SpO₂ + Heart Rate (PPG) | MAX30102 | I²C |
| Skin Temperature | Sensirion STS40-AD | I²C |
| Motion / IMU (6-axis) | TDK ICM-42688-P | SPI or I²C |
| Bio-impedance (optional) | AFE4300 | SPI |
| Wireless | nRF5340 DK **or** ESP32-S3 | BLE / Wi-Fi |
| Battery Charging | BQ25895 | I²C |

---

## Complete Parts List (BOM)

### 🧠 Microcontroller (choose one)

| Component | Model | Qty | Notes |
|-----------|-------|-----|-------|
| MCU Option A | Nordic nRF5340 DK | 1 | Best for medical-grade BLE 5.3, dual-core |
| MCU Option B | ESP32-S3 DevKit | 1 | Best for Wi-Fi + BLE, more compute |

### 🔬 Sensors (Breakout Boards)

| Component | Model | Qty | Interface | Vendor |
|-----------|-------|-----|-----------|--------|
| ECG AFE (single-lead) | MAX30003EVKIT or custom breakout | 1 | SPI | Maxim/Analog Devices, Protocentral |
| SpO₂ + HR PPG | MAX30102 breakout | 1 | I²C | Protocentral, Sparkfun, DFRobot |
| Skin Temperature | STS40-AD breakout | 1 | I²C | Sensirion, Mouser |
| 6-axis IMU | ICM-42688-P breakout | 1 | SPI/I²C | SparkFun (SEN-21829), Adafruit |
| Bio-impedance (optional) | AFE4300EVM or custom | 1 | SPI | Texas Instruments, Protocentral |

### ⚡ Power System

| Component | Model | Qty | Notes |
|-----------|-------|-----|-------|
| Li-ion Battery | 3.7 V, 500–1000 mAh, JST-PH | 1 | Choose 1000 mAh for ~24 h runtime |
| Battery Charger | BQ25895 module | 1 | I²C-programmable, USB-C input |
| LDO Regulator | 3.3 V, 500 mA+ (e.g., AP2112K-3.3) | 1 | Low-noise for analog sensors |
| Power Switch | SPDT slide switch | 1 | Main power disconnect |
| Decoupling Caps | 100 nF + 10 µF ceramic | 10 | One set per sensor VDD pin |

### 🔌 Wiring & Connectors

| Component | Qty | Notes |
|-----------|-----|-------|
| Silicone jumper wires (male–male, male–female) | 40+ | Flexible, body-safe |
| JST-PH 2-pin connectors | 5 | For battery & power |
| JST-SH 4/6-pin connectors | 4 | For sensor breakouts |
| Shielded ECG lead wires (3.5 mm snap) | 1 set | Reduces EMI on ECG traces |
| Soldering iron + solder | — | Fine tip, 60/40 or lead-free |
| Heat-shrink tubing (assorted) | 1 pack | Insulate all solder joints |
| Breadboard (half-size) | 1 | Initial bench testing |
| PCB prototype board | 1–2 | For stable semi-permanent assembly |

### 🏗️ Mechanical / Wearable Hardware

| Component | Qty | Notes |
|-----------|-----|-------|
| Compression sleeve or arm band | 1 | Neoprene or spandex, size to user |
| 3D-printed enclosure (PLA/PETG) | 1 | Or flexible TPU for comfort |
| M2 brass standoffs + screws | 8 | Mount PCBs inside enclosure |
| Velcro cable ties | 10 | Manage wire routing |
| Ag/AgCl ECG electrodes + snap connectors | 1 pack | Disposable, gel-coated |
| PPG optical window (clear acrylic, 3 mm) | 2 | Allows light through enclosure |

### 🖥️ Development Extras

| Component | Qty | Notes |
|-----------|-----|-------|
| USB-C cable (data + charge) | 2 | For MCU programming and BQ25895 charging |
| Logic analyzer (e.g., Saleae Logic 8) | 1 | Debug SPI/I²C signals |
| Multimeter | 1 | Verify power rails |
| Oscilloscope (optional) | 1 | Inspect ECG/PPG analog signal quality |
| SD card module (SPI) + micro SD card | 1 | Optional local data logging |

---

## Required Tools & Equipment

- ✅ Soldering iron (fine tip, temperature-controlled)
- ✅ Solder (63/37 or lead-free)
- ✅ Flush cutters & wire strippers
- ✅ Multimeter
- ✅ Logic analyzer (highly recommended)
- ✅ 3D printer (or access to a print service)
- ✅ Computer with USB and appropriate IDE:
  - **nRF5340**: [nRF Connect SDK](https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/index.html) + VS Code
  - **ESP32-S3**: [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/index.html) or Arduino IDE

---

## Master To-Do Checklist

### Phase 1 — Procurement & Preparation
- [ ] Order all components from the BOM (allow 1–3 weeks for delivery)
- [ ] Download and install MCU toolchain (nRF Connect SDK **or** ESP-IDF)
- [ ] Download datasheets for every sensor and save locally
- [ ] 3D-print or order the enclosure
- [ ] Gather all tools and a dedicated workspace

### Phase 2 — Power System
- [ ] Wire Li-ion battery → BQ25895 BAT pin
- [ ] Wire USB-C input → BQ25895 VBUS pin
- [ ] Wire BQ25895 SYS output → 3.3 V LDO input
- [ ] Wire LDO output → MCU VDD and all sensor VDD pins
- [ ] Verify 3.3 V rail with multimeter (target: 3.30 V ± 0.15 V)
- [ ] Check idle quiescent current < 5 mA with all sensors in low-power mode
- [ ] Add decoupling capacitors (100 nF + 10 µF) at each sensor VDD

### Phase 3 — MCU Bring-Up
- [ ] Flash "hello world" / blink LED firmware to MCU
- [ ] Verify UART output (115200 baud) on serial monitor
- [ ] Verify I²C bus at 400 kHz (scan for devices, check ACK)
- [ ] Verify SPI bus at 1–8 MHz (loopback test)
- [ ] Enable BLE advertising, confirm visible on smartphone

### Phase 4 — Sensor Bring-Up (one at a time)
- [ ] **MAX30102**: Read device ID register (0xFF → expected: 0x15); stream raw PPG
- [ ] **STS40-AD**: Read temperature register; confirm ±0.2 °C accuracy
- [ ] **ICM-42688-P**: Read WHO_AM_I register (expected: 0x47); read accel + gyro
- [ ] **MAX30003**: Read INFO register; read ECG FIFO; observe ECG waveform
- [ ] **AFE4300** (optional): Read device ID; run bio-impedance sweep

### Phase 5 — Integration & Wearable Assembly
- [ ] Integrate all sensors onto PCB / prototype board
- [ ] Route ECG shielded wires to electrode snap connectors
- [ ] Mount PPG sensor against skin window in enclosure
- [ ] Secure IMU rigidly to enclosure (no flex/bounce)
- [ ] Mount enclosure on compression sleeve or arm band
- [ ] Do initial wearable fit test — check sensor contact quality

### Phase 6 — Firmware Integration
- [ ] Implement sensor driver layer (one driver per sensor)
- [ ] Implement timestamping (RTC or MCU tick counter)
- [ ] Implement BLE GATT service for real-time streaming
- [ ] Implement SD card logging (optional)
- [ ] Implement IMU-based motion artifact flagging
- [ ] Implement BQ25895 battery level readback (I²C)
- [ ] Implement power management (sensor sleep on inactivity)

### Phase 7 — Testing & Validation
- [ ] Bench ECG signal quality test (measure noise floor < 10 µVrms)
- [ ] Bench PPG signal quality test (finger or wrist)
- [ ] Temperature accuracy validation against reference thermometer
- [ ] IMU axis orientation check (tap test, known angles)
- [ ] BLE streaming throughput test (target: 200+ Hz ECG, 100 Hz IMU)
- [ ] Motion artifact test (walk, run, arm movement)
- [ ] Battery life test (target: 8–24 h continuous streaming)
- [ ] Long-term wear comfort test (2–4 h session)

---

## Step-by-Step Assembly Guide

### Step 1 — Build the Power System

```
[Li-ion Battery] ──── BAT ──▶ [BQ25895 Module] ──── SYS ──▶ [3.3V LDO] ──▶ [MCU + Sensors]
[USB-C Charger]  ──── VBUS ──▶ [BQ25895 Module]
```

1. Solder JST-PH female connector to battery wires (red = VCC, black = GND)
2. Connect battery JST to BQ25895 BAT input
3. Connect BQ25895 SYS output to LDO VIN
4. Connect LDO VOUT to a shared 3.3 V power rail
5. Connect GND from battery → BQ25895 → LDO → power rail common GND
6. Add a SPDT power switch in series with the battery positive lead
7. Measure 3.3 V rail with multimeter before connecting any sensors

> ⚠️ **Safety**: Never short-circuit Li-ion batteries. Use a current-limited bench supply during initial testing.

---

### Step 2 — MCU Bring-Up

#### nRF5340 DK
1. Install [nRF Connect SDK](https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/index.html) and VS Code with nRF Connect extension
2. Open a "Hello World" Zephyr sample
3. Build and flash via USB:
   ```bash
   west build -b nrf5340dk_nrf5340_cpuapp samples/hello_world
   west flash
   ```
4. Open serial monitor at 115200 baud — confirm "Hello World" output

#### ESP32-S3 DevKit
1. Install ESP-IDF (v5.x recommended):
   ```bash
   git clone --recursive https://github.com/espressif/esp-idf.git
   cd esp-idf && ./install.sh esp32s3
   . ./export.sh
   ```
2. Build and flash a blink example:
   ```bash
   cd examples/get-started/blink
   idf.py set-target esp32s3
   idf.py build flash monitor
   ```

---

### Step 3 — Connect & Test Each Sensor

#### 3a. MAX30102 (SpO₂ / PPG) — I²C

| MAX30102 Pin | MCU Pin |
|-------------|---------|
| VIN | 3.3 V |
| GND | GND |
| SDA | I²C SDA |
| SCL | I²C SCL |
| INT | GPIO (optional interrupt) |

Run I²C scan — device should appear at address **0x57**.

#### 3b. STS40-AD (Temperature) — I²C

| STS40 Pin | MCU Pin |
|-----------|---------|
| VDD | 3.3 V |
| GND | GND |
| SDA | I²C SDA |
| SCL | I²C SCL |

Default I²C address: **0x44** (or 0x45 / 0x46 depending on ADR pin).

#### 3c. ICM-42688-P (IMU) — SPI

| ICM-42688-P Pin | MCU Pin |
|----------------|---------|
| VDD / VDDIO | 3.3 V |
| GND | GND |
| CS | GPIO (chip select) |
| SCK | SPI CLK |
| MOSI | SPI MOSI |
| MISO | SPI MISO |
| INT1 | GPIO (data-ready interrupt) |

WHO_AM_I register (0x75) should return **0x47**.

#### 3d. MAX30003 (ECG) — SPI

| MAX30003 Pin | MCU Pin |
|-------------|---------|
| VDD1 / VDD2 | 3.3 V |
| GND | GND |
| CSB | GPIO (chip select, active low) |
| SCLK | SPI CLK |
| SDI | SPI MOSI |
| SDO | SPI MISO |
| INTB | GPIO (interrupt) |
| ECGP | ECG electrode + |
| ECGN | ECG electrode − |

> 🔌 Connect shielded ECG leads: ECGP → Left Arm electrode, ECGN → Right Arm electrode (LA/RA placement for Lead I, or RA/LL for Lead II).

#### 3e. AFE4300 (Bio-Impedance, optional) — SPI

| AFE4300 Pin | MCU Pin |
|------------|---------|
| DVDD | 3.3 V |
| DGND | GND |
| CS | GPIO |
| SCLK | SPI CLK |
| SDI | SPI MOSI |
| SDO | SPI MISO |

---

### Step 4 — Wearable Integration

1. **3D-print enclosure**: Design or download a wrist/arm-band enclosure. Include:
   - Optical window cutout for MAX30102 (skin-facing side)
   - Snap-in ECG electrode ports (3.5 mm standard snap, 10 mm disc)
   - Cable channel for IMU routing
   - USB-C charging port access hole
   - Battery bay (size to your battery dimensions)

2. **Mount components inside enclosure**:
   - MCU board → standoffs (M2 screws)
   - Battery → foam-padded bay with Velcro strap
   - BQ25895 module → next to MCU
   - Sensors → oriented per their optical/electrical requirements

3. **Attach to garment**:
   - Sew or velcro the enclosure to compression sleeve
   - Route ECG leads through garment channels to electrode positions
   - Secure PPG sensor window flush against skin
   - Ensure IMU is on a rigid panel (no flex)

---

## Wiring & Pinout Reference

### Shared Bus Summary

```
3.3V Rail ──┬── MCU VDD
            ├── MAX30003 VDD
            ├── MAX30102 VIN
            ├── ICM-42688-P VDD
            ├── STS40-AD VDD
            ├── BQ25895 (logic)
            └── AFE4300 DVDD (if used)

GND ────────┬── All sensor GND
            ├── MCU GND
            └── Battery −

I²C Bus (400 kHz, 4.7 kΩ pull-ups to 3.3V):
  SDA ──── MAX30102 SDA ── STS40 SDA ── BQ25895 SDA
  SCL ──── MAX30102 SCL ── STS40 SCL ── BQ25895 SCL

SPI Bus (4–8 MHz):
  MOSI ─── MAX30003 SDI ── ICM-42688-P SDI ── AFE4300 SDI
  MISO ─── MAX30003 SDO ── ICM-42688-P SDO ── AFE4300 SDO
  CLK  ─── MAX30003 SCLK ─ ICM-42688-P SCLK ─ AFE4300 SCLK
  CS0  ─── MAX30003 CSB        (GPIO, active low)
  CS1  ─── ICM-42688-P CS      (GPIO, active low)
  CS2  ─── AFE4300 CS          (GPIO, active low, optional)
```

---

## Firmware Architecture & Code Examples

### Recommended Project Structure

```
firmware/
├── main.c / main.cpp          # Application entry point
├── drivers/
│   ├── max30003.c/h           # ECG driver
│   ├── max30102.c/h           # PPG/SpO₂ driver
│   ├── sts40.c/h              # Temperature driver
│   ├── icm42688p.c/h          # IMU driver
│   ├── bq25895.c/h            # Battery charger driver
│   └── afe4300.c/h            # Bio-impedance driver (optional)
├── ble/
│   ├── ble_service.c/h        # BLE GATT service definitions
│   └── ble_streaming.c/h      # Real-time data streaming
├── storage/
│   └── sd_logger.c/h          # SD card logging (optional)
├── utils/
│   ├── timestamp.c/h          # RTC / tick-based timestamping
│   ├── ring_buffer.c/h        # Lock-free ring buffer for samples
│   └── motion_artifact.c/h   # IMU-based artifact detection
└── config/
    └── board_config.h         # Pin definitions, I²C/SPI addresses
```

---

### Code Example 1 — Board Configuration (`config/board_config.h`)

```c
#ifndef BOARD_CONFIG_H
#define BOARD_CONFIG_H

// ── I²C Bus ──────────────────────────────────────────────
#define I2C_BUS_ID          0         // I²C peripheral index
#define I2C_FREQ_HZ         400000    // 400 kHz Fast Mode

#define MAX30102_I2C_ADDR   0x57
#define STS40_I2C_ADDR      0x44
#define BQ25895_I2C_ADDR    0x6A

// ── SPI Bus ──────────────────────────────────────────────
#define SPI_BUS_ID          1         // SPI peripheral index
#define SPI_FREQ_HZ         4000000   // 4 MHz

#define MAX30003_CS_PIN     10
#define ICM42688_CS_PIN     11
#define AFE4300_CS_PIN      12        // Optional

// ── GPIO ─────────────────────────────────────────────────
#define MAX30003_INT_PIN    14        // ECG FIFO interrupt
#define ICM42688_INT_PIN    15        // IMU data-ready interrupt
#define MAX30102_INT_PIN    16        // PPG interrupt (optional)

// ── Sample Rates ─────────────────────────────────────────
#define ECG_SAMPLE_RATE_HZ  512       // MAX30003 output data rate
#define PPG_SAMPLE_RATE_HZ  100       // MAX30102 sample rate
#define IMU_SAMPLE_RATE_HZ  200       // ICM-42688-P ODR
#define TEMP_SAMPLE_RATE_HZ 1         // STS40 (once per second)

#endif // BOARD_CONFIG_H
```

---

### Code Example 2 — MAX30003 ECG Driver (`drivers/max30003.c`)

```c
#include "max30003.h"
#include "board_config.h"
#include <stdint.h>
#include <string.h>

// MAX30003 Register Addresses
#define REG_INFO        0x0F
#define REG_CNFG_GEN    0x10
#define REG_CNFG_ECG    0x15
#define REG_RTOR        0x25
#define REG_ECG_FIFO    0x20
#define REG_FIFO_BURST  0x22
#define REG_SW_RST      0x08

// Write a 24-bit value to a MAX30003 register (SPI)
static void max30003_write_reg(uint8_t reg, uint32_t value) {
    uint8_t tx[4];
    tx[0] = (reg << 1) | 0x00;   // Write: LSB = 0
    tx[1] = (value >> 16) & 0xFF;
    tx[2] = (value >>  8) & 0xFF;
    tx[3] = (value      ) & 0xFF;
    spi_cs_low(MAX30003_CS_PIN);
    spi_transfer(tx, NULL, 4);
    spi_cs_high(MAX30003_CS_PIN);
}

// Read a 24-bit value from a MAX30003 register (SPI)
static uint32_t max30003_read_reg(uint8_t reg) {
    uint8_t tx[4] = { (reg << 1) | 0x01, 0x00, 0x00, 0x00 };
    uint8_t rx[4] = { 0 };
    spi_cs_low(MAX30003_CS_PIN);
    spi_transfer(tx, rx, 4);
    spi_cs_high(MAX30003_CS_PIN);
    return ((uint32_t)rx[1] << 16) | ((uint32_t)rx[2] << 8) | rx[3];
}

bool max30003_init(void) {
    // Software reset
    max30003_write_reg(REG_SW_RST, 0x000000);
    delay_ms(100);

    // Verify device INFO register
    uint32_t info = max30003_read_reg(REG_INFO);
    if ((info & 0xF00000) != 0x500000) {
        return false; // Unexpected device ID
    }

    // Configure CNFG_GEN: enable ECG channel, internal reference
    max30003_write_reg(REG_CNFG_GEN, 0x081007);

    // Configure CNFG_ECG: 512 SPS, gain = 20 V/V, high-pass filter on
    max30003_write_reg(REG_CNFG_ECG, 0x825000);

    return true;
}

int max30003_read_fifo(int32_t *samples, int max_samples) {
    int count = 0;
    while (count < max_samples) {
        uint32_t raw = max30003_read_reg(REG_ECG_FIFO);
        uint8_t etag = (raw >> 3) & 0x07;
        if (etag == 0x06) break;           // FIFO empty
        int32_t ecg = (int32_t)(raw >> 6); // 18-bit signed ECG sample
        if (ecg & 0x20000) ecg |= 0xFFFC0000; // sign-extend
        samples[count++] = ecg;
    }
    return count;
}
```

---

### Code Example 3 — MAX30102 PPG Driver (`drivers/max30102.c`)

```c
#include "max30102.h"
#include "board_config.h"

#define MAX30102_REG_INT_STATUS1  0x00
#define MAX30102_REG_MODE_CONFIG  0x09
#define MAX30102_REG_SPO2_CONFIG  0x0A
#define MAX30102_REG_LED1_PA      0x0C   // Red LED
#define MAX30102_REG_LED2_PA      0x0D   // IR LED
#define MAX30102_REG_FIFO_DATA    0x07
#define MAX30102_REG_PART_ID      0xFF

static void max30102_write(uint8_t reg, uint8_t value) {
    uint8_t buf[2] = { reg, value };
    i2c_write(MAX30102_I2C_ADDR, buf, 2);
}

static uint8_t max30102_read(uint8_t reg) {
    uint8_t val = 0;
    i2c_write(MAX30102_I2C_ADDR, &reg, 1);
    i2c_read(MAX30102_I2C_ADDR, &val, 1);
    return val;
}

bool max30102_init(void) {
    if (max30102_read(MAX30102_REG_PART_ID) != 0x15) {
        return false; // Device not found
    }
    // Reset device
    max30102_write(MAX30102_REG_MODE_CONFIG, 0x40);
    delay_ms(50);

    // SPO2 mode (Red + IR)
    max30102_write(MAX30102_REG_MODE_CONFIG, 0x03);

    // SPO2 config: 100 SPS, 18-bit ADC, 411 µs pulse width
    max30102_write(MAX30102_REG_SPO2_CONFIG, 0x27);

    // LED current: ~7 mA each
    max30102_write(MAX30102_REG_LED1_PA, 0x24);
    max30102_write(MAX30102_REG_LED2_PA, 0x24);

    return true;
}

void max30102_read_fifo(uint32_t *red, uint32_t *ir) {
    uint8_t buf[6];
    uint8_t reg = MAX30102_REG_FIFO_DATA;
    i2c_write(MAX30102_I2C_ADDR, &reg, 1);
    i2c_read(MAX30102_I2C_ADDR, buf, 6);

    *red = ((uint32_t)(buf[0] & 0x03) << 16) | ((uint32_t)buf[1] << 8) | buf[2];
    *ir  = ((uint32_t)(buf[3] & 0x03) << 16) | ((uint32_t)buf[4] << 8) | buf[5];
}
```

---

### Code Example 4 — ICM-42688-P IMU Driver (`drivers/icm42688p.c`)

```c
#include "icm42688p.h"
#include "board_config.h"

#define ICM_REG_WHO_AM_I    0x75
#define ICM_REG_PWR_MGMT0   0x4E
#define ICM_REG_GYRO_CONFIG 0x4F
#define ICM_REG_ACCEL_CONFIG 0x50
#define ICM_REG_ACCEL_DATA_X1 0x1F

static uint8_t icm_read_reg(uint8_t reg) {
    uint8_t tx[2] = { reg | 0x80, 0x00 };
    uint8_t rx[2] = { 0 };
    spi_cs_low(ICM42688_CS_PIN);
    spi_transfer(tx, rx, 2);
    spi_cs_high(ICM42688_CS_PIN);
    return rx[1];
}

static void icm_write_reg(uint8_t reg, uint8_t value) {
    uint8_t tx[2] = { reg & 0x7F, value };
    spi_cs_low(ICM42688_CS_PIN);
    spi_transfer(tx, NULL, 2);
    spi_cs_high(ICM42688_CS_PIN);
}

bool icm42688p_init(void) {
    if (icm_read_reg(ICM_REG_WHO_AM_I) != 0x47) {
        return false;
    }
    // Enable accel + gyro in low-noise mode
    icm_write_reg(ICM_REG_PWR_MGMT0, 0x0F);
    delay_ms(1);

    // Accel: ±8g, 200 Hz ODR
    icm_write_reg(ICM_REG_ACCEL_CONFIG, 0x56);

    // Gyro: ±2000 dps, 200 Hz ODR
    icm_write_reg(ICM_REG_GYRO_CONFIG, 0x46);

    return true;
}

void icm42688p_read(icm42688p_data_t *data) {
    uint8_t buf[12];
    uint8_t tx[13] = { ICM_REG_ACCEL_DATA_X1 | 0x80 };
    uint8_t rx[13] = { 0 };
    spi_cs_low(ICM42688_CS_PIN);
    spi_transfer(tx, rx, 13);
    spi_cs_high(ICM42688_CS_PIN);
    memcpy(buf, rx + 1, 12);

    data->accel_x = (int16_t)((buf[0]  << 8) | buf[1]);
    data->accel_y = (int16_t)((buf[2]  << 8) | buf[3]);
    data->accel_z = (int16_t)((buf[4]  << 8) | buf[5]);
    data->gyro_x  = (int16_t)((buf[6]  << 8) | buf[7]);
    data->gyro_y  = (int16_t)((buf[8]  << 8) | buf[9]);
    data->gyro_z  = (int16_t)((buf[10] << 8) | buf[11]);
}
```

---

### Code Example 5 — STS40 Temperature Driver (`drivers/sts40.c`)

```c
#include "sts40.h"
#include "board_config.h"

#define STS40_CMD_HIGH_PRECISION  0xFD

bool sts40_read_temperature(float *temperature_c) {
    uint8_t cmd = STS40_CMD_HIGH_PRECISION;
    uint8_t buf[3];

    i2c_write(STS40_I2C_ADDR, &cmd, 1);
    delay_ms(10); // measurement time ~9 ms

    if (i2c_read(STS40_I2C_ADDR, buf, 3) != 0) {
        return false;
    }

    // buf[0:1] = raw temp, buf[2] = CRC8
    uint16_t raw = ((uint16_t)buf[0] << 8) | buf[1];
    *temperature_c = -45.0f + 175.0f * ((float)raw / 65535.0f);
    return true;
}
```

---

### Code Example 6 — BLE GATT Service (`ble/ble_service.c`, nRF5340 / Zephyr)

```c
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include "ble_service.h"

// Custom BLE service UUID: use a UUID generator for production
static struct bt_uuid_128 biosensor_svc_uuid = BT_UUID_INIT_128(
    BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789ABCDEF0));

static struct bt_uuid_128 ecg_char_uuid = BT_UUID_INIT_128(
    BT_UUID_128_ENCODE(0x12345678, 0x1234, 0x5678, 0x1234, 0x56789ABCDEF1));

static uint8_t ecg_notify_buf[20];  // 5 ECG samples × 4 bytes each
static struct bt_gatt_attr biosensor_attrs[] = {
    BT_GATT_PRIMARY_SERVICE(&biosensor_svc_uuid),
    BT_GATT_CHARACTERISTIC(&ecg_char_uuid.uuid,
                           BT_GATT_CHRC_NOTIFY,
                           BT_GATT_PERM_NONE,
                           NULL, NULL, ecg_notify_buf),
    BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
};

static struct bt_gatt_service biosensor_svc = BT_GATT_SERVICE(biosensor_attrs);

void ble_service_init(void) {
    bt_gatt_service_register(&biosensor_svc);
}

void ble_notify_ecg(const int32_t *samples, uint8_t count) {
    // Pack up to 5 samples into 20-byte BLE packet
    uint8_t payload[20];
    uint8_t len = (count > 5 ? 5 : count) * 4;
    memcpy(payload, samples, len);
    bt_gatt_notify(NULL, &biosensor_attrs[1], payload, len);
}
```

---

### Code Example 7 — Main Application Loop (`main.c`)

```c
#include "board_config.h"
#include "drivers/max30003.h"
#include "drivers/max30102.h"
#include "drivers/icm42688p.h"
#include "drivers/sts40.h"
#include "ble/ble_service.h"
#include "utils/timestamp.h"
#include "utils/ring_buffer.h"

#define ECG_FIFO_SIZE   64
static int32_t  ecg_samples[ECG_FIFO_SIZE];
static ring_buf_t ecg_ring;

void sensor_init_all(void) {
    if (!max30003_init()) { log_error("MAX30003 init failed"); }
    if (!max30102_init()) { log_error("MAX30102 init failed"); }
    if (!icm42688p_init()) { log_error("ICM-42688-P init failed"); }
    // STS40 does not require explicit init
}

void ecg_isr_handler(void) {
    int n = max30003_read_fifo(ecg_samples, ECG_FIFO_SIZE);
    for (int i = 0; i < n; i++) {
        ring_buf_put(&ecg_ring, ecg_samples[i]);
    }
}

void main(void) {
    timestamp_init();
    spi_init(SPI_BUS_ID, SPI_FREQ_HZ);
    i2c_init(I2C_BUS_ID, I2C_FREQ_HZ);
    ring_buf_init(&ecg_ring, ECG_FIFO_SIZE);

    sensor_init_all();
    ble_service_init();
    ble_advertise_start();

    // Attach interrupt for ECG FIFO
    gpio_interrupt_attach(MAX30003_INT_PIN, ecg_isr_handler, GPIO_FALLING);

    uint32_t ppg_red, ppg_ir;
    icm42688p_data_t imu_data;
    float temperature;
    uint32_t last_ppg_ms = 0, last_temp_ms = 0;

    while (1) {
        uint32_t now = timestamp_ms();

        // Stream ECG samples via BLE
        if (!ring_buf_is_empty(&ecg_ring)) {
            int32_t batch[5];
            uint8_t n = ring_buf_get_batch(&ecg_ring, batch, 5);
            ble_notify_ecg(batch, n);
        }

        // PPG at 100 Hz
        if (now - last_ppg_ms >= 10) {
            last_ppg_ms = now;
            max30102_read_fifo(&ppg_red, &ppg_ir);
            ble_notify_ppg(ppg_red, ppg_ir);
        }

        // IMU at 200 Hz (interrupt-driven in real firmware)
        icm42688p_read(&imu_data);
        ble_notify_imu(&imu_data);

        // Temperature at 1 Hz
        if (now - last_temp_ms >= 1000) {
            last_temp_ms = now;
            if (sts40_read_temperature(&temperature)) {
                ble_notify_temperature(temperature);
            }
        }

        sleep_us(500); // ~2 kHz main loop tick, sensors drive their own rates
    }
}
```

---

## Testing & Validation

### Bench Testing Protocol

| Test | Pass Criteria | Method |
|------|--------------|--------|
| ECG noise floor | < 10 µVrms with inputs shorted | Measure RMS on ECG FIFO with no electrode |
| ECG signal (Lead I) | Clear P, QRS, T waves visible | Use ECG simulator or human subject |
| PPG (finger) | AC/DC ratio ≥ 0.05 | Place finger on MAX30102 |
| SpO₂ (reference vs. device) | ±2% of pulse oximeter reference | Side-by-side comparison |
| Temperature accuracy | ±0.3 °C | Compare to NIST-traceable reference thermometer |
| IMU accel offset | < 50 mg at rest, each axis | Measure at 6 known orientations |
| IMU gyro offset | < 5 dps at rest | Measure stationary |
| BLE throughput | ≥ 200 bytes/sec sustained | BLE sniffer or smartphone app log |
| Battery life | ≥ 8 hours at full streaming | Discharge test with all sensors running |

### Software Validation Checklist

- [ ] ECG: Verify timestamps are monotonic and sample rate matches target (±1%)
- [ ] PPG: Verify Red/IR ratio yields plausible SpO₂ (95–100% on healthy subject)
- [ ] IMU: Verify gravity vector = 1g at rest on each axis
- [ ] Temperature: Verify readings stable ±0.1 °C over 60 seconds
- [ ] BLE: Verify no packet loss at 2 m over 60 seconds
- [ ] SD Logger: Verify file integrity after 1-hour write session

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| I²C scan finds no devices | Wrong SDA/SCL wiring, missing pull-ups | Verify wiring; add 4.7 kΩ pull-ups to 3.3 V |
| SPI device returns 0xFF/0x00 only | CS pin not toggling, MOSI/MISO swapped | Check CS GPIO; verify MOSI/MISO orientation |
| MAX30003 INFO register wrong | SPI speed too high, or wiring error | Slow SPI to 1 MHz; check cable lengths |
| MAX30102 reads zero | Mode not set, LED current too low | Re-run init; increase LED PA register |
| ECG shows 60 Hz noise | No body ground, poor electrode contact | Add right-leg drive; ensure good skin contact |
| IMU values all zero | PWR_MGMT0 not set; still in sleep | Write 0x0F to PWR_MGMT0 |
| BLE not advertising | Incorrect bt_enable() call; antenna issue | Check Zephyr/ESP-IDF BLE init sequence |
| Battery voltage drops fast | High idle current; sensors not sleeping | Add sensor power-down between measurements |
| Temperature reading ±5 °C off | Self-heating from nearby components | Add thermal isolation; read after settling |

---

> 📌 **Next Steps After Prototype Validation**
> 1. Move to a custom PCB with proper analog ground planes and shielded ECG traces
> 2. Implement clinical-grade algorithms (Pan-Tompkins for R-peak detection, Masimo-style SpO₂)
> 3. Add regulatory documentation (FDA 510(k) pathway or CE MDR if applicable)
> 4. Conduct IRB-approved human subject testing
