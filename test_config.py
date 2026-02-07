# Anki 2.1.x add-on to adjust the sound volume
# Copyright (C) 2021  Muneyuki Noguchi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
Test the behavior in loading configurations
"""
import sys
import unittest
from typing import Dict, Union, Any
from unittest.mock import MagicMock, patch

# Mock aqt modules before importing config
# This allows tests to run without Anki/PyQt installed
mock_aqt = MagicMock()
mock_aqt.mw = MagicMock()
mock_aqt.utils = MagicMock()

# Configure specific mocks needed by config.py
mock_aqt.utils.showWarning = MagicMock()

# Setup sys.modules to intercept imports
sys.modules['aqt'] = mock_aqt
sys.modules['aqt.utils'] = mock_aqt.utils

# Now we can safely import config
from config import load_config, VolumeConfig, LoudnormConfig


class TestConfig(unittest.TestCase):
    """A class to test the loading of configurations"""

    def setUp(self) -> None:
        # Reset the mock for each test
        mock_aqt.mw.reset_mock()
        self.mock_mw = mock_aqt.mw

    def _get_config(self, config_data: Union[Dict, None]) -> VolumeConfig:
        # Configure the return value of getConfig
        self.mock_mw.addonManager.getConfig.return_value = config_data
        return load_config()

    def test_default(self) -> None:
        """Validate the default value."""
        actual = self._get_config({})
        expected = VolumeConfig(
            volume=100,
            is_muted=False,
            allow_volume_boost=False,
            mute_shortcut='',
            settings_shortcut='',
            volume_up_shortcut='',
            volume_down_shortcut='',
            speed_up_shortcut='',
            speed_down_shortcut='',
            playback_speed=1.0,
            loudnorm=LoudnormConfig(
                enabled=False,
                i=-24,
                dual_mono=False
            )
        )
        self.assertEqual(actual, expected)

    def test_full_valid_config(self) -> None:
        """Test with all values validly set."""
        config_data = {
            'volume': 50,
            'is_muted': True,
            'allow_volume_boost': True,
            'mute_shortcut': 'M',
            'settings_shortcut': 'S',
            'volume_up_shortcut': 'U',
            'volume_down_shortcut': 'D',
            'speed_up_shortcut': 'R',
            'speed_down_shortcut': 'L',
            'playback_speed': 1.5,
            'loudnorm': {
                'enabled': True,
                'i': -10,
                'dual_mono': True
            }
        }
        actual = self._get_config(config_data)
        expected = VolumeConfig(
            volume=50,
            is_muted=True,
            allow_volume_boost=True,
            mute_shortcut='M',
            settings_shortcut='S',
            volume_up_shortcut='U',
            volume_down_shortcut='D',
            speed_up_shortcut='R',
            speed_down_shortcut='L',
            playback_speed=1.5,
            loudnorm=LoudnormConfig(
                enabled=True,
                i=-10,
                dual_mono=True
            )
        )
        self.assertEqual(actual, expected)

    def test_valid_volume(self) -> None:
        """Test with a valid volume value."""
        actual = self._get_config({
            'volume': 70
        })
        self.assertEqual(actual.volume, 70)

    def test_invalid_volume(self) -> None:
        """Test with an invalid volume value."""
        actual = self._get_config({
            'volume': 'a'
        })
        # Expect default config because exception is caught and defaults returned
        expected = VolumeConfig()
        self.assertEqual(actual, expected)

    def test_playback_speed(self) -> None:
        """Test valid playback speed."""
        actual = self._get_config({
            'playback_speed': 2.0
        })
        self.assertEqual(actual.playback_speed, 2.0)

    def test_invalid_playback_speed(self) -> None:
        """Test invalid playback speed."""
        actual = self._get_config({
            'playback_speed': 'fast'
        })
        # Expect default config due to exception handling
        expected = VolumeConfig()
        self.assertEqual(actual, expected)

    def test_shortcuts(self) -> None:
        """Test shortcut configurations."""
        actual = self._get_config({
            'mute_shortcut': 'Ctrl+M',
            'volume_up_shortcut': 'Ctrl+Up'
        })
        self.assertEqual(actual.mute_shortcut, 'Ctrl+M')
        self.assertEqual(actual.volume_up_shortcut, 'Ctrl+Up')
        # Check others are default empty
        self.assertEqual(actual.settings_shortcut, '')

    def test_empty_shortcuts(self) -> None:
        """Test empty string shortcuts."""
        actual = self._get_config({
            'mute_shortcut': ''
        })
        self.assertEqual(actual.mute_shortcut, '')

    def test_loudnorm_partial(self) -> None:
        """Test partial loudnorm configuration."""
        actual = self._get_config({
            'loudnorm': {
                'enabled': True
            }
        })
        # Should have enabled=True, others default
        self.assertTrue(actual.loudnorm.enabled)
        self.assertEqual(actual.loudnorm.i, -24)
        self.assertFalse(actual.loudnorm.dual_mono)

    def test_loudnorm_invalid_type(self) -> None:
        """Test loudnorm with invalid type."""
        actual = self._get_config({
            'loudnorm': "not a dict"
        })
        # Config code: if isinstance(loudnorm, dict): ...
        expected = VolumeConfig()
        self.assertEqual(actual, expected)

    def test_invalid_config_format(self) -> None:
        """Test with non-dict config."""
        actual = self._get_config("not a dict")
        expected = VolumeConfig()
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
