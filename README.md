# Work in progress
Sony Bravia component for Home Assistant, which can be used for PIN and Pre-Shared Key (PSK) connection

**Example configuration file**

*When using PSK*
```yaml
media_player:
  - platform: braviatv_psk
    host: 192.168.1.191
    psk: sony
    mac: AA:BB:CC:DD:EE:FF
    amp: True
    android: False
    sourcefilter:
      - ' HD'
      - HDMI
```

*When using PIN*
```yaml
media_player:
  - platform: braviatv_psk
    host: 192.168.1.191
    mac: AA:BB:CC:DD:EE:FF
    amp: True
    android: False
    sourcefilter:
      - ' HD'
      - HDMI
```

**Configuration variables:**

* name (Optional): The name to use on the frontend, defaults to Sony Bravia TV.

* host (Required): The IP of the Sony Bravia TV, eg. 192.168.1.191.

* psk (Optional): The Pre-Shared Key of the Sony Bravia TV, eg. sony (see below for instructions how to configure this on the TV). When using a pin with a leading zero, the pin must be placed between quotes.

* mac (Optional): The MAC address of the Sony Bravia TV (see below for instructions how to get this from the TV). Only needed for non Android TV's.

* amp (Optional): Boolean, defaults to False. Set this to True if you have an amplifier attached to the TV and not use the internal TV speakers. Then the volume slider will not be shown as this doesn’t work for the amplifier. Mute and volume up and down buttons are there and working with an amplifier.

* android (Optional): Boolean, defaults to False. Set this to True when you have an Android TV as these TV’s don’t respond to WakeOn LAN commands, so another method of turning on the TV can be used.

* sourcefilter (Optional): List of text that is used to filter the source list, eg. ’ HD’ (with quotes) will only show TV channels in the source list which contain ‘HD’, eg. ‘NPO 3 HD’ (in my config this will only show HD channels).

**Installation instructions TV**

* Enable remote start on your TV: [Settings] => [Network] => [Home Network Setup] => [Remote Start] => [On]

* Enable pre-shared key on your TV: [Settings] => [Network] => [Home Network Setup] => [IP Control] => [Authentication] => [Normal and Pre-Shared Key]

* Set pre-shared key on your TV: [Settings] => [Network] => [Home Network Setup] => [IP Control] => [Pre-Shared Key] => sony

* Give your TV a static IP address, or make a DHCP reservation for a specific IP address in your router

* Determine the MAC address of your TV: [Settings] => [Network] => [Network Setup] => [View Network Status]
