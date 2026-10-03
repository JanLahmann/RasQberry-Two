# Tips and Tricks from Jan

Tips from my own builds: the 3D model, the LED panel, the beta and the A/B
image, and working on the software.

## 3D model

Some STL files I changed for my printer or for a variant of the model are in the
[3D Model modifications folder](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/3D%20Model%20-%20modifications%20-%20Jan).

### Standalone model

The standalone model has no floor. Several of them together resemble the modular
structure of IBM Quantum System Two: you can rearrange the elements and build
larger systems. So the screw holes are gone, and instead of the double-wide RTEs
it uses the small ones, with four magnets each (two on each side).

### LED filter screen

Instead of cutting a welding shield, you can print the screen in front of the
LEDs. Most black filaments absorb too much light, but 0.6 mm of Prusament PLA
Galaxy Grey works well:
[STL file](https://github.com/JanLahmann/RasQberry-Two/blob/3D-model/3D%20Model/3D%20Model%20-%20modifications%20-%20Jan/October%202025/wall/RQB2-WallPanel-jrl02-2.stl).

## LED panel: one 8×32 panel, cut to 8×24

I recommend one flexible 8×32 WS2812B panel, cut to 8×24 (192 LEDs), over the
four 4×12 panels in the Bill of Materials: one piece means no wiring between
panels and no seams. Cut between two columns and keep the end with the data
input. The LED check in the setup checklist works with both kits.

Use the official 27 W power supply for the Pi 5. On a weaker supply a bright
panel can make the LEDs stop until the next restart.

## The beta and the A/B image

- **Card:** 128 GB, A2/U3. The A/B image then holds two systems, each with room
  for all Docker demos.
- **Updates:** install a new release into Slot B and try it. Make Slot B the
  stable system only once you are happy with it; until then Slot A is your way back.
- **Keep your files in Shared:** that folder, your IBM Quantum account, Wi-Fi and
  LED settings move with every update. The rest of your home folder stays in its slot.
- **Docker demos belong to one system:** after an update they download again.
- **Tell us how it goes:** the beta is tested on a Pi 5 and a Pi 4 on my desk, not
  in your classroom. Your feedback is highly appreciated:
  [open an issue](https://github.com/JanLahmann/RasQberry-Two/issues).

More in [A/B image](/02-software/03-ab-boot/).

## Working on the software

### Forking the repository

The image workflow takes the repository and user name from the GitHub context,
so a fork usually builds without changes. `RQB_GIT_USER`, `RQB_GIT_BRANCH` and
`RQB_REPO` in `pi-gen-config` are filled in by the workflow.

### Trying changes on a running Pi

A full image build takes a while. To test scripts (like `RQB2_menu.sh`) on a
running Pi, update them from a branch:

```bash
# Update from a specific branch (auto-detects repository)
sudo rq_update_from_branch.sh --branch dev-features05

# Update from a different repository
sudo rq_update_from_branch.sh --repo YourUser/RasQberry-Two --branch development

# Preview changes without applying them
sudo rq_update_from_branch.sh --branch dev --dry-run
```

This updates the scripts in `/usr/bin/`, the files in `/usr/config/` and the
system files (systemd units, autostart entries). Device settings in
`rasqberry_environment.env`, such as the LED layout, are kept: new keys arrive,
existing values stay. The same function is in `sudo raspi-config` →
**0 RasQberry** → **Advanced** → **Update from GitHub Branch**. Kernel, packages
and the partition layout need a new image or an A/B update.

### Building images

GitHub Actions builds the images (`.github/workflows/RQB-image-v2.yaml`,
"Rasqberry Pi Image Release v2"):

- **Automatic:** every push to a `dev*` branch, `development` included.
- **Manual:** Actions → "Rasqberry Pi Image Release v2" → "Run workflow". Inputs:
  `version` (required for `main`), `build_scope` (`ab-only`, `standard-image`,
  `full`, `no-release`), `console_type`, `boot_verbosity` and `runner_type`.
- By default every build produces both the standard and the A/B image.
