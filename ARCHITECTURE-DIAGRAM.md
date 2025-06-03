# RasQberry Two - Complete System Architecture

## 🏗️ High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RASQBERRY TWO QUANTUM EDUCATION PLATFORM                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                │
│  │   DEVELOPMENT   │    │      BUILD      │    │   DEPLOYMENT    │                │
│  │   ECOSYSTEM     │────▶│    PIPELINE     │────▶│   & RUNTIME     │                │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘                │
│           │                       │                       │                        │
│           ▼                       ▼                       ▼                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                │
│  │ Multi-Branch    │    │ GitHub Actions  │    │ Raspberry Pi    │                │
│  │ Development     │    │ CI/CD Pipeline  │    │ Hardware        │                │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Development Ecosystem Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DEVELOPMENT BRANCHES                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  main (stable)                                                                      │
│    │                                                                               │
│    ├── feature/multi-qiskit-venvs ────┐                                           │
│    │   • Multiple Qiskit versions      │                                           │
│    │   • Virtual env consolidation     │                                           │
│    │   • 59% space optimization        │                                           │
│    │                                   │                                           │
│    ├── feature/quantum-fractals ───────┼── MERGE ──┐                              │
│    │   • Fractal visualization         │           │                              │
│    │   • Advanced quantum demos        │           │                              │
│    │   • Directory handling fixes      │           │                              │
│    │                                   │           ▼                              │
│    ├── feature/base-stage-caching ─────┤      main (release)                      │
│    │   • Intelligent CI caching        │                                           │
│    │   • 70% build time reduction      │                                           │
│    │   • Immediate cache saving        │                                           │
│    │                                   │                                           │
│    └── feature/config-driven-build ────┘                                           │
│        • Production vs dev builds                                                  │
│        • Quality automation                                                        │
│        • Branch-specific settings                                                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 CI/CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             GITHUB ACTIONS WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  TRIGGER                    JOBS                             OUTPUT                 │
│    │                        │                                │                     │
│    ▼                        ▼                                ▼                     │
│  ┌───────────┐    ┌─────────────────────┐         ┌─────────────────┐             │
│  │           │    │                     │         │                 │             │
│  │  Manual   │───▶│  1. Version Mgmt    │────────▶│  GitHub Release │             │
│  │Workflow   │    │     • Semantic      │         │  • Changelog    │             │
│  │Dispatch   │    │     • Timestamps    │         │  • Artifacts    │             │
│  │           │    │     • Git Tags      │         │  • Downloads    │             │
│  └───────────┘    └─────────────────────┘         └─────────────────┘             │
│                                │                                                   │
│  ┌───────────┐                 ▼                                                   │
│  │           │    ┌─────────────────────┐         ┌─────────────────┐             │
│  │Push to    │───▶│                     │         │                 │             │
│  │dev*       │    │  2. Image Builder   │────────▶│  Pi OS Image    │             │
│  │branches   │    │     • Pi-gen        │         │  • 2GB limit    │             │
│  │           │    │     • Caching       │         │  • XZ compressed│             │
│  └───────────┘    │     • Multi-stage   │         │  • Ready to flash│            │
│                   └─────────────────────┘         └─────────────────┘             │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

                        CACHING STRATEGY DETAIL
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  First Build:          Cached Builds:         Cache Refresh:                       │
│  ┌──────────┐         ┌──────────┐            ┌──────────┐                        │
│  │ Stage 0  │         │ Stage 0  │            │ Stage 0  │                        │
│  │ Stage 1  │ Build   │ Stage 1  │ From       │ Stage 1  │ Rebuild                │
│  │ Stage 2  │ All     │ Stage 2  │ Cache      │ Stage 2  │ All                    │
│  │ Stage 3  │   ↓     │ Stage 3  │ (Fast)     │ Stage 3  │   ↓                    │
│  │ Stage 4  │ Save    │ Stage 4  │   │        │ Stage 4  │ Save                   │
│  ├──────────┤ Cache   ├──────────┤   ▼        ├──────────┤ Cache                  │
│  │ RasQberry│ Immed.  │ RasQberry│ Build      │ RasQberry│ Immed.                 │
│  └──────────┘         └──────────┘ Fresh      └──────────┘                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 🖥️ Runtime System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RASPBERRY PI RUNTIME ENVIRONMENT                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                            USER INTERFACE LAYER                            │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  │  raspi-config   │    │   Desktop GUI   │    │  Terminal/SSH   │        │   │
│  │  │  RQB2 Menu      │    │   Demo Icons    │    │  Command Line   │        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                             │
│                                      ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         QUANTUM DEMO ECOSYSTEM                             │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │ Quantum Lights  │    │ Quantum Fractals│    │ Grok Bloch      │        │   │
│  │  │ Out Game        │    │ Visualization   │    │ Sphere          │        │   │
│  │  │ • LED Matrix    │    │ • WebGL Render  │    │ • 3D Sphere     │        │   │
│  │  │ • Touch Input   │    │ • Selenium Auto │    │ • Web Browser   │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐                               │   │
│  │  │ Quantum Rasp.   │    │ LED Test        │                               │   │
│  │  │ Tie             │    │ Patterns        │                               │   │
│  │  │ • IBM Quantum   │    │ • NeoPixel SPI  │                               │   │
│  │  │ • Real Backend  │    │ • GPIO Control  │                               │   │
│  │  └─────────────────┘    └─────────────────┘                               │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                             │
│                                      ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                        QUANTUM RUNTIME LAYER                               │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  │  Qiskit 2.x     │    │  Qiskit 1.4     │    │   Qiskit 0.44   │        │   │
│  │  │  (Latest)       │    │  (Legacy)       │    │  (Disabled)     │        │   │
│  │  │  • Main demos   │    │  • Fractals     │    │  • Space saving │        │   │
│  │  │  • IBM Runtime  │    │  • Compatibility│    │                 │        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │ Virtual Env     │    │ Package Deps    │    │ System Libraries│        │   │
│  │  │ Management      │    │ • NumPy         │    │ • Python 3.11   │        │   │
│  │  │ • Version Switch│    │ • Matplotlib    │    │ • OpenGL        │        │   │
│  │  │ • PYTHONPATH    │    │ • Selenium      │    │ • GPIO          │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                             │
│                                      ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           HARDWARE LAYER                                   │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  │ Raspberry Pi 4  │    │  LED Strip      │    │  Sense HAT      │        │   │
│  │  │ • ARM64 CPU     │    │  • WS2812B      │    │  • Sensors      │        │   │
│  │  │ • 4GB+ RAM      │    │  • 135 pixels   │    │  • LED Matrix   │        │   │
│  │  │ • GPIO Pins     │    │  • SPI Control  │    │  • Joystick     │        │   │
│  │  │                 │    │                 │    │                 │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  │                                                                             │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │   │
│  │  │ Network         │    │ Storage         │    │ Display         │        │   │
│  │  │ • WiFi/Ethernet │    │ • microSD Card  │    │ • HDMI Output   │        │   │
│  │  │ • SSH Access    │    │ • USB Ports     │    │ • Desktop GUI   │        │   │
│  │  │ • VNC Server    │    │ • Boot Config   │    │ • Web Browser   │        │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 📦 Build System Architecture Detail

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PI-GEN BUILD PROCESS                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  INPUT                        PROCESSING                        OUTPUT             │
│    │                             │                              │                 │
│    ▼                             ▼                              ▼                 │
│  ┌───────────┐    ┌─────────────────────────────┐    ┌─────────────────┐         │
│  │           │    │                             │    │                 │         │
│  │Raspberry  │───▶│  Stage 0: Bootstrap         │───▶│  Base Debian    │         │
│  │Pi OS Base │    │  • Minimal Debian           │    │  System         │         │
│  │           │    │  • Core packages            │    │                 │         │
│  └───────────┘    └─────────────────────────────┘    └─────────────────┘         │
│                                 │                                                 │
│                                 ▼                                                 │
│  ┌───────────┐    ┌─────────────────────────────┐    ┌─────────────────┐         │
│  │           │    │                             │    │                 │         │
│  │Pi Config  │───▶│  Stage 1-4: Standard       │───▶│  Standard Pi    │         │
│  │Settings   │    │  • Desktop environment     │    │  Environment    │         │
│  │           │    │  • Standard packages        │    │                 │         │
│  └───────────┘    └─────────────────────────────┘    └─────────────────┘         │
│                                 │                              ▲                 │
│                                 ▼                              │                 │
│  ┌───────────┐    ┌─────────────────────────────┐             │                 │
│  │           │    │                             │   CACHE     │                 │
│  │RasQberry  │───▶│  Stage RQB2: Custom        │   SAVE      │                 │
│  │Custom     │    │  • Qiskit installation     │─────────────┘                 │
│  │Code       │    │  • Demo integration        │                               │
│  │           │    │  • Hardware configuration  │                               │
│  └───────────┘    └─────────────────────────────┘                               │
│                                 │                                                 │
│                                 ▼                                                 │
│                    ┌─────────────────────────────┐    ┌─────────────────┐         │
│                    │                             │    │                 │         │
│                    │  Image Finalization         │───▶│  RasQberry.img  │         │
│                    │  • Compression (XZ)         │    │  • 2GB target   │         │
│                    │  • Validation               │    │  • Ready to use │         │
│                    └─────────────────────────────┘    └─────────────────┘         │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

                            STAGE BREAKDOWN DETAIL
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  Stage 0:    Bootstrap          Stage 1:    Lite System                           │
│  • Debootstrap                  • Boot files                                      │
│  • Essential packages           • Kernel modules                                  │
│  • Base configuration           • Basic tools                                     │
│                                                                                     │
│  Stage 2:    Desktop Base       Stage 3:    Desktop Environment                  │
│  • X11 system                   • Full desktop                                    │
│  • Window manager               • Applications                                    │
│  • Basic desktop tools          • User interface                                 │
│                                                                                     │
│  Stage 4:    Desktop Complete   Stage RQB2: RasQberry Custom                     │
│  • Full software suite          • Qiskit installation                            │
│  • Educational packages         • Quantum demos                                  │
│  • Ready for customization      • Hardware integration                           │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 🔧 Configuration Management Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          CONFIGURATION HIERARCHY                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  GLOBAL SETTINGS                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  pi-gen-config                                                              │   │
│  │  • Image name, compression                                                  │   │
│  │  • Hardware settings                                                        │   │
│  │  • Production vs Dev quality                                                │   │
│  │  • Git repository configuration                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                             │
│                                      ▼                                             │
│  RUNTIME ENVIRONMENT                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  rasqberry_environment.env                                                  │   │
│  │  • Virtual environment settings                                             │   │
│  │  • Demo requirements mapping                                                │   │
│  │  • Hardware configuration (LEDs, GPIO)                                     │   │
│  │  • User interface settings                                                  │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                             │
│                                      ▼                                             │
│  BRANCH-SPECIFIC OVERRIDES                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  GitHub Actions Workflow                                                    │   │
│  │  • main/beta: Production settings (compression=9, initramfs=0)             │   │
│  │  • dev*: Development settings (compression=3, initramfs=1)                 │   │
│  │  • Dynamic Git variables                                                    │   │
│  │  • Cache strategies                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 📊 System Metrics & Optimizations

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              PERFORMANCE METRICS                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  BUILD TIMES                          STORAGE OPTIMIZATION                         │
│  ┌─────────────────┐                  ┌─────────────────┐                         │
│  │ Without Cache   │                  │ Virtual Envs    │                         │
│  │ • 45+ minutes   │                  │ • 3 separate    │                         │
│  │ • Full rebuild  │                  │   → 1 unified   │                         │
│  │ • Every branch  │                  │ • 1.05GB        │                         │
│  └─────────────────┘                  │   → 430MB       │                         │
│           │                           │ • 59% reduction │                         │
│           ▼                           └─────────────────┘                         │
│  ┌─────────────────┐                                                              │
│  │ With Cache      │                  IMAGE COMPRESSION                           │
│  │ • 15 minutes    │                  ┌─────────────────┐                         │
│  │ • Base cached   │                  │ Level 3 (Dev)   │                         │
│  │ • 70% faster    │                  │ • Fast builds   │                         │
│  └─────────────────┘                  │ • 2.56GB result │                         │
│                                       │                 │                         │
│  CACHE STRATEGY                       │ Level 9 (Prod)  │                         │
│  ┌─────────────────┐                  │ • Small images  │                         │
│  │ Base Stages     │                  │ • <2GB target   │                         │
│  │ • Shared cache  │                  │ • Release ready │                         │
│  │ • Immediate save│                  └─────────────────┘                         │
│  │ • Monthly rotate│                                                              │
│  └─────────────────┘                                                              │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 **Key Architecture Highlights:**

1. **Multi-Branch Development**: Parallel feature development with intelligent merging
2. **Intelligent Caching**: 70% build time reduction through base-stage caching
3. **Configuration-Driven**: Branch-specific quality settings without code changes
4. **Virtual Environment Optimization**: 59% space savings through consolidation
5. **Hardware Integration**: Full GPIO, LED, and sensor support
6. **Educational Focus**: Complete quantum computing demo ecosystem
7. **Production Ready**: Automated compression and quality management

This architecture represents a mature, scalable quantum education platform with sophisticated development and deployment processes.