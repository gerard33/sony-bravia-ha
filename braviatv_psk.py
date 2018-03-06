"""
Support for interface with a Sony Bravia TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.braviatv_psk/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_SET, SUPPORT_SELECT_SOURCE,
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_TVSHOW, SUPPORT_STOP)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_MAC, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

# REQUIREMENTS = ['pySonyBraviaPSK==0.1.5']
REQUIREMENTS = [
    'https://github.com/gerard33/sony_bravia_psk/archive/0.2.3.zip'
    '#sony_bravia_psk==0.2.3']

_LOGGER = logging.getLogger(__name__)

SUPPORT_BRAVIA = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
                 SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                 SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                 SUPPORT_SELECT_SOURCE | SUPPORT_PLAY | SUPPORT_STOP

BRAVIA_CONFIG_FILE = 'bravia.conf'
CLIENTID_PREFIX = 'HomeAssistant'
NICKNAME = 'Home Assistant'
DEFAULT_NAME = 'Sony Bravia TV'

# Map ip to request id for configuring
_CONFIGURING = {}

# Config file
CONF_PSK = 'psk'
CONF_AMP = 'amp'
CONF_ANDROID = 'android'
CONF_SOURCE_FILTER = 'sourcefilter'
CONF_BROADCAST = 'broadcast'

# Some additional info to show specific for Sony Bravia TV
TV_WAIT = 'TV started, waiting for program info'
PLAY_MEDIA_OPTIONS = [
    'Num1', 'Num2', 'Num3', 'Num4', 'Num5', 'Num6', 'Num7', 'Num8', 'Num9',
    'Num0', 'Netflix', 'Display', 'ChannelUp', 'ChannelDown', 'Up', 'Down',
    'Left', 'Right', 'Confirm', 'Home', 'EPG', 'Return', 'Options', 'Exit'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PSK): cv.string,  ###aanpassen naar str, https://github.com/home-assistant/home-assistant/pull/12934/files
    vol.Optional(CONF_MAC): cv.string,
    vol.Optional(CONF_BROADCAST, default="255.255.255.255"): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_AMP, default=False): cv.boolean,
    vol.Optional(CONF_ANDROID, default=False): cv.boolean,
    vol.Optional(CONF_SOURCE_FILTER, default=[]): vol.All(
        cv.ensure_list, [cv.string])})

# pylint: disable=unused-argument


def _get_mac_address(ip_address):
    """Get the MAC address of the device."""
    from subprocess import Popen, PIPE

    pid = Popen(["arp", "-n", ip_address], stdout=PIPE)
    pid_component = pid.communicate()[0]
    match = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})".encode('UTF-8'),
                      pid_component)
    if match is not None:
        return match.groups()[0]
    return None

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sony Bravia TV platform."""
    host = config.get(CONF_HOST)
    psk = config.get(CONF_PSK)
    mac = config.get(CONF_MAC)
    broadcast = config.get(CONF_BROADCAST)
    name = config.get(CONF_NAME)
    amp = config.get(CONF_AMP)
    android = config.get(CONF_ANDROID)
    source_filter = config.get(CONF_SOURCE_FILTER)
    pin = None

    if host is None:
        _LOGGER.error("No TV IP address found in configuration file")
        return

    # If no PSK is entered in the config file the PIN config is started
    if psk is None:
        bravia_config = load_json(hass.config.path(BRAVIA_CONFIG_FILE))
        while bravia_config:
            # Set up a configured TV
            host_ip, host_config = bravia_config.popitem()
            if host_ip == host:
                pin = host_config['pin']
                mac = host_config['mac']
                name = config.get(CONF_NAME)
                add_devices([BraviaTVDevice(host, psk, mac, broadcast, name,
                                            pin, amp, android, source_filter)])
                return

        setup_bravia(config, pin, hass, add_devices)
    else:
        add_devices([BraviaTVDevice(host, psk, mac, broadcast, name,
                                    pin, amp, android, source_filter)])

def setup_bravia(config, pin, hass, add_devices):
    """Set up a Sony Bravia TV based on host parameter."""
    host = config.get(CONF_HOST)
    psk = config.get(CONF_PSK)
    mac = config.get(CONF_MAC)
    name = config.get(CONF_NAME)
    amp = config.get(CONF_AMP)
    android = config.get(CONF_ANDROID)
    source_filter = config.get(CONF_SOURCE_FILTER)

    if pin is None:
        request_configuration(config, hass, add_devices)
        return
    else:
        mac = _get_mac_address(host)
        if mac is not None:
            mac = mac.decode('utf8')
        # If we came here and configuring this host, mark as done
        if host in _CONFIGURING:
            request_id = _CONFIGURING.pop(host)
            configurator = hass.components.configurator
            configurator.request_done(request_id)
            _LOGGER.info("Discovery configuration done")

        # Save config
        save_json(
            hass.config.path(BRAVIA_CONFIG_FILE),
            {host: {'pin': pin, 'host': host, 'mac': mac}})

        add_devices([BraviaTVDevice(host, psk, mac, broadcast, name,
                                    pin, amp, android, source_filter)])


def request_configuration(config, hass, add_devices):
    """Request configuration steps from the user."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    configurator = hass.components.configurator

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")
        return

    def bravia_configuration_callback(data):
        """Handle the entry of user PIN."""
        from braviapsk import sony_bravia_psk

        pin = data.get('pin')
        braviarc = sony_bravia_psk.BraviaRC(host)
        braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
        if braviarc.is_connected():
            setup_bravia(config, pin, hass, add_devices)
        else:
            request_configuration(config, hass, add_devices)

    _CONFIGURING[host] = configurator.request_config(
        name, bravia_configuration_callback,
        description='Enter the Pin shown on your Sony Bravia TV.' +
        'If no Pin is shown, enter 0000 to let TV show you a Pin.',
        description_image="/static/images/smart-tv.png",
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the pin', 'type': ''}]
    )


class BraviaTVDevice(MediaPlayerDevice):
    """Representation of a Sony Bravia TV."""

    def __init__(self, host, psk, mac, broadcast, name, pin, amp, android,
                 source_filter):
        """Initialize the Sony Bravia device."""
        _LOGGER.info("Setting up Sony Bravia TV")
        from braviapsk import sony_bravia_psk

        self._braviarc = sony_bravia_psk.BraviaRC(host, psk, mac)
        self._name = name
        self._psk = psk
        self._pin = pin
        self._broadcast = broadcast
        self._amp = amp
        self._android = android
        self._source_filter = source_filter
        self._state = STATE_OFF
        self._muted = False
        self._program_name = None
        self._channel_name = None
        self._channel_number = None
        self._source = None
        self._source_list = []
        ###self._original_content_list = []
        self._content_mapping = {}
        self._duration = None
        self._content_uri = None
        ###self._id = None
        self._playing = False
        self._start_date_time = None
        self._program_media_type = None
        self._min_volume = None
        self._max_volume = None
        self._volume = None
        self._start_time = None
        self._end_time = None

        if self._psk:
            _LOGGER.debug(
                "Set up Sony Bravia TV withIP: %s, PSK: %s, MAC: %s",
                host, psk, mac)
            self.update()
        else:
            self._braviarc.connect(pin, CLIENTID_PREFIX, NICKNAME)
            if self._braviarc.is_connected():
                self.update()
            else:
                self._state = STATE_OFF

    def update(self):
        """Update TV info."""
        if not self._psk:
            if not self._braviarc.is_connected():
                if self._braviarc.get_power_status() != 'off':
                    self._braviarc.connect(
                        self._pin, CLIENTID_PREFIX, NICKNAME)
                if not self._braviarc.is_connected():
                    return
        try:
            power_status = self._braviarc.get_power_status()
            if power_status == 'active':
                self._state = STATE_ON
                self._refresh_volume()
                self._refresh_channels()
                playing_info = self._braviarc.get_playing_info()
                self._reset_playing_info()
                if playing_info is None or not playing_info:
                    self._program_name = 'No info (resumed after pause or \
                                          app opened)'
                else:
                    self._program_name = playing_info.get('programTitle')
                    self._channel_name = playing_info.get('title')
                    self._program_media_type = playing_info.get(
                        'programMediaType')
                    self._channel_number = playing_info.get('dispNum')
                    self._source = playing_info.get('source')
                    self._content_uri = playing_info.get('uri')
                    self._duration = playing_info.get('durationSec')
                    self._start_date_time = playing_info.get('startDateTime')
                    # Get time info from TV program
                    if self._start_date_time and self._duration:
                        time_info = self._braviarc.playing_time(
                            self._start_date_time, self._duration)
                        self._start_time = time_info.get('start_time')
                        self._end_time = time_info.get('end_time')
            else:
                if self._program_name == TV_WAIT:
                    # TV is starting up, takes some time before it responds
                    _LOGGER.info("TV is starting, no info available yet")
                else:
                    self._state = STATE_OFF

        except Exception as exception_instance:  # pylint: disable=broad-except
            _LOGGER.error("No data received from TV. Error message: %s",
                          exception_instance)
            self._state = STATE_OFF

    def _reset_playing_info(self):
        self._program_name = None
        self._channel_name = None
        self._program_media_type = None
        self._channel_number = None
        self._source = None
        self._content_uri = None
        self._duration = None
        self._start_date_time = None
        self._start_time = None
        self._end_time = None

    def _refresh_volume(self):
        """Refresh volume information."""
        volume_info = self._braviarc.get_volume_info()
        if volume_info is not None:
            self._volume = volume_info.get('volume')
            self._min_volume = volume_info.get('minVolume')
            self._max_volume = volume_info.get('maxVolume')
            self._muted = volume_info.get('mute')

    def _refresh_channels(self):
        if not self._source_list:
            self._content_mapping = self._braviarc.load_source_list()
            self._source_list = []
            if not self._source_filter:  # list is empty
                for key in self._content_mapping:
                    self._source_list.append(key)
            else:
                filtered_dict = {title: uri for (title, uri) in
                                 self._content_mapping.items()
                                 if any(filter_title in title for filter_title
                                        in self._source_filter)}
                for key in filtered_dict:
                    self._source_list.append(key)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is not None:
            return self._volume / 100
        return None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        supported = SUPPORT_BRAVIA
        # Remove volume slider if amplifier is attached to TV
        if self._amp:
            supported = supported ^ SUPPORT_VOLUME_SET
        return supported

    @property
    def media_content_type(self):
        """Content type of current playing media.

        Used for program information below the channel in the state card.
        """
        return MEDIA_TYPE_TVSHOW

    @property
    def media_title(self):
        """Title of current playing media.

        Used to show TV channel info.
        """
        return_value = None
        if self._channel_name is not None:
            if self._channel_number is not None:
                return_value = '{0!s}: {1}'.format(
                    self._channel_number.lstrip('0'), self._channel_name)
            else:
                return_value = self._channel_name
        return return_value

    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only.

        Used to show TV program info.
        """
        return_value = None
        if self._program_name is not None:
            if self._start_time is not None and self._end_time is not None:
                return_value = '{0} [{1} - {2}]'.format(
                    self._program_name, self._start_time, self._end_time)
            else:
                return_value = self._program_name
        else:
            if not self._channel_name:  # This is empty when app is opened
                return_value = 'App opened'
        return return_value

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self._channel_name

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._braviarc.set_volume_level(volume)

    def turn_on(self):
        """Turn the media player on.

        Use a different command for Android as WOL is not working.
        """
        if self._android:
            self._braviarc.turn_on_command()
        else:
            self._braviarc.turn_on(self._broadcast)

        # Show that TV is starting while it takes time
        # before program info is available
        self._reset_playing_info()
        self._state = STATE_ON
        self._program_name = TV_WAIT

    def turn_off(self):
        """Turn off media player."""
        self._braviarc.turn_off()
        self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self._braviarc.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._braviarc.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self._braviarc.mute_volume()

    def select_source(self, source):
        """Set the input source."""
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self._braviarc.play_content(uri)

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._braviarc.media_play()

    def media_pause(self):
        """Send media pause command to media player.

        Will pause TV when TV tuner is on.
        """
        self._playing = False
        if self._program_media_type == 'tv' or self._program_name is not None:
            self._braviarc.media_tvpause()
        else:
            self._braviarc.media_pause()

    def media_next_track(self):
        """Send next track command.

        Will switch to next channel when TV tuner is on.
        """
        if self._program_media_type == 'tv' or self._program_name is not None:
            self._braviarc.send_command('ChannelUp')
        else:
            self._braviarc.media_next_track()

    def media_previous_track(self):
        """Send the previous track command.

        Will switch to previous channel when TV tuner is on.
        """
        if self._program_media_type == 'tv' or self._program_name is not None:
            self._braviarc.send_command('ChannelDown')
        else:
            self._braviarc.media_previous_track()

    def play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

        if media_id in PLAY_MEDIA_OPTIONS:
            self._braviarc.send_command(media_id)
        else:
            _LOGGER.warning("Unsupported media_id: %s", media_id)
