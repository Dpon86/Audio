# Technical Specifications
## Precise Robotics Medication Packing System

This document provides detailed technical specifications for the automated medication packing system.

---

## Physical Specifications

### Dimensions
- **Footprint**: 600mm (W) x 400mm (D) x 500mm (H)
- **Weight**: 15-20 kg (33-44 lbs)
- **Workspace Volume**: ~200mm x 200mm x 250mm
- **Modular Units**: Stackable and arrangeable

### Materials
- **Frame**: Aluminum extrusion (20mm x 20mm)
- **Panels**: 3mm acrylic (transparent/colored)
- **Moving Parts**: Steel/aluminum linear rails and components
- **Storage Bins**: Food-grade plastic

---

## Performance Specifications

### Speed and Throughput
- **Pick-and-Place Cycle**: 30-60 seconds per medication
- **Maximum Speed**: 1000 mm/min (adjustable)
- **Acceleration**: 500 mm/s² (adjustable)
- **Homing Speed**: 200 mm/min
- **Pouch Advance Time**: ~5 seconds

### Capacity
- **Storage Bins**: 20 bins (standard), expandable to 40+
- **Bin Capacity**: ~10-50 items per bin (depends on size)
- **Pouches per Hour**: 10-20 (depends on formulary complexity)
- **Continuous Operation**: 8+ hours designed

### Accuracy
- **Positioning Accuracy**: ±1mm
- **Repeatability**: ±0.5mm
- **Scan Success Rate**: >99% (with quality barcodes)
- **Verification Rate**: 100% (double-scan system)

---

## Electrical Specifications

### Power Requirements
- **Input Voltage**: 12V DC
- **Maximum Current**: 10A
- **Average Power Consumption**: 50-80W
- **Peak Power**: 120W
- **Standby Power**: <10W

### Controllers
- **Main Controller**: Raspberry Pi 4 (4GB RAM)
  - Processor: Quad-core ARM Cortex-A72 @ 1.5GHz
  - Storage: 32GB microSD
  - Operating System: Raspberry Pi OS (Linux)
  
- **Motion Controller**: Arduino Mega 2560
  - Processor: ATmega2560 @ 16MHz
  - Digital I/O: 54 pins
  - Analog Inputs: 16 pins

### Motors
- **Stepper Motors**: 3x NEMA 17 (X, Y, Z axes)
  - Voltage: 12V
  - Current: 1.5A per phase
  - Torque: 40-50 Ncm
  - Steps per Revolution: 200 (1.8° per step)
  - Microstepping: 16x (3200 steps/rev)

- **Servo Motors**: 2-3x MG996R or equivalent
  - Voltage: 5-6V
  - Torque: 10-15 kg-cm
  - Speed: 0.17 sec/60°

### Sensors
- **Limit Switches**: 6x mechanical switches
  - Type: NO (Normally Open)
  - Rating: 3A @ 125V AC

- **Optical Sensors**: 2-4x through-beam or reflective
  - Range: 10-50mm
  - Response Time: <1ms

- **Barcode Scanners**: 2x USB scanners
  - Type: 1D/2D barcode and QR code
  - Interface: USB HID (keyboard emulation)
  - Scan Rate: 100-300 scans/second

---

## Motion System Specifications

### Linear Motion (X and Y Axes)
- **Rail Type**: Linear guide rails with carriages
- **Rail Length**: 400mm
- **Travel Distance**: 350mm effective
- **Drive System**: 8mm lead screw (4mm pitch) or GT2 timing belt
- **Load Capacity**: 5-10 kg per axis

### Vertical Motion (Z Axis)
- **Rail Type**: Linear guide rail or smooth rod
- **Rail Length**: 300mm
- **Travel Distance**: 200-250mm effective
- **Drive System**: 8mm lead screw (2mm or 4mm pitch)
- **Load Capacity**: 2-5 kg

### Resolution
- **X/Y Axes (with lead screw)**: 0.00125mm per microstep (4mm pitch, 16x microstepping)
- **Z Axis (with lead screw)**: 0.000625mm per microstep (2mm pitch, 16x microstepping)
- **Practical Resolution**: 0.1mm (more than sufficient for medication handling)

---

## Gripper System Specifications

### Gripper Types (Modular, Interchangeable)

#### Pneumatic Soft Gripper
- **Type**: Silicone soft gripper fingers
- **Grip Force**: Adjustable via air pressure (0-50 PSI)
- **Opening Range**: 0-100mm
- **Object Weight**: Up to 500g
- **Compressor**: 12V DC, 150 PSI max

#### Mechanical Parallel Gripper
- **Type**: Servo or stepper-driven parallel jaw
- **Grip Force**: 5-20 N (adjustable)
- **Opening Range**: 0-80mm
- **Object Weight**: Up to 1 kg
- **Response Time**: 0.5-1 second

#### Vacuum Gripper
- **Type**: Vacuum cups (various sizes)
- **Vacuum Level**: -50 to -80 kPa
- **Cup Diameter**: 20-40mm
- **Object Weight**: Up to 500g (flat surfaces)
- **Pump**: 12V DC vacuum pump

---

## Storage System Specifications

### Storage Bins
- **Bin Dimensions**: 100mm x 100mm x 50mm (typical)
- **Bin Material**: Transparent plastic (PS or PMMA)
- **Grid Layout**: 5 columns x 4 rows = 20 bins (standard)
- **Expandable**: Up to 40+ bins with additional modules
- **Capacity per Bin**: Varies by medication size
  - Small pills: 30-50 items
  - Medium bottles: 10-20 items
  - Large boxes: 5-10 items

### Dispensing Gates
- **Type**: Servo-controlled flip or slide gates
- **Servo**: Micro servo (9g or 20g)
- **Opening**: Releases one item at a time
- **Sensor**: Optional optical sensor for verification

---

## Scanning and Verification System

### Barcode Scanning
- **Technology**: Laser or image-based 1D/2D scanner
- **Supported Codes**: 
  - 1D: UPC, EAN, Code 39, Code 128
  - 2D: QR Code, Data Matrix
- **Scan Distance**: 50-300mm
- **Scan Angle**: ±30° from perpendicular
- **Decode Speed**: <100ms per scan

### Vision System (Optional)
- **Camera**: Raspberry Pi Camera Module v2
  - Resolution: 8 megapixels (3280 x 2464)
  - Sensor: Sony IMX219
  - Video: 1080p30, 720p60
  
- **Lighting**: LED ring light, adjustable brightness
- **Processing**: OpenCV on Raspberry Pi
- **OCR Capability**: Text recognition for labeling

---

## User Interface Specifications

### Display
- **Type**: 7" capacitive touchscreen
- **Resolution**: 800 x 480 pixels
- **Interface**: HDMI + USB (touch) or GPIO
- **Viewing Angle**: 160° (H) x 140° (V)

### Indicators
- **Status LEDs**: 3-5 RGB LEDs
  - Ready (Green)
  - Working (Blue/Yellow)
  - Error (Red)
  
- **Audio**: Buzzer for alerts (85 dB @ 10cm)

### Controls
- **Emergency Stop**: Large red mushroom button
  - Type: Twist-to-release
  - Contacts: NC (Normally Closed)
  
- **Door Interlock**: Magnetic or mechanical switch

---

## Environmental Specifications

### Operating Conditions
- **Temperature**: 15°C to 30°C (59°F to 86°F)
- **Humidity**: 30% to 70% RH (non-condensing)
- **Altitude**: Up to 2000m
- **Ventilation**: Natural or forced air cooling

### Storage Conditions
- **Temperature**: -10°C to 40°C (14°F to 104°F)
- **Humidity**: 10% to 90% RH (non-condensing)

### Noise Level
- **Operation**: <60 dB(A) at 1 meter
- **Standby**: <30 dB(A)

---

## Software Specifications

### Operating System
- **Raspberry Pi**: Raspberry Pi OS (Debian-based Linux)
- **Arduino**: Arduino firmware (C++)

### Programming Languages
- **Main Application**: Python 3.7+
- **Motion Control**: Arduino C/C++
- **Database**: SQLite 3
- **User Interface**: Python Tkinter or Flask (web-based)

### Software Features
- Medication database management
- Formulary configuration
- Job scheduling and queuing
- Real-time monitoring and logging
- User authentication (optional)
- Remote access (optional)
- Automatic updates (optional)

### Communication Protocols
- **Serial**: USB serial (115200 baud)
- **Network**: Ethernet or WiFi (TCP/IP)
- **Data Format**: JSON for configuration, CSV for logs

---

## Safety Specifications

### Safety Features
- **Emergency Stop**: Hardwired motor cutoff
- **Door Interlock**: Motion disabled when door open
- **Limit Switches**: Prevent over-travel on all axes
- **Collision Detection**: Motor stall detection
- **Software Watchdog**: Auto-recovery from hangs
- **Error Logging**: All errors logged with timestamps

### Compliance
- **Electrical**: Design for low-voltage safety (<50V)
- **Mechanical**: Guarded moving parts
- **Medical**: (Requires formal validation for medical use)

### Risk Mitigation
- **Redundant Verification**: Double-scanning of all medications
- **Audit Trail**: Complete logging of all operations
- **Access Control**: Optional user authentication
- **Data Backup**: Automatic database backups

---

## Data Logging Specifications

### Log Types
1. **Loading Log**: Medication stocking events
2. **Packing Log**: Medication packing events
3. **Error Log**: System errors and warnings
4. **Performance Log**: Cycle times and statistics
5. **Maintenance Log**: Service and calibration records

### Data Retention
- **Active Database**: 30-90 days on device
- **Archived Logs**: Unlimited (external storage)
- **Backup Frequency**: Daily (configurable)

### Log Fields (Example - Packing Event)
- Timestamp (date and time)
- Operator ID
- Formulary ID
- Medication barcode
- Bin ID
- Verification scan result
- Pouch ID
- Status (success/error)
- Error details (if applicable)

---

## Maintenance Specifications

### Scheduled Maintenance

#### Daily
- Visual inspection: 2 minutes
- Test basic functions: 5 minutes

#### Weekly
- Clean scanners: 5 minutes
- Lubricate rails: 10 minutes
- Check connections: 5 minutes

#### Monthly
- Comprehensive test: 30 minutes
- Calibration check: 15 minutes
- Software update: 10 minutes

### Consumables
- **Lubricant**: Light machine oil, ~10ml/month
- **Cleaning**: Isopropyl alcohol and lint-free cloths
- **Replacement Parts**: Keep spare motors, sensors, servos

### MTBF (Mean Time Between Failures)
- **Target**: >1000 hours of operation
- **Expected**: 2000-5000 hours with proper maintenance

---

## Expandability and Customization

### Modular Expansion
- **Storage**: Add bins in multiples of 10-20
- **Grippers**: Swap or add gripper types
- **Scanners**: Add additional verification points
- **Sensors**: Add weight scales, temperature monitors

### Software Customization
- **Formularies**: Unlimited custom medication sets
- **User Interface**: Customizable screens and workflows
- **Integration**: API for external systems
- **Reporting**: Custom report generation

### Network Features
- **Local Network**: Ethernet or WiFi connectivity
- **Remote Monitoring**: Web-based dashboard
- **Multi-Unit**: Coordinate multiple machines
- **Cloud Integration**: Optional cloud logging

---

## Standards and Compliance

### Design Standards
- **Robotics**: ISO 10218 (Industrial robots - Safety requirements)
- **Electrical**: IEC 61010 (Safety requirements for electrical equipment)
- **Software**: Following best practices for safety-critical systems

### Medical Compliance (Future)
For use in medical settings, additional validation required:
- **FDA**: 21 CFR Part 11 (Electronic records)
- **ISO**: ISO 13485 (Medical devices - Quality management)
- **GMP**: Good Manufacturing Practices

*Note: Current design is for educational/development purposes. Medical use requires formal validation and certification.*

---

## Warranty and Support

### Recommended Warranty (for commercial builds)
- **Hardware**: 1 year parts
- **Software**: Lifetime updates
- **Support**: Email and forum-based

### Documentation
- Complete build instructions provided
- Software source code included
- Troubleshooting guides
- Video tutorials (optional)

---

## Summary

This medication packing system is designed to be:
- **Affordable**: ~$800-1,600 per unit
- **Compact**: 600x400x500mm footprint
- **Accurate**: ±1mm positioning, >99% scan rate
- **Fast**: 30-60 seconds per medication
- **Safe**: Multiple safety systems and verification
- **Expandable**: Modular design for easy upgrades
- **Reliable**: >1000 hours MTBF

For detailed implementation, refer to:
- [Assembly Guide](../guides/ASSEMBLY_GUIDE.md)
- [System Integration](../guides/SYSTEM_INTEGRATION.md)
- [Parts List](../parts/PARTS_LIST.md)
