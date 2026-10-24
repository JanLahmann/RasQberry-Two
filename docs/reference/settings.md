<!-- Generated from the code by docs/reference/reference_docs.py; do not edit. -->

# Settings

RasQberry's settings live in `/usr/config/rasqberry_environment.env` (shipped defaults below). Change them in the RasQberry menu where it offers them, or under **Advanced > Edit a RasQberry Two setting**. Settings marked **kept** are also stored on the /data partition, so they survive an A/B image update.


## LED configuration

- `LED_COUNT` = `192` **kept**: Number of LED pixels (4*4*12 = 192, supports 1000+ LEDs with PWM/PIO drivers). NOTE: when LED_LAYOUT is set, the count is DERIVED from the layout definition (sum of panel sizes) and this value is used only as a fallback.
- `LED_GPIO_PIN` = `18` **kept**: GPIO pin connected to the pixels (GPIO18 for both Pi4 PWM and Pi5 PIO) Pi 4: the panel uses the PWM hardware that the headphone socket also uses. The rig showed no LED glitches with analogue sound playing (R-113), but the driver's authors advise against both together: for sound use HDMI audio.
- `LED_PIXEL_ORDER` = `GRB` **kept**: LED Pixel Order: RGB, GRB, RGBW, GRBW (most WS2812B LEDs use GRB)
- `LED_DEFAULT_BRIGHTNESS` = `0.4` **kept**: LED Default Brightness (0.0-1.0, where 1.0 is maximum) Current: a WS2812B LED draws up to about 60 mA at full white, so a full white 192-LED panel draws about 4.5 A at 0.4 and over 11 A at 1.0. A panel powered from the Pi's 5V pin must stay well below what the Pi's power supply has left: keep 0.4 or lower there, and use a separate 5V supply for more.
- `LED_MAX_BRIGHTNESS` = `1.0` **kept**: Upper limit for every LED demo's brightness, also for demos that choose their own (1.0 = no limit). Set together with the default by RasQberry menu > Quantum Demos > LED panel > LED setup & tests > LED brightness, which also offers a lower level after the Pi 5's LED driver stalled on a weak power supply.
- `LED_LAYOUT` = `single-24x8` **kept**: LED layout: names an entry in the layout registry (led-layouts.json). Both kits are supported (Q11): one 24x8 panel (single-24x8) and four 4x12 panels (quad-4x12); also triple-8x8 (all 192 LEDs / 24x8). Geometry and LED_COUNT are DERIVED from the selected layout. The LED panel check of the setup checklist sets it; it asks without a pre-selected answer.
- `LED_LAYOUT_VERIFIED` = `false` **kept**: LED panel check (setup checklist, LED menu): false = not checked yet, true = the person saw the IBM logo upright with this layout, skipped = "no LED panel yet" (not offered again; the LED menu still has the check).
- `N_QUBIT` = `192`: Qubit count (typically matches LED_COUNT: 4*4*12 = 192)
- `LED_FREQ_HZ` = `800000` **kept**: DEPRECATED advanced LED settings - retained for back-compat but NOT used by the current PWM/PIO driver path (kept so old images/scripts don't break). DEPRECATED: LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_CHANNEL (never read)
- `LED_DMA` = `10` **kept**
- `LED_INVERT` = `false` **kept**
- `LED_CHANNEL` = `0` **kept**
- `LED_PHYSICAL` = `true` **kept**: Output targets (#231): independent booleans - drive any combination. LED_PHYSICAL: drive the real LED strip LED_VIRTUAL:  drive the mmap/GUI emulator (rq_led_virtual_gui.py, on-screen Tk) LED_WEB:      serve a browser view of the same matrix (rq_led_web.py); open http://<pi>:${LED_WEB_PORT} from any device on the network. Reads the same mmap frame bus as LED_VIRTUAL, so it needs no hardware and can run alongside or instead of the strip/GUI. Default matches previous shipped behavior (LED_VIRTUAL_MIRROR=true): physical strip plus on-screen virtual display.
- `LED_VIRTUAL` = `true` **kept**
- `LED_WEB` = `false` **kept**
- `LED_WEB_PORT` = `8098` **kept**: Port for the LED_WEB browser emulator (chosen clear of the demo ports).
- `LED_VIRTUAL_MIRROR` = `false` **kept**: DEPRECATED: LED_VIRTUAL_MIRROR - superseded by LED_PHYSICAL + LED_VIRTUAL. For one release, when LED_PHYSICAL is UNSET, LED_VIRTUAL_MIRROR=true still maps to physical+virtual. Prefer the explicit flags above.
- `LED_RENDER_MODE` = `direct` **kept**: Render mode: how LED programs reach the panel. LED demos run as the desktop user (in a sandbox) in both modes. - direct  (default): by board. Raspberry Pi 5: the program drives the panel itself. Raspberry Pi 4 (its LED driver needs root): the demo's launcher, rq_python and LED-Painter start rasqberry-led-renderer for the run and stop it afterwards; the program sends its frames to it. Leave the service disabled: running all the time, it holds the panel ("LED panel in use"). - service: every LED program only sends frames; the root rasqberry-led-renderer drives the panel, on every board. Keep it running (rq_python and LED-Painter expect it): sudo systemctl enable --now rasqberry-led-renderer.service

## Display/interface settings

- `TOUCH_MODE_ENABLED` = `false`: Touch Mode: Enable touch-friendly interface (larger buttons, on-screen keyboard) Values: true/false (managed by rq_touch_mode.sh)
- `TOUCH_PANEL_HEIGHT` = `64`: Touch mode customization (sizes applied when touch mode is enabled) Adjust these values for different screen sizes or preferences
- `TOUCH_PANEL_ICON_SIZE` = `48`
- `TOUCH_DESKTOP_ICON_SIZE` = `72`
- `TOUCH_DESKTOP_GRID_SPACING` = `140`
- `TOUCH_TERMINAL_FONT_SIZE` = `12`: At most 12 (bigger dialogs no longer fit); unchanged on screens lower than 600 px
- `TOUCH_DOUBLE_CLICK_MS` = `500`

## Demo loop configuration

- `DEMO_LOOP_DEMOS` = `all`: Which demos the loop shows: all, or a comma-separated list of ibm-logo, quantum-lights-out, quantum-raspberry-tie, rasq-led, quantum-fractals (Quantum Demos > Workshops & events > Demo Loop > Choose the demos)
- `DEMO_LOOP_IBM_LOGO_TIME` = `15`
- `DEMO_LOOP_LIGHTS_OUT_TIME` = `60`
- `DEMO_LOOP_RASQBERRY_TIE_TIME` = `60`
- `DEMO_LOOP_RASQ_LED_TIME` = `60`
- `DEMO_LOOP_QUANTUM_FRACTALS_TIME` = `90`
- `DEMO_LOOP_PAUSE` = `2`
- `DEMO_LOOP_AT_LOGIN` = `false`: Start the loop at desktop login, instead of the browser (Demo Loop menu)



## Advanced/system variables

- `PI_MODEL` = `Pi5`: Hardware Detection (auto-detected at boot by rq_detect_hardware.sh)
- `REPO` = `RasQberry-Two`: Repository configuration
- `RQB_GIT_USER` = `JanLahmann`
- `STD_VENV` = `RQB2`
- `RQB_BUILD_REPO` = `(empty)`: Where this image was built from (filled in by the image build; empty on images built before #289). Default for "Update from GitHub Branch".
- `RQB_BUILD_BRANCH` = `(empty)`
- `RQB_BUILD_COMMIT` = `(empty)`
- `BROWSER_AUTOSTART` = `true`: Open Chromium with rasqberry.org at desktop login (#227). RasQberry -> Desktop: browser at login, or set to false here.
- `RQ_AUDIO_DELAY_MS` = `0` **kept**: Sound delay in milliseconds (0-2000): how long LEDs in demos with sound wait for the speaker. Bluetooth speakers play 100-300 ms late. RasQberry -> Desktop Settings -> Sound delay. Demos read RQ_AUDIO_DELAY_MS.
- `HOTSPOT_BAND` = `a` **kept**: Wi-Fi hotspot for booths and classrooms (rq_hotspot.sh on|off|status|qr). HOTSPOT_BAND a (5 GHz) or bg (2.4 GHz); HOTSPOT_INTERFACE auto (a USB Wi-Fi adapter first; tested: TP-Link Archer T2U Nano) or a device name; HOTSPOT_SHARE_INTERNET yes/no; HOTSPOT_AT_BOOT yes/no. Kept across A/B updates (/data). Name and password are not here: this file is loaded as shell code and anyone can read it. They are in a root-only file (sudo rq_hotspot.sh get HOTSPOT_SSID; set them in the menu or with rasqberry-hotspot.txt on the boot partition).
- `HOTSPOT_INTERFACE` = `auto` **kept**
- `HOTSPOT_SHARE_INTERNET` = `yes` **kept**
- `HOTSPOT_AT_BOOT` = `no` **kept**
- `HOTSPOT_ALLOW_ADMIN` = `auto` **kept**: SSH and VNC from devices on the hotspot, whose password is on a public card. auto: only once no account that can use sudo has the published default password any more (checked at every start and sync); no: never; yes: always
- `RQ_NO_MESSAGES` = `false`: Interactive mode settings (INTERACTIVE, ASK_TO_REBOOT and CONFIG used to be here. They are raspi-config's own variables, and loading them inside raspi-config broke its dialogs - R-001. Never add them back; rq_env_merge.py drops them from older files.)
- `OS_VERSION` = `none`: OS version (set during build)

## Demo-specific configuration

- `RASQ_LED_DISPLAY_TIMEOUT` = `3` **kept**: RasQ-LED Demo timeout in seconds
- `GIT_REPO_DEMO_QOFFEE` = `https://github.com/JanLahmann/Qoffee-Maker.git`: Qoffee-Maker and Quantum-Mixer: their sources and Docker images are pinned per release in the demo manifests (install.source, entrypoint.docker_image). DEPRECATED: GIT_REPO_DEMO_QOFFEE, QOFFEE_DOCKER_IMAGE, GIT_REPO_DEMO_QUANTUM_MIXER, QUANTUM_MIXER_DOCKER_IMAGE (not read)
- `QOFFEE_DOCKER_IMAGE` = `ghcr.io/janlahmann/qoffee-maker`
- `QOFFEE_PORT` = `8887`
- `GIT_REPO_DEMO_QUANTUM_MIXER` = `https://github.com/JanLahmann/quantum-mixer.git`
- `QUANTUM_MIXER_DOCKER_IMAGE` = `quantum-mixer:arm64`
- `GIT_REPO_DEMO_FWQ` = `https://github.com/JanLahmann/fun-with-quantum.git`: Fun-with-Quantum
- `MARKER_FWQ` = `Quantum-Coin-Game.ipynb`
- `FWQ_JUPYTER_PORT` = `8888`
- `GIT_REPO_DEMO_QRT` = `https://github.com/KPRoche/quantum-raspberry-tie.git`: Quantum-Raspberry-Tie
- `PATCH_FILE_QRT` = `quantum-raspberry-tie.patch`
- `GIT_REPO_DEMO_QLO` = `https://github.com/Luka-D/Quantum-Lights-Out.git`: Quantum-Lights-Out
- `MARKER_QLO` = `lights_out.py`
- `PATCH_FILE_QLO` = `quantum-lights-out.patch`
- `GIT_REPO_DEMO_GROK_BLOCH` = `https://github.com/JavaFXpert/grok-bloch.git`: Grok-Bloch
- `MARKER_GROK_BLOCH` = `index.html`
- `GIT_REPO_DEMO_LED_PAINTER` = `https://github.com/Luka-D/RasQberry-Two-LED-Painter.git`: LED-Painter
- `MARKER_LED_PAINTER` = `LED_painter.py`
- `GIT_REPO_DEMO_PARADOXES` = `https://github.com/maria-violaris/quantum-paradoxes`: Quantum-Paradoxes
- `MARKER_PARADOXES` = `WELCOME.ipynb`
- `PARADOXES_JUPYTER_PORT` = `8891`
- `GIT_REPO_DEMO_IBM_LEARNING` = `https://github.com/Qiskit/documentation.git`: IBM Quantum Tutorials & Courses (from Qiskit documentation - CC BY-SA 4.0)
- `MARKER_IBM_TUTORIALS` = `WELCOME-tutorials.ipynb`: (its pinned commit: install.source.ref in demo-manifests/rq_demo_ibm-courses.json)
- `MARKER_IBM_COURSES` = `WELCOME-courses.ipynb`
- `IBM_TUTORIALS_JUPYTER_PORT` = `8889`
- `IBM_COURSES_JUPYTER_PORT` = `8890`

## Installed demos (internal)

Flags the demo installers set (true/false), one per demo: `TEST_LED_INSTALLED`, `QUANTUM_LIGHTS_OUT_INSTALLED`, `QUANTUM_RASPBERRY_TIE_INSTALLED`, `GROK_BLOCH_INSTALLED`, `QUANTUM_FRACTALS_INSTALLED`, `LED_PAINTER_INSTALLED`, `QOFFEE_MAKER_INSTALLED`, `QUANTUM_MIXER_INSTALLED`, `FUN_WITH_QUANTUM_INSTALLED`, `QUANTUM_PARADOXES_INSTALLED`, `IBM_TUTORIALS_INSTALLED`, `IBM_COURSES_INSTALLED`.
