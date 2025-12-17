"""Config flow for SDM630 integration."""

import logging
import serial.tools.list_ports
from typing import Any

import voluptuous as vol
from pymodbus.client import ModbusSerialClient

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BAUDRATE,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_SLAVE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SDM630ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SDM630."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        # Auto-discover serial ports for dropdown
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        port_options = {port.device: f"{port.device} ({port.description})" for port in ports}

        if user_input is not None:
            # Validate connection
            try:
                await self._async_test_connection(user_input)
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            except Exception as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Connection test failed: %s", err)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="SDM630 Meter"): str,
                vol.Required(CONF_SERIAL_PORT): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(port_options.keys()), mode=selector.SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In([2400, 4800, 9600, 19200, 38400]),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _async_test_connection(self, data: dict[str, Any]) -> None:
        """Test Modbus connection."""
        client = ModbusSerialClient(
            port=data[CONF_SERIAL_PORT],
            baudrate=data[CONF_BAUDRATE],
            parity="N",
            stopbits=1,
            bytesize=8,
            timeout=3,
        )
        try:
            if not await self.hass.async_add_executor_job(client.connect):
                raise ConnectionError("Failed to connect")
            # Test read (e.g., voltage L1 at address 0)
            rr = client.read_holding_registers(0, 1, slave=data[CONF_SLAVE_ID])
            if rr.isError():
                raise ValueError("Read error")
        finally:
            client.close()
