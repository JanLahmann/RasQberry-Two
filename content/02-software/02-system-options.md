# System Options

The System Options allows you to configure system based settings such as WiFi Connectivity. Open your terminal window and connect to the Raspberry Configuration Tool.

```
sudo raspi-config
```

Select `S1 System Options` to configure system settings 
<img width="851" height="269" alt="systemsettings-01" src="https://github.com/user-attachments/assets/78e10ba9-49b8-472f-808a-040c0f50a3b4" />

## Setting up WiFi Connectivity 

Select `S1 Wireless LAN` to configure your WiFi SSID and Passphrase. 

<img width="850" height="276" alt="wifi-01" src="https://github.com/user-attachments/assets/d50544dc-3502-4824-a434-a74496b835dc" />

Specify your WifI `SSID` followed by the `passphrase` (if any) then apply the settings. 
<img width="434" height="302" alt="wifi-02" src="https://github.com/user-attachments/assets/0a32232b-5280-4c7b-a2c9-1abd17dd1872" />

If WiFi is enabled for your network, your device will obtain an IP address via DHCP. To view your WiFi IP address, run this command via terminal:

```
ip address
```
<img width="740" height="105" alt="image" src="https://github.com/user-attachments/assets/ff351437-5f6f-45c5-8cac-3419c395c16f" />

## Connecting to RasQberry Remotely 

There are several ways to connect to your RasQberry Two. SSH and VNC are enabled by default. 

### Connecting to RasQberry Remotely via SSH 

Open a terminal on your remote device and specify your ssh username and IP address. The default username is `rasqberry`.
```
ssh rasqberry@/{your IP address}
```
You need to agree that you want to connect your devices and enter your Raspberry Pi password (default: `Qiskit1!`). Now you should be able to use SSH.

