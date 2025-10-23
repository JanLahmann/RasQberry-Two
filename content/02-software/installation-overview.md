# RasQberry Installation Overview

> #### **Please Note:** The software image is currently undergoing many updates. As such, the instructions listed here may be slightly out of date. The Installation Overview will be updated shortly.

Below you can find the list of steps that are needed to write the RasQberry Two image to
an SD card and use it in your Rasberry Pi version 4 or 5.

The future available releases of the RasQberry-Two will be stored in the release section
from the Github repository “JanLahmann/RasQberry-pi-gen”
(https://github.com/JanLahmann/RasQberry-pi-gen/tags). An image from this release
section wil also be used in the custom repository configuration of the Pi-imager. You can
find the decription of the pi-imager start with a custom repository incl. rasQberry-two
the section below.

The RasQberry image contains a desktop environment that was adjusted for the
rasqberry-two. Several demos can be found via the desktop menu to start right away with
several Quantum Demos.

This image also contains the RasQberry-two menu structure from the repository
https://github.com/JanLahmann/RasQberry-Two. In your raspi-config menu (open via
command: sudo raspi-config) you can find based on this repositoy the following
rasQberry menu entries.

One-Click Install Run standard RQB2 setup automatically
System Update Update the system and create swapfile
Initial Config Basic configurations (PATH, LOCALE, Python venv, etc)
Qiskit Install Install latest version of Qiskit
Quantum Demos Install Quantum Demos

Please note that currently, only the last menu option “install quantum demos” should
be used. “one-click install” is not needed when using our RasQberry image (and it will
not work).

**! Note:** The standard user is rasqberry with the pwd: “Qiskit1!”
Currently, modifying the username is not supported - and will not work.
We recommend to not change any settings in “Edit Settings” in the Raspberry Pi Imager
(step 7 - 13 below). FYI: ssh and vnc are enabled by default.

![alt text](/installation-images/image.png)

![alt text](/installation-images/image-1.png)

![alt text](/installation-images/image-2.png)

## Steps to write the RasQberry Image to your SD Card

**! Warning:** Ensure there is no important information stored on this SD Card before following these steps.

1. Download and install the Raspberry Pi Imager: https://www.raspberrypi.com/software/

2. Put a formatted SD into the SD card reader of your computer. If your computer does not have an SD Card reader slot, you can use a USB SD Card Reader.

3. Open the Raspberry Pi Imager with the following command in a terminal window. Depending on your OS the command will differ:

   Mac OS

   ```
   /Applications/Raspberry\ Pi\ Imager.app/Contents/MacOS/rpi-imager --repo https://rasqberry.org/RQB-images.json
   ```

   Windows

   ```
   "C:\Program Files (x86)\Raspberry Pi Imager\rpi-imager.exe" --repo https://rasqberry.org/RQB-images.json
   ```

   <br/>

4. Click the `Choose OS` button. Select the operating system `RasQberry Two (64-bit)`

   ![alt text](/installation-images/image-5.png)

   ![alt text](/installation-images/image-6.png)

   ![alt text](/installation-images/image-7.png)

5. Click `Choose Storage` and select the SD Card you inserted in step 2 (e.g. Apple SDCX Reader Media xxx GB).

   ![alt text](/installation-images/image-8.png)

6. Click `Next`.

7. Select `Edit Settings`.

   ![alt text](/installation-images/image-9.png)

8. In the `General` tab, select `Set locale settings` (e.g. for Germany time zone: Europe / Berlin and Keyboard layout: de). User configuration here is optional. The standard user info is:\
   <br />Username: `rasqberry`
   <br />Password: `Qiskit1!`
   <br />
   **! NOTE:** There is no need to specify a username/password in the configuration settings. Doing so might lead to a gray screen when attempting to connect via VNC.

   ![alt text](/installation-images/image-10.png)

9. No further selections are needed in the `Services` tab.

   ![alt text](/installation-images/image-11.png)

10. **Optional**: Select the checkboxes as you can see in the picture below.

    ![alt text](/installation-images/image-12.png)

11. Click `Yes` to apply OS customization settings.

    ![alt text](/installation-images/image-13.png)

12. Click `Yes` to erase all existing data from the SD card and copy the above selected RasQberry image to the SD card.

    ![alt text](/installation-images/image-14.png)

13. The writing process for the RasQberry Pi image will begin and will be completed after verification of the writing process.

    ![alt text](/installation-images/image-15.png)

14. Take the SD Card out of the SD Card reader and put it into your Raspberry Pi 5. Connect power and the RasQberry Pi will boot.
