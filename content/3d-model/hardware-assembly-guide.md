# Hardware Assembly Procedure

This section provides a step-by-step photographic guide on how to assemble the RasQberry Two Platform. The guide is divided into different sections based on the separate sections of the model. The three main components of the RasQberry Two platform are: The Wall, The Cryostat and The Floor.

### Contributors

The following people have contributed to the development of the documentation:

Luka Dojcinovic, Andy Stanford-Clark, Eric H Jenney, Jan-Rainer Lahmann, Sascha Schefenacker

You can contact any of us with questions, concerns or suggestions for changes to the hardware specs and the assembly guide

## Assembly of the Wall

The Wall is the part of the model that represents the server wall behind the real life IBM Quantum System Two. Our rendition of the wall houses all of the vital electronic components of the model and also serves as a housing for the LED display. This part of the assembly guide is likely the most intensive, but fear not; the process is relatively straightforward and when you’re finished you’ll have an amazing looking enclosure for your Raspberry Pi that also functions as a display for all the quantum demos!

Before we begin this guide, it is important that we cover the three main parts of the Wall. These parts will be referenced throughout the remainder of this tutorial:

3D Files used in this section:

- R2M7.0Wall-Back-Dual

- R2M7.6Wall-Test-Base

- R2M7.6Wall-Test-Lid (1)

### Gluing all the pieces together

Depending on whether you printed the components for the wall yourself, and the size of your 3D printer, you might have needed to print the various parts of the Wall in two parts or even more. If you printed all of the components in one part, you can skip this step and move on to the section titled Integrating the Raspberry Pi. For this guide, each major component of The Wall was split in two for easier printing. Once they finished printing, they were cleaned up of any remaining supports and stringing material.

![Figure 1](https://github.com/user-attachments/assets/e087c6cb-26de-49fa-8885-8734fb51734f)

<p align='center'><em>Figure 1: Each sub-assembly of the Wall printed.</em></p>

After cleaning the models, it’s now time to put them together! To ensure that the parts are securely attached, it is recommended to use CA Super Glue to glue the halves together. Super glue can be easily found in most stores, and is popularly sold under brands such as Gorilla Glue, Loctite, Adhear etc. For this guide, we will be using Gorilla Glue:

![Figure 2](https://github.com/user-attachments/assets/f1af3264-ba30-4daa-92e5-36deb341a9dc)

<p align='center'><em>Figure 2: Gorilla super glue used to glue the halves together.</em></p>

**! Warning:**
Super Glue can very easily stick to skin and cause painful injuries. Please use caution when using super glue and never touch the glue while it is drying. Only use a small amount of glue, a little drop goes a long way.

Before gluing the halves together, it is recommended to lightly sand down the upper and lower “lip” of each half. This sanding process will create a smoother surface while also enabling the super glue to form a stronger attachment between the two parts. Once sanded down, apply a small amount of super glue to both the upper and lower lips of the two halves and hold them firmly together.

![Figure 3](https://github.com/user-attachments/assets/20268b4e-1757-4394-b061-5d926eb197d0)

<p align='center'><em>Figure 3: Gluing one half of the Wall base.</em></p>

![Figure 4](https://github.com/user-attachments/assets/3da9a68c-588f-4e54-86e1-ac50bd50c3a7)

<p align='center'><em>Figure 4: Gluing one half of the Wall’s lid.</em></p>

After the two halves have been glued and brought together, it is recommended to let them dry for at least 24 hours. To ensure that they remain connected over this 24 hour period, it is strongly encouraged to use clamps to hold the pieces together while they dry. The following is an example of that:

<p>
  <img align="center" width="500" height="300" src="https://github.com/user-attachments/assets/1b039c83-9233-4830-824a-9071aecd03fc" />
  <img align="center" width="500" height="300"src="https://github.com/user-attachments/assets/921625ed-7bab-4715-899d-d6098da63ce1" />
</p>
<p align='center'><em>Figures 5 & 6: Using clamps to hold the pieces together while they dry.</em></p>

Once 24 hours have elapsed, remove the clamps and verify that the halves are securely attached. If needed, more glue can be added at this point and the drying process repeated. When you are confident in the strength of the components, it’s time to move on to putting them together and adding the Raspberry Pi!

### Setting up the Raspberry Pi

In this section, we will be attaching the Raspberry Pi to the back part of the Wall and completing all of the wiring for the LED array.

Before attaching the Raspberry Pi to the Wall, it is recommended to first install the OS image and complete the setup procedure. Instructions for installing the operating system can be found [here](https://ibm.ent.box.com/file/1639433522353?s=4bgqgtgv7oevdgmpze9vqvk98553fmec&sb=/activity/annotations/1873312986315).

After you have finished flashing the OS image to the micro-SD card, you can insert it into the slot underneath the Pi as such:

![Figure 7](https://github.com/user-attachments/assets/c78ff5af-4ca3-4525-a5c7-3af52f378b8e)

<p align='center'><em>Figure 7: Mounting location for the Micro SD card.</em></p>

Once the OS has been installed, you will need to enable SPI for the LED array to work. To do so, run:

`sudo raspi-config`

In the menu that shows up, navigate to `3. Interface Options` using the arrow keys and press enter. Then, navigate to `I4 SPI` the same way and press enter again. The dialog will ask you `Do you want to enable SPI?`. Hover over the option that says Yes and press enter. Now you’re all set to use SPI!

### Mounting the fan

Before we can wire up the Pi and integrate it into the Wall, it is recommended to mount the Pi 5 Active Cooler onto the board.

![Figure 8](https://github.com/user-attachments/assets/a07bcbb1-1fd1-4698-87d9-2d4c2fe02ecc)

<p align='center'><em>Figure 8: The Raspberry Pi 5 and the Active Cooler.</em></p>

The mounting process for the active cooler is quite straightforward. First, ensure that the protective film covering the bottom of the heat sink is removed:

<p>
  <img align="center" width="500" height="300" src="https://github.com/user-attachments/assets/6c6393a7-0cdd-4353-825b-876fad7dcbda" />
  <img align="center" width="500" height="300" src="https://github.com/user-attachments/assets/284a007e-3d00-4af6-9e5a-e30cb3ebf114" />
</p>

<p align='center'><em>Figure 9: Removing the film from the active cooler.</em></p>

Then, line up the cooler so that it is over the two mounting holes. The correct orientation for the cooler is to place the end with the fan and the colorful cables close to the IO ports (USB, Ethernet etc.). Once you have lined it up correctly, place it down and gently press on the two spring buttons on opposite ends of the cooler. You will hear a click sound when the connector has successfully fastened. Flip the board over to verify that the plastic anchor is all the way through the board:

![Figure 10](https://github.com/user-attachments/assets/8ff7e286-c10c-456d-91dc-5b10525166c6)

<p align='center'><em>Figure 10: Correct mounting orientation for the active cooler.</em></p>

![Figure 11](https://github.com/user-attachments/assets/5a7a4621-f60b-4fdb-8da8-53490c2ad2b1)

<p align='center'><em>Figure 11: View of the plastic anchor correctly secured through the board.</em></p>

Finally, plug the colorful cable into the connector close to the top left spring button you just pushed. There may be a cover on the fan port when you first receive the Pi 5. If so, use some tweezers to gently pull the cover off. Once completed, simply plug the fan cable into that connector:

![Figure 12](https://github.com/user-attachments/assets/3452943e-94cf-4b2e-9a4b-d1ed16135f19)

<p align='center'><em>Figure 12: Fan cable plugged into the fan port.</em></p>

Now you’ve successfully mounted an active cooler to your Raspberry Pi!

![Figure 13](https://github.com/user-attachments/assets/79123800-9845-463f-99dd-899fc52b8064)

<p align='center'><em>Figure 13: Raspberry Pi 5 with Active Cooler mounted.</em></p>

### Wiring up the LED Arrays

The LED array is composed of four identical WS2812IC LED panels. Each one looks like this:

![Figure 14](https://github.com/user-attachments/assets/6312b8a0-ed8f-41ad-bffd-696162ba56df)

<p align='center'><em>Figure 14: One of the LED panels.</em></p>

Each panel has two separate plugs; an input plug and an output plug to chain multiple panels together. The output plug has two latches on the side, while the input plug looks like this:

![Figure 15](https://github.com/user-attachments/assets/979f871d-7885-4911-9a81-21352f7932ce)

<p align='center'><em>Figure 15: The input plug of the LED panel.</em></p>

You will notice that the plugs have three wires; red, green and white. The purpose of these wires is as follows:

Red: This wire is the power lead. This is usually hooked up to 5V and provides all the power needed to turn the LEDs on.

Green: This wire is the SPI interface lead. This will be used to tell our panel which LEDs to turn on and off, depending on which program we run from the Pi.

White: This wire is the ground lead. This is needed to complete the circuit.

To connect the LED array to the Pi, we will need to use jumper wires to connect the Pi’s GPIO to the LED panel’s input plug. GPIO stands for General Purpose Input/Output; it provides a bunch of useful pins that can be used to connect a variety of add-ons and components to the Pi. For this step, we will need three Male to Female Breadboard Jumper wires:

![Figure 16](https://github.com/user-attachments/assets/48f18966-cc47-433b-9791-97acc636aeca)

<p align='center'><em>Figure 16: Three color-coded M-F Breadboard Jumper wires.</em></p>

Now, we need to connect these wires to the Pi’s GPIO on the female end and to the LED panel’s input plug on the male end. I have provided a pinout of the Pi 5’s GPIO below. The three pins we need to connect are circled in their appropriate wire colors.

![Figure 17](https://github.com/user-attachments/assets/2db1b0b8-147f-4444-a6e8-f7f6e41c405e)

<p align='center'><em>Figure 17: GPIO Pinout of the Pi 5, with the needed connections circled in the wire color.</em></p>

Connect the Red wire to Pin 2 (5V). Connect the White wire to Pin 6 (GND). Connect the Green wire to Pin 19 (SPI MOSI GPIO 10). Once finished, your wiring should look like this:

![Figure 18](https://github.com/user-attachments/assets/4fe82a7c-c560-450e-b8b9-8fa1d0761a82)

<p align='center'><em>Figure 18: Wiring the Raspberry Pi.</em></p>

Now we need to connect the male ends to the LED panel. The male end has a bit of exposed wire, this can be carefully slotted into the input plug to achieve a connection:

![Figure 19](https://github.com/user-attachments/assets/e6018529-4b9b-4ce6-a900-3e5f9ba5c5f1)

<p align='center'><em>Figure 19: Plugging the male end of the jumper cable into the LED panel plug.</em></p>

After plugging in all three wires, it should look like this:

![Figure 20](https://github.com/user-attachments/assets/dc2d2937-f8bd-4983-8e6d-bc9a09f0db3b)

<p align='center'><em>Figure 20: Plugging all three jumper cables into the LED plug.</em></p>

Now we’re going to connect that LED panel with the other panels in a chain. Find the output plug of the panel you just wired up and connect it to the input plug of another LED panel. Follow this process for the other two panels until you have a chain of four panels all connected together. You want to make sure they all have the same orientation. Orient your fist panel so that the top left corner has an arrow pointing downwards in the **second** column, then make sure that the other three panels have the same orientation and the same arrow in the top left corner.

![Figure 21](https://github.com/user-attachments/assets/6a9f9fc7-74f2-4f28-ade9-8598b281e950)

<p align='center'><em>Figure 21: Wiring all four LED panels together.</em></p>

After ensuring that all four panels are in line, take the two panels on the right side and bring them down below the other two panels, this will essentially bring the two panels into an upside down orientation. Doing so will give you the arrangement of LEDs as they will be on the wall. Ensure that the bottom two LED panels have arrows in the top left corner pointing downwards in the **first** column.

![Figure 22](https://github.com/user-attachments/assets/ada8b534-b574-4b9d-8072-f91a5aaefd74)

<p align='center'><em>Figure 22: Flipping the last two LED panels underneath.</em></p>

**! Warning:**
The LEDs can be very bright! It is recommended to wear eye protection when working with the LED panels.

Now it’s time to test the LEDs! Run the Python script in your terminal:

```python3 neopixel_spi_IBMtestFunc.py.```

If everything is wired up correctly, you should see the IBM logo appear on the LED array in the correct orientation. Verify that your result looks similar to this:

![Figure 23](https://github.com/user-attachments/assets/ebc9d2c0-2301-4abe-830d-5f5249b4b61e)

<p align='center'><em>Figure 23: Testing the proper orientation of the LED panels before slotting them into the wall.</em></p>

Finally, take the bottom two LED panels and slot them into the space in the wall between the thin pillars and the wider pillars.

![Figure 24](https://github.com/user-attachments/assets/1af1229f-2ba4-4bc6-b376-208a8c02cda2)

<p align='center'><em>Figure 24: Placing the bottom row of LED panels.</em></p>

While making sure to preserve the LED orientation, slot the other two panels on top. You can rest the top row of the LEDs onto the black board of the bottom LEDs.
You can run`python3 neopixel_spi_IBMtestFunc.py` again to help you line up the columns together. Once you’re all done, it should look like this:

![Figure 25](https://github.com/user-attachments/assets/c05e3ad0-7da5-49c6-9602-053927934f64)

<p align='center'><em>Figure 25: Both rows of LED panels lined up.</em></p>

![Figure 26](https://github.com/user-attachments/assets/a214126d-e214-46f2-a5b7-4da5d59f063f)

<p align='center'><em>Figure 26: Resting the top row on top of the bottom row.</em></p>

![Figure 27](https://github.com/user-attachments/assets/b9997d01-a7d6-42f2-a3da-cd5bcf74dbeb)

<p align='center'><em>Figure 27: Testing out panel alignment using the IBM test function.</em></p>

Congratulations! You have successfully wired up the LED panels with the Raspberry Pi!
