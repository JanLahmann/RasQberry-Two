#!/bin/sh
# Auto-generated demo menu cache from manifests
# DO NOT EDIT - regenerate with: rq_demo_generate_menu.sh --cache
#
# Generated: 2026-09-30T08:50:04+02:00
# Manifest directory: /Users/majl/GitHub/RasQberry-Two-dev-backlog/RQB2-config/demo-manifests

# Demo menu items for whiptail (tag description pairs)
# Usage: eval "set -- $DEMO_MENU_ITEMS"; show_menu "$@"
DEMO_MENU_ITEMS='
"grok-bloch" "Grokking the Bloch Sphere"
"grok-bloch-web" "Grokking the Bloch Sphere (Web)"
"quantum-fractals" "Quantum Fractals"
"quantum-lights-out" "Quantum Lights Out"
"quantum-raspberry-tie" "Quantum Raspberry Tie"
"rasq-led" "RasQ-LED Demo"
"led-painter" "LED-Painter"
"composer" "IBM Quantum Composer"
"quantum-mixer" "Quantum-Mixer"
"fun-with-quantum" "Fun with Quantum"
"quantum-paradoxes" "Quantum Paradoxes"
"ibm-tutorials" "IBM Quantum Tutorials"
"ibm-courses" "IBM Quantum Courses"
"qoffee-maker" "Qoffee-Maker"
"quantum-lab" "Quantum Lab (QuBins)"
"doqumentation" "doQumentation (Workshop Server)"
'

# Dispatch function: run demo by ID
# Usage: dispatch_demo_by_id <demo-id>
dispatch_demo_by_id() {
    case "$1" in
        "grok-bloch") /usr/bin/rq_demo_run.sh "grok-bloch" ;;
        "grok-bloch-web") /usr/bin/rq_demo_run.sh "grok-bloch-web" ;;
        "quantum-fractals") /usr/bin/rq_demo_run.sh "quantum-fractals" ;;
        "quantum-lights-out") /usr/bin/rq_demo_run.sh "quantum-lights-out" ;;
        "quantum-raspberry-tie") /usr/bin/rq_demo_run.sh "quantum-raspberry-tie" ;;
        "rasq-led") /usr/bin/rq_demo_run.sh "rasq-led" ;;
        "led-painter") /usr/bin/rq_demo_run.sh "led-painter" ;;
        "composer") /usr/bin/rq_demo_run.sh "composer" ;;
        "quantum-mixer") /usr/bin/rq_demo_run.sh "quantum-mixer" ;;
        "fun-with-quantum") /usr/bin/rq_demo_run.sh "fun-with-quantum" ;;
        "quantum-paradoxes") /usr/bin/rq_demo_run.sh "quantum-paradoxes" ;;
        "ibm-tutorials") /usr/bin/rq_demo_run.sh "ibm-tutorials" ;;
        "ibm-courses") /usr/bin/rq_demo_run.sh "ibm-courses" ;;
        "qoffee-maker") /usr/bin/rq_demo_run.sh "qoffee-maker" ;;
        "quantum-lab") /usr/bin/rq_demo_run.sh "quantum-lab" ;;
        "doqumentation") /usr/bin/rq_demo_run.sh "doqumentation" ;;
        *) echo "Unknown demo: $1" >&2; return 1 ;;
    esac
}

# Get launcher script for demo ID
# Usage: get_demo_launcher <demo-id>
get_demo_launcher() {
    case "$1" in
        "grok-bloch") echo "/usr/bin/rq_demo_run.sh grok-bloch" ;;
        "grok-bloch-web") echo "/usr/bin/rq_demo_run.sh grok-bloch-web" ;;
        "quantum-fractals") echo "/usr/bin/rq_demo_run.sh quantum-fractals" ;;
        "quantum-lights-out") echo "/usr/bin/rq_demo_run.sh quantum-lights-out" ;;
        "quantum-raspberry-tie") echo "/usr/bin/rq_demo_run.sh quantum-raspberry-tie" ;;
        "rasq-led") echo "/usr/bin/rq_demo_run.sh rasq-led" ;;
        "led-painter") echo "/usr/bin/rq_demo_run.sh led-painter" ;;
        "composer") echo "/usr/bin/rq_demo_run.sh composer" ;;
        "quantum-mixer") echo "/usr/bin/rq_demo_run.sh quantum-mixer" ;;
        "fun-with-quantum") echo "/usr/bin/rq_demo_run.sh fun-with-quantum" ;;
        "quantum-paradoxes") echo "/usr/bin/rq_demo_run.sh quantum-paradoxes" ;;
        "ibm-tutorials") echo "/usr/bin/rq_demo_run.sh ibm-tutorials" ;;
        "ibm-courses") echo "/usr/bin/rq_demo_run.sh ibm-courses" ;;
        "qoffee-maker") echo "/usr/bin/rq_demo_run.sh qoffee-maker" ;;
        "quantum-lab") echo "/usr/bin/rq_demo_run.sh quantum-lab" ;;
        "doqumentation") echo "/usr/bin/rq_demo_run.sh doqumentation" ;;
        *) return 1 ;;
    esac
}


# Total demos: 16
DEMO_COUNT=16
