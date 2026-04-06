# Assembly and Integration Guide
## Precise Robotics Medication Packing System

This guide provides step-by-step instructions for assembling and integrating the automated medication packing system from components to a fully operational unit.

---

## Prerequisites

Before beginning assembly:
- [ ] All parts from [PARTS_LIST.md](../parts/PARTS_LIST.md) received and verified
- [ ] Work area cleared (2m x 2m minimum)
- [ ] Tools prepared (see Tools Required section)
- [ ] Safety equipment ready (safety glasses, gloves)

---

## Tools Required

### Essential Tools
- Allen key set (metric, 2-10mm)
- Screwdriver set (Phillips and flat head)
- Wire strippers and cutters
- Soldering iron and solder (if needed)
- Multimeter
- Cable ties and velcro straps
- Drill with bits (if custom modifications needed)
- Measuring tape and level

### Optional but Helpful
- 3D printer (for custom brackets/mounts)
- Heat shrink tubing and heat gun
- Label maker
- Crimping tool for connectors

---

## Assembly Phases

The build is divided into logical phases that can be completed over several sessions.

---

## Phase 1: Structural Frame Assembly

**Estimated Time: 2-3 hours**

### Step 1.1: Base Frame
1. Cut aluminum extrusions to length:
   - Base: 2 pieces at 600mm (length), 2 pieces at 400mm (width)
   - Vertical posts: 4 pieces at 500mm (height)
   
2. Assemble base rectangle:
   - Connect the four base pieces using corner brackets
   - Ensure corners are square (use a carpenter's square)
   - Tighten T-slot nuts, but don't overtighten yet

3. Attach vertical posts:
   - Insert one post at each corner
   - Use corner brackets to secure
   - Verify posts are perpendicular to base using level

4. Add top frame:
   - Mirror base frame construction
   - Connect to top of vertical posts
   - Check overall squareness and adjust if needed
   - Final tighten all connections

### Step 1.2: Internal Structure
1. Add horizontal cross-members:
   - Install supports for storage bins (approx. 200mm from base)
   - Install supports for linear motion system (approx. 350mm from base)
   - These provide rigidity and mounting points

2. Add vertical dividers:
   - Create sections for storage vs. packing area
   - Leave clearance for moving components

### Step 1.3: Enclosure Panels
1. Measure and mark acrylic panels:
   - Front panel: Include cutout for touchscreen
   - Side panels: Include ventilation holes if needed
   - Top panel: Access hatch option

2. Attach panels to frame:
   - Use panel mounting brackets or drill/tap holes
   - Leave front panel easily removable for maintenance
   - Ensure door interlock switch mounting

**Checkpoint**: Verify structural integrity, all joints secure, frame is square and level.

---

## Phase 2: Linear Motion System

**Estimated Time: 3-4 hours**

### Step 2.1: X-Axis Installation
1. Mount X-axis linear rail:
   - Position rail along bottom cross-member (front-to-back)
   - Ensure rail is parallel to frame edges
   - Secure with T-slot nuts every 100mm

2. Install X-axis drive:
   - Attach lead screw or belt system
   - Mount NEMA 17 motor to one end
   - Install coupling or pulley
   - Ensure smooth, free movement of carriage

3. Add limit switches:
   - Mount switch at each end of travel
   - Position to trigger before hard stop
   - Wire to controller (document connections)

### Step 2.2: Y-Axis Installation
1. Mount Y-axis rail to X-axis carriage:
   - Perpendicular to X-axis
   - Elevate if needed for clearance
   - Secure firmly to moving carriage

2. Install Y-axis drive:
   - Similar to X-axis
   - Mount NEMA 17 motor
   - Add limit switches

### Step 2.3: Z-Axis Installation
1. Create Z-axis carriage:
   - Smaller linear rail or smooth rod system
   - Vertical orientation
   - Mount to Y-axis carriage

2. Install Z-axis drive:
   - NEMA 17 motor at top
   - Lead screw for precise control
   - Add limit switches
   - Ensure sufficient travel (approx. 200-250mm)

### Step 2.4: Cable Management
1. Install cable chain/carrier:
   - Protect moving wires from damage
   - Route motor cables, limit switch wires
   - Leave slack for full range of motion

**Checkpoint**: Manually move all axes through full range. Movement should be smooth with no binding. Limit switches should trigger at correct positions.

---

## Phase 3: Gripper System

**Estimated Time: 2-3 hours**

### Step 3.1: Gripper Mount
1. Design/3D print modular mount:
   - Attach to Z-axis carriage
   - Quick-release mechanism for swapping grippers
   - Ensure stable, aligned mounting

### Step 3.2: Install Primary Gripper
Choose based on your medication types:

#### Option A: Pneumatic Soft Gripper
1. Attach gripper to mount
2. Route air lines through cable chain
3. Mount solenoid valves near gripper
4. Install air compressor on frame (vibration-isolated)
5. Connect power and control signals

#### Option B: Mechanical Gripper
1. Attach gripper to mount
2. Connect servo motor or stepper
3. Route control cables
4. Test grip range and force

#### Option C: Vacuum Gripper
1. Attach vacuum cups to mount
2. Connect vacuum tubing
3. Mount vacuum pump on frame
4. Install control valve
5. Route power and control

### Step 3.3: Install Additional Grippers (if modular)
1. Prepare each gripper type on quick-release plate
2. Store unused grippers nearby
3. Document mounting/removal procedure

**Checkpoint**: Test gripper actuation. Verify sufficient grip force without damage to test objects.

---

## Phase 4: Storage System

**Estimated Time: 3-4 hours**

### Step 4.1: Bin Mounting
1. Create bin mounting grid:
   - Use aluminum extrusion or 3D printed rails
   - Arrange in accessible grid (e.g., 5x4 = 20 bins)
   - Label each position clearly (A1, A2, B1, etc.)

2. Install bins:
   - Ensure bins slide in/out easily for restocking
   - Verify clearance for gripper access
   - Angle bins slightly forward for visibility

### Step 4.2: Dispensing Gates
1. For each bin, install servo-controlled gate:
   - Gate at bottom/front of bin
   - One medication at a time release
   - Servo mounted to bin or rail
   - Connect servo signal wires

2. Cable management:
   - Bundle servo wires by row
   - Route to central distribution point
   - Label each servo wire with bin position

### Step 4.3: Sensors
1. Install optical sensors at each bin (optional but recommended):
   - Detect medication presence
   - Verify dispensing
   - Position below gate opening

**Checkpoint**: Test each gate servo. Verify full open/close operation. Check sensor readings.

---

## Phase 5: Scanning System

**Estimated Time: 2-3 hours**

### Step 5.1: Loading Station Scanner
1. Mount first barcode scanner:
   - Position at loading station (manual entry point)
   - Height and angle for easy scanning
   - Secure to frame with adjustable mount

2. Connect scanner:
   - USB to Raspberry Pi
   - Ensure proper driver/recognition
   - Test with sample barcodes

### Step 5.2: Verification Scanner
1. Mount second barcode scanner:
   - Position at packing station
   - On Z-axis near gripper OR fixed position where gripper presents medication
   - Optimal angle for consistent scans

2. Connect scanner:
   - USB to Raspberry Pi
   - Test functionality

### Step 5.3: Vision System (Optional)
1. Mount Raspberry Pi camera:
   - Above packing station
   - Include LED ring light for consistent lighting
   - Adjustable focus

2. Connect camera to Raspberry Pi
3. Test image capture and quality

**Checkpoint**: Test scanning various barcode types and angles. Verify consistent reads.

---

## Phase 6: Pouch Handling

**Estimated Time: 2-3 hours**

### Step 6.1: Pouch Dispenser
1. Mount pouch roll holder:
   - Position near packing station
   - Smooth rotation, no binding
   - Adjustable for different pouch widths

2. Install feed mechanism:
   - Stepper motor with roller or pinch wheels
   - Advance pouch to packing position
   - Maintain tension without tearing

### Step 6.2: Pouch Detection
1. Install optical sensors:
   - Detect pouch presence
   - Detect pouch edge for alignment
   - Through-beam or reflective type

2. Test detection:
   - Verify triggering at correct positions
   - Adjust sensitivity if needed

### Step 6.3: Packing Station
1. Define packing area:
   - Where medications are deposited
   - Open pouch access
   - Camera/scanner view

2. Optional: Add pouch opening mechanism
   - Vacuum or mechanical
   - Keeps pouch open during packing

**Checkpoint**: Test pouch advance mechanism. Verify accurate positioning.

---

## Phase 7: Electronics Integration

**Estimated Time: 4-5 hours**

### Step 7.1: Power System
1. Mount 12V power supply:
   - Central location in enclosure
   - Proper ventilation
   - Secure mounting

2. Install buck converter (12V to 5V):
   - For Raspberry Pi power
   - Adequate current capacity

3. Create power distribution:
   - Terminal blocks for multiple outputs
   - Fuses or breakers (recommended)
   - Clean, organized wiring

### Step 7.2: Controller Installation
1. Mount Raspberry Pi:
   - Central, accessible location
   - With heatsinks or cooling fan
   - Secure but removable for maintenance

2. Mount Arduino:
   - Near motor drivers
   - Minimal wire runs to motors
   - Secure mounting

3. Install CNC Shield (if used):
   - Stack onto Arduino
   - Insert stepper drivers
   - Set current limits on drivers (see motor specs)

### Step 7.3: Motor Wiring
1. Connect stepper motors to drivers:
   - X-axis motor to Driver 1
   - Y-axis motor to Driver 2
   - Z-axis motor to Driver 3
   - Pouch advance motor to Driver 4 (if needed)
   - **Verify coil pairing** (important!)

2. Connect servo motors:
   - Gripper servo to Arduino PWM pin
   - Gate servos to servo controller board or Arduino pins
   - Power from 5V or 6V supply (check servo rating)

### Step 7.4: Sensor Wiring
1. Connect limit switches:
   - 6 switches (2 per axis) to Arduino inputs
   - Use pull-up resistors or internal pull-ups
   - Label each wire

2. Connect optical sensors:
   - Pouch detection sensors to Arduino
   - Bin sensors (if used) to Arduino
   - Power and ground

3. Connect scanners:
   - USB to Raspberry Pi USB ports
   - Note which USB port for software configuration

4. Connect other sensors:
   - Temperature/humidity to Arduino or Raspberry Pi
   - Door interlock to Arduino (safety critical)

### Step 7.5: User Interface
1. Connect touchscreen:
   - Raspberry Pi GPIO or HDMI (depends on model)
   - Mount on front panel
   - Secure connection

2. Connect indicators:
   - LED status lights to Arduino or GPIO
   - Buzzer to Arduino
   - Test each indicator

3. Install emergency stop:
   - Hardwired to motor power circuit
   - Cuts power when pressed
   - Prominent, accessible location

### Step 7.6: Communication
1. Connect Arduino to Raspberry Pi:
   - USB cable
   - Serial communication
   - Stable connection (strain relief)

2. Network connection:
   - Ethernet cable to Raspberry Pi (or WiFi)
   - For remote monitoring/control
   - For logging to external database

**Checkpoint**: Power on system. Verify all components receive power. Check for shorts or overheating. Test emergency stop functionality.

---

## Phase 8: Software Setup

**Estimated Time: 4-6 hours (including testing)**

### Step 8.1: Raspberry Pi Setup
1. Install Raspberry Pi OS:
   - Flash to microSD card
   - Boot and configure
   - Update system: `sudo apt update && sudo apt upgrade`

2. Install dependencies:
   ```bash
   sudo apt install python3-pip python3-venv sqlite3
   pip3 install pyserial RPi.GPIO pyzbar opencv-python
   ```

3. Configure USB devices:
   - Identify scanner device IDs
   - Set up udev rules for consistent naming
   - Test scanner input

### Step 8.2: Arduino Setup
1. Install Arduino IDE on development computer
2. Install required libraries:
   - AccelStepper (for smooth motion)
   - Servo library
   - Any sensor-specific libraries

3. Upload motion control firmware:
   - See [firmware folder](../guides/firmware/) for code
   - Modify pin assignments to match wiring
   - Test basic motor movement

### Step 8.3: Main Application
1. Clone/download application code:
   - See [software folder](../guides/software/) for code
   - Main Python application for Raspberry Pi
   - User interface code

2. Configure application:
   - Database initialization
   - Serial port configuration
   - Scanner device paths
   - Medication formulary setup

3. Test basic functionality:
   - Scan a test barcode
   - Command a simple motion
   - Verify logging

### Step 8.4: Calibration
1. Teach bin positions:
   - Manually jog to each bin
   - Record coordinates
   - Store in configuration

2. Teach packing station position:
   - Record pouch drop-off coordinates

3. Test pick-and-place:
   - Manual test of full cycle
   - Adjust coordinates as needed
   - Verify scanning at each step

**Checkpoint**: Run complete test cycle with dummy objects. Verify all subsystems respond correctly.

---

## Phase 9: Safety and Testing

**Estimated Time: 3-4 hours**

### Step 9.1: Safety Checks
1. Emergency stop:
   - Press button, verify all motion stops immediately
   - Verify power cut to motors
   - Test recovery after reset

2. Limit switches:
   - Trigger each switch manually
   - Verify motion stops
   - Verify software handles correctly

3. Door interlock:
   - Open enclosure door
   - Verify motion stops
   - Test that system won't start with door open

4. Collision detection:
   - Slowly move axes to obstacles
   - Verify motors don't overheat or skip steps
   - Check for mechanical interference

### Step 9.2: Functional Testing
1. Test each subsystem independently:
   - Motion system: Move to all bin positions
   - Gripper: Pick up various test objects
   - Scanning: Scan barcodes from different angles
   - Pouch handling: Advance and position pouches
   - Logging: Verify data recorded correctly

2. Test integrated operation:
   - Load mock medications into bins
   - Scan at loading station
   - Create test packing order
   - Run automated packing cycle
   - Verify verification scanning
   - Check logs for completeness

3. Test error handling:
   - Simulate missing medication
   - Simulate scan failure
   - Simulate wrong medication
   - Verify alerts and logging

### Step 9.3: Performance Testing
1. Measure cycle time:
   - Time for single medication retrieval and packing
   - Identify bottlenecks
   - Optimize as needed

2. Test with various medications:
   - Different sizes: Small pills to large boxes
   - Different shapes: Round bottles, flat boxes
   - Different weights: Light and heavy items
   - Adjust gripper or swap modules as needed

3. Endurance test:
   - Run multiple packing cycles
   - Monitor for degradation or errors
   - Check for overheating
   - Verify consistent performance

**Checkpoint**: System completes full packing cycle reliably. All safety systems functional. Logging accurate and complete.

---

## Phase 10: Finalization

**Estimated Time: 2-3 hours**

### Step 10.1: Documentation
1. Label all components:
   - Motor numbers/axis assignments
   - Bin positions
   - Emergency stop
   - Power switches

2. Create wiring diagram:
   - Document actual connections
   - Note any deviations from plan
   - Attach to inside of enclosure

3. Write operation manual:
   - Startup procedure
   - Normal operation
   - Shutdown procedure
   - Basic troubleshooting

### Step 10.2: Cleanup and Organization
1. Secure all wiring:
   - Use cable ties and mounts
   - Avoid pinch points and moving parts
   - Clean up excess wire length

2. Organize spare parts:
   - Create maintenance kit
   - Label and store nearby

3. Clean enclosure:
   - Remove installation debris
   - Wipe down surfaces
   - Ensure professional appearance

### Step 10.3: Training
1. Create user training materials:
   - How to load medications
   - How to start packing job
   - How to respond to alerts
   - Basic maintenance tasks

2. Train operators:
   - Hands-on demonstration
   - Practice runs
   - Q&A session

### Step 10.4: Final Acceptance
1. Run acceptance test:
   - Complete packing of full formulary
   - Verify all medications logged
   - Check pouch contents match order
   - Confirm no errors or alerts

2. Document results:
   - Test completion certificate
   - Any outstanding issues
   - Recommendations for improvements

**Checkpoint**: System ready for production use.

---

## Maintenance and Ongoing Support

### Daily Maintenance
- Visual inspection of moving parts
- Verify scanner functionality
- Check medication stock levels
- Review logs for anomalies

### Weekly Maintenance
- Clean optics (scanners, cameras)
- Lubricate linear rails
- Check cable connections
- Test emergency stop

### Monthly Maintenance
- Comprehensive system test
- Update software if available
- Clean/inspect gripper
- Check and tighten all fasteners

### Troubleshooting Guide
See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues and solutions.

---

## Next Steps

- **Expand capacity**: Add more storage bins
- **Add features**: Implement vision system, network monitoring
- **Build more units**: Use lessons learned to streamline process
- **Integrate with existing systems**: Connect to pharmacy management software

---

## Support and Resources

- **Technical Support**: [Contact information]
- **Parts Suppliers**: [List of vendors]
- **User Community**: [Forum or discussion group]
- **Software Updates**: [Repository or download site]

---

**Congratulations!** You've successfully built the Precise Robotics Medication Packing System. With proper operation and maintenance, this system will provide reliable, accurate medication packing for years to come.
