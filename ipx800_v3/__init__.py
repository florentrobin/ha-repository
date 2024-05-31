"""The IPX800 V3 integration."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.http import HomeAssistantView

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

QUEUE = None


PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPX800 V3 from a config entry."""

    global QUEUE
    hass.data[DOMAIN] = {}
    session = async_get_clientsession(hass)
    hass.data[DOMAIN]["session"] = session
    QUEUE = asyncio.Queue()

    # Register a new route for the webhook
    hass.http.register_view(IPX800View)

    # Start the queue processor
    hass.loop.create_task(process_queue(session))

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def process_queue(session):
    while True:
        url = await QUEUE.get()
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to send command to IPX800: %s", response.status
                    )
        except Exception as e:
            _LOGGER.error("Error sending command to IPX800: %s", e)
        await asyncio.sleep(0.2)  # 200ms delay


class IPX800View(HomeAssistantView):
    """Handle incoming webhook requests."""

    url = "/api/ipx800_update"
    name = "api:ipx800_update"
    requires_auth = False

    async def get(self, request):
        """Handle GET request."""
        hass = request.app["hass"]
        state = request.query.get("state")
        index = request.query.get("index")
        if state is not None and index is not None:
            hass.bus.async_fire(f"ipx800_update_{index}", {"state": state})
            return web.Response(status=200)
        return web.Response(status=400)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.pop(DOMAIN)
        return True
