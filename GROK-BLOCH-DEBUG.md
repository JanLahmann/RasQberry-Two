# Grok Bloch Demo Failure Analysis

## 🔍 **Potential Failure Points:**

### **1. Environment Loading Issues**
```bash
# Script loads environment from:
. $HOME/.local/bin/env-config.sh

# Check if this file exists and is accessible
# Check if required variables are set: REPO, GROK_BLOCH_INSTALLED
```

### **2. Demo Installation Issues**
```bash
# Repository URL: https://github.com/JavaFXpert/grok-bloch.git
# Expected file: $HOME/$REPO/demos/grok-bloch/index.html
# Installation flag: GROK_BLOCH_INSTALLED=true (in rasqberry_environment.env)

# Potential issues:
# - Git clone failure (network, repository access)
# - Missing demos directory
# - File permissions
# - Repository structure changed
```

### **3. Runtime Dependencies**
```bash
# Required for HTTP server:
python3 -m http.server $PORT

# Required for browser launch:
# - chromium-browser, OR
# - firefox, OR  
# - xdg-open

# Potential issues:
# - Python3 not available
# - No browsers installed
# - Display environment issues (DISPLAY variable)
# - X11 forwarding problems
```

### **4. Network/Port Issues**
```bash
# Uses netstat to find available port starting from 8080
# Potential issues:
# - netstat command not available
# - All ports in range already in use
# - Firewall blocking local connections
```

## 🛠 **Debugging Steps:**

### **Step 1: Check Environment**
```bash
# Test environment loading
. $HOME/.local/bin/env-config.sh
echo "REPO: $REPO"
echo "GROK_BLOCH_INSTALLED: $GROK_BLOCH_INSTALLED"
echo "GIT_REPO_DEMO_GROK_BLOCH: $GIT_REPO_DEMO_GROK_BLOCH"
```

### **Step 2: Check Installation**
```bash
# Check if demo is installed
DEMO_DIR="$HOME/$REPO/demos/grok-bloch"
echo "Demo directory: $DEMO_DIR"
ls -la "$DEMO_DIR"
echo "Index file exists: $(test -f "$DEMO_DIR/index.html" && echo "YES" || echo "NO")"
```

### **Step 3: Test Manual Installation**
```bash
# Try manual git clone
mkdir -p "$HOME/$REPO/demos"
cd "$HOME/$REPO/demos"
git clone https://github.com/JavaFXpert/grok-bloch.git
echo "Clone result: $?"
ls -la grok-bloch/
```

### **Step 4: Test HTTP Server**
```bash
# Test Python HTTP server
cd "$DEMO_DIR"
python3 -m http.server 8080 &
SERVER_PID=$!
sleep 2
curl -I http://localhost:8080 2>/dev/null | head -1
kill $SERVER_PID
```

### **Step 5: Test Browser Availability**
```bash
# Check browser availability
echo "chromium-browser: $(command -v chromium-browser || echo "NOT FOUND")"
echo "firefox: $(command -v firefox || echo "NOT FOUND")"  
echo "xdg-open: $(command -v xdg-open || echo "NOT FOUND")"
echo "DISPLAY: $DISPLAY"
```

### **Step 6: Check Network Tools**
```bash
# Check netstat availability
echo "netstat: $(command -v netstat || echo "NOT FOUND")"
# Alternative: use ss command
echo "ss: $(command -v ss || echo "NOT FOUND")"
```

## 🐛 **Common Issues & Solutions:**

### **Issue 1: Repository Access**
- **Problem**: Can't clone grok-bloch repository
- **Solution**: Check network connectivity, try manual clone
- **Alternative**: Use local copy or different repository

### **Issue 2: Missing Dependencies**
- **Problem**: Python3 or browsers not installed
- **Solution**: Install missing packages:
  ```bash
  sudo apt-get update
  sudo apt-get install python3 chromium-browser
  ```

### **Issue 3: Display Issues**
- **Problem**: No DISPLAY environment for X11
- **Solution**: 
  - For SSH: Use `ssh -X` for X11 forwarding
  - For VNC: Ensure VNC server is running
  - For console: Run in text mode or use different demo

### **Issue 4: Permission Issues**
- **Problem**: Can't write to demo directory
- **Solution**: Fix ownership:
  ```bash
  sudo chown -R $USER:$USER "$HOME/$REPO"
  ```

### **Issue 5: Port Conflicts**
- **Problem**: HTTP server can't bind to port
- **Solution**: Script should auto-increment port, but check:
  ```bash
  netstat -tuln | grep :8080
  ```

## 🎯 **Enhanced Error Reporting:**

Add debug output to rq_grok_bloch.sh:
```bash
# Add at the beginning:
set -x  # Enable debug output
echo "DEBUG: Starting Grok Bloch launcher"
echo "DEBUG: HOME=$HOME"
echo "DEBUG: USER=$USER"

# Add before each major step:
echo "DEBUG: Loading environment..."
echo "DEBUG: Checking demo directory..."
echo "DEBUG: Starting HTTP server..."
echo "DEBUG: Looking for browsers..."
```