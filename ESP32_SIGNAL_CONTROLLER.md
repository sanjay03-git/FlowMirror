# ESP32 miniature signal controller

This integration makes the FlowMirror simulation visibly control a three-LED
model intersection. It is a classroom/demo integration only. Never connect it
to a real traffic controller, relay, mains supply, or public-road equipment.

## Parts

- ESP32 DevKit V1
- Breadboard
- One red, one yellow, and one green 5 mm LED
- Three 220 ohm resistors
- Male-to-male jumper wires
- USB data cable

## Wiring

For each LED, connect the ESP32 pin to the LED's positive leg through a 220 ohm
resistor. Connect the LED's negative leg to a GND pin.

| LED | ESP32 GPIO |
| --- | --- |
| Red | 25 |
| Yellow | 26 |
| Green | 27 |

## Flash the controller

1. In Arduino IDE, install **ESP32 by Espressif Systems** from Boards Manager.
2. Install the **ArduinoJson** library from Library Manager.
3. Open `firmware/esp32_signal_controller/esp32_signal_controller.ino`.
4. Set `WIFI_SSID` and `WIFI_PASSWORD`.
5. Replace `192.168.1.50` with the LAN IPv4 address of the laptop running FlowMirror. Find it with `ipconfig`; use the `IPv4 Address` for the active Wi-Fi adapter.
6. Select **ESP32 Dev Module**, select its COM port, and upload.

## Start FlowMirror for the ESP32

Run the API on every network interface:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Allow Python through the private-network firewall prompt. The ESP32 and laptop
must be on the same Wi-Fi network. Do not use `localhost` in the ESP32 sketch:
on an ESP32 it refers to the ESP32 itself.

The controller polls:

```text
GET /api/signals/signal-E/hardware
```

The response includes the current green phase, remaining duration, reason, and
whether emergency priority is active. If it cannot reach FlowMirror, the yellow
LED flashes to show a safe simulation fallback.

## Demo sequence

1. Start FlowMirror and open the command center.
2. Verify `http://LAPTOP_IP:8000/api/signals/signal-E/hardware` opens from a phone on the same Wi-Fi.
3. Power the ESP32. The green model LED follows FlowMirror's adaptive phase.
4. Create an incident affecting the corresponding corridor. FlowMirror switches to emergency priority and the physical green LED confirms the command.
