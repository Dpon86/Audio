# System Integration Guide
## Precise Robotics Medication Packing System

This document provides detailed information on integrating the software and hardware components of the medication packing system.

---

## Overview

The system consists of three main software layers:
1. **Motion Control Layer** (Arduino) - Real-time control of motors and sensors
2. **Application Layer** (Raspberry Pi) - Business logic, scanning, logging
3. **User Interface Layer** (Raspberry Pi) - Touchscreen interface, status display

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                User Interface Layer                 │
│  (Python/Tkinter or Web Interface on RPi)          │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              Application Layer                       │
│  - Job Management                                    │
│  - Barcode Scanning                                  │
│  - Database Logging                                  │
│  - Safety Monitoring                                 │
│  (Python on Raspberry Pi)                           │
└─────────────────┬───────────────────────────────────┘
                  │ Serial Communication (USB)
┌─────────────────▼───────────────────────────────────┐
│            Motion Control Layer                      │
│  - Stepper Motor Control                             │
│  - Servo Control                                     │
│  - Sensor Reading                                    │
│  - Emergency Stop Handling                           │
│  (Arduino C++)                                       │
└─────────────────┬───────────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
┌────────▼──────┐  ┌──────▼────────┐
│   Motors      │  │   Sensors     │
│   Servos      │  │   Switches    │
│   Pneumatics  │  │   Scanners    │
└───────────────┘  └───────────────┘
```

---

## Hardware Integration

### 1. Arduino Motion Controller

#### Pin Assignments (Example for Arduino Mega with CNC Shield)

```cpp
// Stepper Motors (via CNC Shield)
#define X_STEP_PIN    2
#define X_DIR_PIN     5
#define Y_STEP_PIN    3
#define Y_DIR_PIN     6
#define Z_STEP_PIN    4
#define Z_DIR_PIN     7
#define ENABLE_PIN    8

// Limit Switches
#define X_MIN_PIN     9
#define X_MAX_PIN     10
#define Y_MIN_PIN     11
#define Y_MAX_PIN     12
#define Z_MIN_PIN     13
#define Z_MAX_PIN     14

// Servos
#define GRIPPER_SERVO_PIN  44
#define GATE_SERVO_START   22  // Gates on pins 22-41 (20 bins)

// Sensors
#define POUCH_SENSOR_PIN   50
#define DOOR_INTERLOCK_PIN 51
#define TEMP_SENSOR_PIN    A0

// Emergency Stop (interrupt capable)
#define EMERGENCY_STOP_PIN 18

// Status LEDs
#define LED_READY_PIN      A8
#define LED_WORKING_PIN    A9
#define LED_ERROR_PIN      A10
#define BUZZER_PIN         A11
```

#### Arduino Firmware Structure

```cpp
// Main sketch outline
#include <AccelStepper.h>
#include <Servo.h>

// Create stepper objects
AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

// Create servo objects
Servo gripperServo;
Servo gateServos[20];  // One for each bin

// State machine
enum SystemState {
  IDLE,
  HOMING,
  MOVING,
  PICKING,
  PLACING,
  ERROR
};
SystemState currentState = IDLE;

void setup() {
  Serial.begin(115200);
  
  // Initialize steppers
  stepperX.setMaxSpeed(1000);
  stepperX.setAcceleration(500);
  
  // Initialize servos
  gripperServo.attach(GRIPPER_SERVO_PIN);
  
  // Initialize pins
  pinMode(EMERGENCY_STOP_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(EMERGENCY_STOP_PIN), emergencyStop, FALLING);
  
  // Home all axes
  homeAllAxes();
}

void loop() {
  // Check for commands from Raspberry Pi
  if (Serial.available()) {
    processCommand();
  }
  
  // Run stepper motors
  stepperX.run();
  stepperY.run();
  stepperZ.run();
  
  // Check safety conditions
  checkSafety();
  
  // Send status updates
  sendStatus();
}

void processCommand() {
  // Parse command from serial (e.g., "MOVE X100 Y200 Z50")
  // Execute appropriate action
}

void emergencyStop() {
  // Immediate stop all motion
  stepperX.stop();
  stepperY.stop();
  stepperZ.stop();
  currentState = ERROR;
}
```

### 2. Raspberry Pi Application Controller

#### Python Application Structure

```python
# main.py - Main application entry point

import serial
import sqlite3
import time
from datetime import datetime
from barcode_scanner import BarcodeScanner
from motion_controller import MotionController
from database import Database
from ui import UserInterface

class MedicationPackingSystem:
    def __init__(self):
        # Initialize components
        self.arduino = MotionController('/dev/ttyACM0', 115200)
        self.scanner_loading = BarcodeScanner('/dev/input/event0')
        self.scanner_verify = BarcodeScanner('/dev/input/event1')
        self.db = Database('medications.db')
        self.ui = UserInterface(self)
        
        # System state
        self.current_job = None
        self.bin_positions = self.load_bin_positions()
        
    def load_medication(self, bin_id):
        """Handle medication loading process"""
        # Wait for scan
        barcode = self.scanner_loading.wait_for_scan()
        
        # Lookup medication info
        med_info = self.db.get_medication_info(barcode)
        
        # Prompt user to place in bin
        self.ui.show_message(f"Place {med_info['name']} in bin {bin_id}")
        
        # Log the loading
        self.db.log_loading(bin_id, barcode, datetime.now())
        
        return True
    
    def pack_pouch(self, formulary_id):
        """Execute packing job for a specific formulary"""
        # Get list of medications needed
        medications = self.db.get_formulary_medications(formulary_id)
        
        # Advance pouch
        self.arduino.advance_pouch()
        
        for med in medications:
            # Find medication in bins
            bin_id = self.db.find_medication_location(med['barcode'])
            
            if not bin_id:
                self.ui.show_error(f"Medication {med['name']} not in stock")
                return False
            
            # Move to bin
            bin_pos = self.bin_positions[bin_id]
            self.arduino.move_to(bin_pos['x'], bin_pos['y'], bin_pos['z'])
            
            # Open gate to release one item
            self.arduino.open_gate(bin_id)
            time.sleep(0.5)
            self.arduino.close_gate(bin_id)
            
            # Pick up medication
            self.arduino.lower_gripper()
            self.arduino.close_gripper()
            self.arduino.raise_gripper()
            
            # Move to verification scanner
            self.arduino.move_to_scanner()
            
            # Verify correct medication
            scanned_code = self.scanner_verify.wait_for_scan(timeout=5)
            if scanned_code != med['barcode']:
                self.ui.show_error("Wrong medication detected!")
                return False
            
            # Move to pouch
            self.arduino.move_to_pouch()
            
            # Release medication
            self.arduino.open_gripper()
            
            # Log the action
            self.db.log_packing(formulary_id, med['barcode'], 
                              bin_id, datetime.now())
        
        # Complete job
        self.ui.show_message("Pouch packing complete!")
        return True
    
    def run(self):
        """Main application loop"""
        self.ui.show_main_menu()
        self.ui.start()

if __name__ == "__main__":
    system = MedicationPackingSystem()
    system.run()
```

#### Database Schema

```python
# database.py - Database management

import sqlite3

class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Medication master list
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                barcode TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                size_category TEXT,
                weight_grams REAL,
                special_handling TEXT
            )
        ''')
        
        # Bin inventory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bin_inventory (
                bin_id TEXT PRIMARY KEY,
                barcode TEXT,
                quantity INTEGER,
                last_loaded TIMESTAMP,
                FOREIGN KEY (barcode) REFERENCES medications(barcode)
            )
        ''')
        
        # Formularies (medication sets)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formularies (
                formulary_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Formulary contents
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formulary_contents (
                formulary_id TEXT,
                barcode TEXT,
                quantity INTEGER,
                FOREIGN KEY (formulary_id) REFERENCES formularies(formulary_id),
                FOREIGN KEY (barcode) REFERENCES medications(barcode)
            )
        ''')
        
        # Loading log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loading_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bin_id TEXT,
                barcode TEXT,
                timestamp TIMESTAMP,
                operator_id TEXT
            )
        ''')
        
        # Packing log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packing_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                formulary_id TEXT,
                barcode TEXT,
                bin_id TEXT,
                timestamp TIMESTAMP,
                verified BOOLEAN,
                pouch_id TEXT
            )
        ''')
        
        self.conn.commit()
```

---

## Communication Protocol

### Arduino ↔ Raspberry Pi Serial Protocol

Messages are newline-terminated ASCII strings.

#### Commands (Raspberry Pi → Arduino)

```
HOME             - Home all axes
MOVE X<val> Y<val> Z<val>  - Move to absolute position
MOVR X<val> Y<val> Z<val>  - Move relative
GRIPPER OPEN     - Open gripper
GRIPPER CLOSE    - Close gripper
GATE <id> OPEN   - Open specific gate
GATE <id> CLOSE  - Close specific gate
POUCH ADVANCE    - Advance pouch
ESTOP RESET      - Reset emergency stop
STATUS           - Request status update
```

#### Responses (Arduino → Raspberry Pi)

```
OK               - Command completed successfully
ERROR <msg>      - Error occurred
STATUS <json>    - Status information
POS X<val> Y<val> Z<val>  - Current position
LIMIT <axis>     - Limit switch triggered
ESTOP            - Emergency stop activated
```

#### Example Communication

```
→ HOME
← STATUS {"state":"HOMING","x":0,"y":0,"z":0}
← OK

→ MOVE X100 Y150 Z20
← STATUS {"state":"MOVING","x":50,"y":75,"z":10}
← POS X100 Y150 Z20
← OK

→ GRIPPER CLOSE
← OK
```

---

## Configuration Files

### bin_positions.json
```json
{
  "A1": {"x": 50, "y": 50, "z": 0},
  "A2": {"x": 150, "y": 50, "z": 0},
  "A3": {"x": 250, "y": 50, "z": 0},
  "B1": {"x": 50, "y": 150, "z": 0},
  "B2": {"x": 150, "y": 150, "z": 0}
}
```

### system_config.json
```json
{
  "serial_port": "/dev/ttyACM0",
  "baud_rate": 115200,
  "scanner_loading": "/dev/input/event0",
  "scanner_verify": "/dev/input/event1",
  "database_path": "/var/lib/medpack/medications.db",
  "log_path": "/var/log/medpack/",
  "max_speed": 1000,
  "acceleration": 500,
  "homing_speed": 200,
  "gripper_open_angle": 90,
  "gripper_close_angle": 0
}
```

---

## User Interface

### Touchscreen Interface Options

#### Option 1: Python Tkinter (Simpler)
```python
# ui.py
import tkinter as tk
from tkinter import ttk, messagebox

class UserInterface:
    def __init__(self, system):
        self.system = system
        self.root = tk.Tk()
        self.root.title("Medication Packing System")
        self.root.geometry("800x480")  # 7" touchscreen resolution
        
        self.create_main_menu()
    
    def create_main_menu(self):
        # Large buttons for touch interface
        btn_load = tk.Button(self.root, text="Load Medications", 
                            command=self.show_loading_screen,
                            height=3, font=('Arial', 16))
        btn_load.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_pack = tk.Button(self.root, text="Pack Pouch",
                            command=self.show_packing_screen,
                            height=3, font=('Arial', 16))
        btn_pack.pack(fill='both', expand=True, padx=10, pady=10)
        
        btn_status = tk.Button(self.root, text="System Status",
                              command=self.show_status_screen,
                              height=3, font=('Arial', 16))
        btn_status.pack(fill='both', expand=True, padx=10, pady=10)
    
    def show_loading_screen(self):
        # Screen for loading medications
        pass
    
    def show_packing_screen(self):
        # Screen for packing operations
        pass
    
    def start(self):
        self.root.mainloop()
```

#### Option 2: Web Interface (More Flexible)
```python
# web_ui.py
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
system = None  # Set in main()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/load', methods=['POST'])
def load_medication():
    data = request.json
    result = system.load_medication(data['bin_id'])
    return jsonify({'success': result})

@app.route('/api/pack', methods=['POST'])
def pack_pouch():
    data = request.json
    result = system.pack_pouch(data['formulary_id'])
    return jsonify({'success': result})

@app.route('/api/status', methods=['GET'])
def get_status():
    status = system.get_status()
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## Safety Integration

### Emergency Stop Handling

```cpp
// Arduino: Interrupt-driven emergency stop
volatile bool emergencyStopActive = false;

void emergencyStop() {
  emergencyStopActive = true;
  // Immediately disable all motors
  digitalWrite(ENABLE_PIN, HIGH);
  // Set error state
  currentState = ERROR;
  // Alert Raspberry Pi
  Serial.println("ESTOP");
}

void loop() {
  if (emergencyStopActive) {
    // Don't process any commands
    // Flash error LED
    return;
  }
  // ... normal operation
}
```

```python
# Python: Handle emergency stop notification
def handle_arduino_message(self, message):
    if message == "ESTOP":
        self.emergency_stop_active = True
        self.ui.show_critical_error("EMERGENCY STOP ACTIVATED")
        # Prevent any new commands
        self.pause_all_operations()
```

### Door Interlock

```cpp
// Arduino: Check door status before allowing motion
bool isDoorClosed() {
  return digitalRead(DOOR_INTERLOCK_PIN) == LOW;
}

void processCommand() {
  if (!isDoorClosed()) {
    Serial.println("ERROR Door open");
    return;
  }
  // ... process command
}
```

---

## Testing and Calibration

### Initial Calibration Procedure

1. **Homing Calibration**
   ```python
   # Run homing sequence
   system.arduino.send_command("HOME")
   # Verify all axes reach home switches
   ```

2. **Bin Position Teaching**
   ```python
   # Manual jog mode
   for bin_id in bin_list:
       print(f"Move to bin {bin_id}")
       # Use arrow keys or touchscreen to jog
       x, y, z = system.arduino.get_position()
       bin_positions[bin_id] = {'x': x, 'y': y, 'z': z}
   
   # Save positions
   save_bin_positions(bin_positions)
   ```

3. **Gripper Force Calibration**
   ```python
   # Test with various objects
   for test_object in test_objects:
       angle = find_minimum_grip_angle(test_object)
       print(f"{test_object}: {angle} degrees")
   ```

4. **Scanner Alignment**
   - Position test barcode
   - Adjust scanner angle and distance
   - Verify consistent scanning

---

## Deployment

### Raspberry Pi Service Setup

Create systemd service for automatic startup:

```bash
# /etc/systemd/system/medpack.service
[Unit]
Description=Medication Packing System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/medpack
ExecStart=/usr/bin/python3 /home/pi/medpack/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl enable medpack.service
sudo systemctl start medpack.service
```

### Network Configuration

For remote monitoring:
```python
# Add MQTT or REST API for external monitoring
import paho.mqtt.client as mqtt

class SystemMonitor:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.connect("mqtt.server.com", 1883)
    
    def publish_status(self, status):
        self.client.publish("medpack/status", json.dumps(status))
```

---

## Troubleshooting

### Common Issues

1. **Motors not moving**
   - Check power supply
   - Verify stepper driver current settings
   - Check enable pin state

2. **Scanners not detected**
   - Check USB connections
   - Verify device paths: `ls -l /dev/input/`
   - Check permissions: add user to `input` group

3. **Serial communication errors**
   - Verify baud rate matches
   - Check cable connection
   - Monitor serial: `screen /dev/ttyACM0 115200`

4. **Position drift**
   - Check for missed steps
   - Reduce speed/acceleration
   - Verify mechanical tightness

---

## Maintenance

### Software Updates
```bash
cd /home/pi/medpack
git pull
sudo systemctl restart medpack.service
```

### Database Backup
```bash
# Daily backup cron job
0 2 * * * cp /var/lib/medpack/medications.db /backup/medications_$(date +\%Y\%m\%d).db
```

### Log Rotation
```bash
# /etc/logrotate.d/medpack
/var/log/medpack/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

---

## Future Enhancements

1. **Machine Learning Integration**
   - Computer vision for medication verification
   - Predictive maintenance

2. **Cloud Connectivity**
   - Real-time inventory tracking
   - Remote diagnostics
   - Multi-site coordination

3. **Advanced Robotics**
   - More sophisticated grippers
   - Faster motion algorithms
   - Collaborative robot features

---

This completes the system integration guide. For specific code examples and full source code, see the [software repository](../guides/software/).
