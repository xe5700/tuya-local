from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch, PropertyMock
from uuid import uuid4

from custom_components.tuya_local.generic.climate import TuyaLocalClimate
from custom_components.tuya_local.generic.fan import TuyaLocalFan
from custom_components.tuya_local.generic.humidifier import TuyaLocalHumidifier
from custom_components.tuya_local.generic.light import TuyaLocalLight
from custom_components.tuya_local.generic.lock import TuyaLocalLock
from custom_components.tuya_local.generic.switch import TuyaLocalSwitch

from custom_components.tuya_local.helpers.device_config import (
    TuyaDeviceConfig,
    possible_matches,
)

DEVICE_TYPES = {
    "climate": TuyaLocalClimate,
    "fan": TuyaLocalFan,
    "humidifier": TuyaLocalHumidifier,
    "light": TuyaLocalLight,
    "lock": TuyaLocalLock,
    "switch": TuyaLocalSwitch,
}


class TuyaDeviceTestCase(IsolatedAsyncioTestCase):
    __test__ = False

    def setUpForConfig(self, config_file, payload):
        """Perform setup tasks for every test."""
        device_patcher = patch("custom_components.tuya_local.device.TuyaLocalDevice")
        self.addCleanup(device_patcher.stop)
        self.mock_device = device_patcher.start()
        self.dps = payload.copy()
        self.mock_device.get_property.side_effect = lambda id: self.dps[id]
        cfg = TuyaDeviceConfig(config_file)
        self.conf_type = cfg.legacy_type
        type(self.mock_device).unique_id = PropertyMock(return_value=str(uuid4()))
        self.mock_device.name = cfg.name

        self.entities = {}
        self.entities[cfg.primary_entity.config_id] = self.create_entity(
            cfg.primary_entity
        )

        self.names = {}
        self.names[cfg.primary_entity.config_id] = cfg.primary_entity.name(cfg.name)
        for e in cfg.secondary_entities():
            self.entities[e.config_id] = self.create_entity(e)
            self.names[e.config_id] = e.name(cfg.name)

    def create_entity(self, config):
        """Create an entity to match the config"""
        dev_type = DEVICE_TYPES[config.entity]
        if dev_type:
            return dev_type(self.mock_device, config)

    def test_config_matched(self):
        for cfg in possible_matches(self.dps):
            if cfg.legacy_type == self.conf_type:
                self.assertEqual(cfg.match_quality(self.dps), 100.0)
                return
        self.fail()

    def test_should_poll(self):
        for e in self.entities.values():
            self.assertTrue(e.should_poll)

    def test_name_returns_device_name(self):
        for e in self.entities:
            self.assertEqual(self.entities[e].name, self.names[e])

    def test_unique_id_contains_device_unique_id(self):
        entities = {}
        for e in self.entities.values():
            self.assertIn(self.mock_device.unique_id, e.unique_id)
            if type(e) not in entities:
                entities[type(e)] = []

            entities[type(e)].append(e.unique_id)

        for e in entities.values():
            self.assertCountEqual(e, set(e))

    def test_device_info_returns_device_info_from_device(self):
        for e in self.entities.values():
            self.assertEqual(e.device_info, self.mock_device.device_info)

    async def test_update(self):
        for e in self.entities.values():
            result = AsyncMock()
            self.mock_device.async_refresh.return_value = result()
            self.mock_device.async_refresh.reset_mock()
            await e.async_update()
            self.mock_device.async_refresh.assert_called_once()
            result.assert_awaited()
