import logging
import xml.etree.ElementTree as ET

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from . import QUEUE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the IPX800 light platform."""
    session = hass.data[DOMAIN]["session"]
    ip_address = config_entry.data[CONF_HOST]

    coordinator = IPX800Coordinator(hass, session, ip_address)
    await coordinator.async_refresh()

    entities = [IPX800Light(coordinator, i) for i in range(1, 9)]

    async_add_entities(entities)


class IPX800Coordinator:
    """Class to manage fetching IPX800 data."""

    def __init__(self, hass, session, ip_address):
        """Initialize."""
        self.hass = hass
        self._session = session
        self._ip_address = ip_address
        self.data = {}

    async def async_refresh(self):
        """Fetch data from IPX800."""
        try:
            async with self._session.get(
                f"http://{self._ip_address}/status.xml"
            ) as response:
                if response.status != 200:
                    _LOGGER.error(f"Error fetching data: {response.status}")
                xml_data = await response.text()
                self.parse_xml(xml_data)
        except Exception as e:
            _LOGGER.error(f"Error communicating with IPX800: {e}")

    def parse_xml(self, xml_data):
        """Parse the XML data."""
        root = ET.fromstring(xml_data)
        for i in range(1, 9):
            self.data[f"{i}"] = int(root.find(f"led{(i - 1)}").text)


class IPX800Light(LightEntity):
    """Representation of a IPX800 light."""

    def __init__(self, coordinator, index):
        """Initialize the light."""
        self.coordinator = coordinator
        self._index = index
        self._state: bool = None

        self.coordinator.hass.bus.async_listen(
            f"ipx800_update_{self._index}", self._handle_event
        )

    # To link this entity to the cover device, this property must return an
    # identifiers value matching that used in the cover, but no other information such
    # as name. If name is returned, this entity will then also become a device in the
    # HA UI.
    @property
    def device_info(self) -> DeviceInfo:
        """Return information to link this entity with the correct device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"light_{DOMAIN}_{self._index}")},
            name=f"IPX800 Light {self._index}",
            manufacturer="GCE Electronics",
            model="IPX800 V3",
        )

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return f"IPX800 Light {self._index}"

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        if self._state is None:
            return self.coordinator.data.get(f"{self._index}") == 1
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self._send_command(1)
        self._state = True

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._send_command(0)
        self._state = False

    async def _send_command(self, state):
        """Send the command to the IPX800."""
        url = (
            f"http://{self.coordinator._ip_address}/preset.htm?set{self._index}={state}"
        )
        await QUEUE.put(url)

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = [ColorMode.ONOFF]

    @callback
    def _handle_event(self, event):
        """Handle incoming events from IPX800."""
        new_state = int(event.data["state"])
        self.coordinator.data[f"{self._index}"] = new_state
        self.async_write_ha_state()
