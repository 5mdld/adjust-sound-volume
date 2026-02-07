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
Defines the sound configuration UI.
Original by Muneyuki Noguchi
Modified by egg rolls
"""

from typing import Tuple
import os
import json

from aqt import gui_hooks
from aqt import mw
from aqt.qt import (
    QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QSizePolicy, QSlider,
    QSpinBox, QVBoxLayout, QWidget, Qt, QShortcut, QKeySequence,
    QKeySequenceEdit, QAction, QPushButton, QMainWindow, QDoubleSpinBox
)
from aqt.sound import MpvManager
from aqt.sound import av_player
from aqt.utils import tooltip

from . import config
from . import hook

def save_config(volume_config: config.VolumeConfig) -> None:
    """Save the sound volume configuration."""
    # Save to config.json
    config.save_config(volume_config)

    gui_hooks.av_player_did_begin_playing.remove(hook.did_begin_playing)
    gui_hooks.av_player_did_begin_playing.append(hook.did_begin_playing)
    
    # Reset shortcuts
    setup_shortcuts()


def _create_config_widgets(text: str, min_max: Tuple[int, int]) \
        -> Tuple[QLabel, QSlider, QSpinBox]:
    label = QLabel()
    label.setText(text)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    slider = QSlider()
    slider.setOrientation(Qt.Orientation.Horizontal)
    slider.setMinimum(min_max[0])
    slider.setMaximum(min_max[1])
    slider.setSingleStep(1)  # Arrow key / small drag step
    slider.setPageStep(1)    # Page up/down step (also affects click precision)
    slider.setTracking(True) # Update while dragging
    slider.setMinimumWidth(200)  # Wider slider for more precise dragging

    spin_box = QSpinBox()
    spin_box.setMinimum(min_max[0])
    spin_box.setMaximum(min_max[1])
    spin_box.setSingleStep(1)

    slider.valueChanged.connect(spin_box.setValue)
    spin_box.valueChanged.connect(slider.setValue)

    return label, slider, spin_box


def _set_value(value: int, slider: QSlider, spin_box: QSpinBox) -> None:
    for widget in [slider, spin_box]:
        widget.setValue(value)


def adjust_volume(delta: int):
    """Adjust the volume level"""
    volume_config = config.load_config()
    max_volume = 200 if volume_config.allow_volume_boost else 100
    new_volume = max(0, min(max_volume, volume_config.volume + delta))
    
    # Add validation for delta to prevent invalid jumps
    if abs(delta) > max_volume:
        delta = max_volume if delta > 0 else -max_volume
    
    # Set to mute if volume is 0
    if new_volume == 0:
        volume_config.is_muted = True
    # Unmute if increasing volume from 0
    elif volume_config.volume == 0 and new_volume > 0:
        volume_config.is_muted = False
    # Unmute if increasing volume from muted state
    elif delta > 0 and volume_config.is_muted:
        volume_config.is_muted = False
    
    volume_config.volume = new_volume
    save_config(volume_config)
    
    # Show volume status
    status = "Muted" if volume_config.is_muted else f"Volume: {new_volume}%"
    tooltip(status)


def _get_nearest_speed(current_speed: float, increase: bool) -> float:
    """Get the nearest valid speed value from the predefined steps"""
    SPEED_STEPS = [0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]
    
    # Find the next or previous valid speed
    if increase:
        for speed in SPEED_STEPS:
            if speed > current_speed:
                return speed
        return SPEED_STEPS[-1]  # Return max speed if already at max
    else:
        for speed in reversed(SPEED_STEPS):
            if speed < current_speed:
                return speed
        return SPEED_STEPS[0]  # Return min speed if already at min

def adjust_speed(delta: float):
    """Adjust the playback speed using predefined steps"""
    volume_config = config.load_config()
    
    # Get next speed based on direction
    new_speed = _get_nearest_speed(volume_config.playback_speed, delta > 0)
    
    # Save and apply the new speed
    volume_config.playback_speed = new_speed
    save_config(volume_config)
    
    # Apply speed change to current player if any
    from aqt.sound import av_player
    for player in getattr(av_player, 'players', []):
        try:
            if isinstance(player, MpvManager):
                player.set_property('speed', new_speed)
        except:
            pass
    
    tooltip(f"Speed: {new_speed:.2f}x")


def _create_speed_widgets() -> Tuple[QLabel, QSlider, QDoubleSpinBox]:
    """Create speed control widgets with precise stepping"""
    label = QLabel("Speed")
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    slider = QSlider()
    slider.setOrientation(Qt.Orientation.Horizontal)
    slider.setMinimum(25)  # 0.25x
    slider.setMaximum(200)  # 2.00x
    
    spin_box = QDoubleSpinBox()
    spin_box.setRange(0.25, 2.0)
    spin_box.setSingleStep(0.05)
    spin_box.setDecimals(2)
    
    return label, slider, spin_box

def _round_to_nearest_step(value: float, step: float = 0.05) -> float:
    """Round a value to the nearest step"""
    return round(value / step) * step

class VolumeDialog(QDialog):
    """A dialog window to set the sound volume"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adjust Sound Volume Settings")
        # Add a variable to track the current dialog session state
        self._current_session_boost_enabled = False
        
        # Volume section
        volume_group = QGroupBox("Volume")
        volume_layout = QGridLayout()
        
        # Volume slider and spinbox
        volume_label, self.volume_slider, self.volume_spin_box = _create_config_widgets(
            'Volume', (0, 200))
        volume_layout.addWidget(volume_label, 0, 0)
        volume_layout.addWidget(self.volume_slider, 0, 1)
        volume_layout.addWidget(self.volume_spin_box, 0, 2)
        
        # Volume boost checkbox
        self.volume_boost_check_box = QCheckBox('Allow volume boost above 100%')
        self.volume_boost_check_box.stateChanged.connect(self.on_volume_boost_changed)
        volume_layout.addWidget(self.volume_boost_check_box, 1, 0, 1, 3)
        
        # Mute checkbox
        self.mute_check_box = QCheckBox("Mute")
        volume_layout.addWidget(self.mute_check_box, 2, 0, 1, 3)
        
        self.mute_check_box.stateChanged.connect(self.on_mute_changed_silent)
        self.mute_check_box.stateChanged.connect(self.update_volume_controls)
        
        volume_group.setLayout(volume_layout)

        # Loudness normalization settings
        self.loudnorm_group_box = QGroupBox("Loudness Normalization")
        self.loudnorm_group_box.setCheckable(True)
        self.loudnorm_group_box.toggled.connect(self._show_warning_on_non_mpv)
        
        # Create loudnorm layout
        loudnorm_layout = QGridLayout()
        
        # I value slider and spinbox
        i_label, self.i_slider, self.i_spin_box = _create_config_widgets(
            'Integrated loudness', (-50, -14))
        
        loudnorm_layout.addWidget(i_label, 0, 0)
        loudnorm_layout.addWidget(self.i_slider, 0, 1)
        loudnorm_layout.addWidget(self.i_spin_box, 0, 2)
        
        # Add info text
        i_info = QLabel("Safe range: -50 to -20 dB")
        i_info.setStyleSheet("color: gray; font-size: 11px;")
        loudnorm_layout.addWidget(i_info, 1, 0, 1, 3)
        
        # Add value change warning
        self._last_value = self.i_spin_box.value()  # Record previous value
        def on_loudness_change(value):
            if value > -20 and self._last_value <= -20:
                QMessageBox.warning(self, 'Warning',
                    'Setting integrated loudness above -20 dB may cause audio instability.\n'
                    'Recommended range is between -50 and -20 dB.')
            self._last_value = value
        
        self.i_spin_box.valueChanged.connect(on_loudness_change)
        
        # Add dual mono checkbox
        self.dual_mono_check_box = QCheckBox('Treat mono input as dual-mono')
        loudnorm_layout.addWidget(self.dual_mono_check_box, 2, 0, 1, 3)
        
        # Set layout for loudnorm group box
        self.loudnorm_group_box.setLayout(loudnorm_layout)
        
        # Shortcuts section
        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_layout = QGridLayout()
        
        # Add shortcut instruction label
        instruction_label = QLabel("Click to record shortcut, press ESC to clear")
        instruction_label.setStyleSheet("color: gray; font-size: 11px;")
        shortcuts_layout.addWidget(instruction_label, 0, 0, 1, 3)
        
        # Define shortcut items
        shortcut_items = [
            ("Volume Up:", "volume_up_shortcut_edit"),
            ("Volume Down:", "volume_down_shortcut_edit"),
            ("Toggle Mute:", "mute_shortcut_edit"),
            ("Settings:", "settings_shortcut_edit"),
            ("Speed Up:", "speed_up_shortcut_edit"),
            ("Speed Down:", "speed_down_shortcut_edit")
        ]
        
        # Add shortcut editors
        row = 1
        self.shortcut_editors = {}
        for label_text, attr_name in shortcut_items:
            label = QLabel(label_text)
            label.setMinimumWidth(100)
            editor = QKeySequenceEdit()
            
            # Connect validation and install event filter
            editor.keySequenceChanged.connect(self.validate_shortcut)
            editor.installEventFilter(self)
            
            setattr(self, attr_name, editor)
            self.shortcut_editors[attr_name] = editor
            
            shortcuts_layout.addWidget(label, row, 0)
            shortcuts_layout.addWidget(editor, row, 1)
            row += 1
        
        # Reset shortcuts button
        reset_shortcuts_button = QPushButton("Reset Shortcuts to Default")
        reset_shortcuts_button.clicked.connect(self._reset_shortcuts)
        shortcuts_layout.addWidget(reset_shortcuts_button, len(shortcut_items) + 1, 0, 1, 3)
        
        shortcuts_group.setLayout(shortcuts_layout)
        
        # Speed section
        speed_group = QGroupBox("Playback Speed")
        speed_layout = QGridLayout()
        
        # Create speed controls
        speed_label, self.speed_slider, self.speed_spin_box = _create_speed_widgets()
        speed_layout.addWidget(speed_label, 0, 0)
        speed_layout.addWidget(self.speed_slider, 0, 1)
        speed_layout.addWidget(self.speed_spin_box, 0, 2)
        
        # Connect speed controls
        self.speed_slider.valueChanged.connect(self._on_speed_slider_changed)
        self.speed_spin_box.valueChanged.connect(self._on_speed_spin_changed)
        
        speed_group.setLayout(speed_layout)
        
        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(volume_group)
        layout.addWidget(self.loudnorm_group_box)
        layout.addWidget(shortcuts_group)
        layout.addWidget(speed_group)
        layout.addStretch()
        
        # Reset all settings button
        reset_all_button = QPushButton("Reset All Settings to Default")
        reset_all_button.clicked.connect(self._reset_all_settings)
        layout.addWidget(reset_all_button)
        
        # Create dialog buttons
        button_box = QDialogButtonBox()
        button_box.addButton(QDialogButtonBox.StandardButton.Ok)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Add button box to main layout
        layout.addWidget(button_box)
        
        self.setLayout(layout)

    def _reset_all_settings(self):
        """Reset all settings to default values"""
        if QMessageBox.question(
            self,
            "Reset All Settings",
            "Are you sure you want to reset all settings to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            # Load default settings from config.json
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(addon_dir, "config.json")
            with open(config_path, 'r') as f:
                default_config = json.load(f)
            
            # Update UI elements
            self.volume_slider.setValue(default_config["volume"])
            self.volume_spin_box.setValue(default_config["volume"])
            self.volume_boost_check_box.setChecked(default_config["allow_volume_boost"])
            self.mute_check_box.setChecked(default_config["is_muted"])
            
            # Update speed controls
            speed_value = int(default_config["playback_speed"] * 100)
            self.speed_slider.setValue(speed_value)
            self.speed_spin_box.setValue(default_config["playback_speed"])
            
            # Update loudnorm settings
            self.loudnorm_group_box.setChecked(default_config["loudnorm"]["enabled"])
            self.i_slider.setValue(default_config["loudnorm"]["i"])
            self.i_spin_box.setValue(default_config["loudnorm"]["i"])
            self.dual_mono_check_box.setChecked(default_config["loudnorm"]["dual_mono"])
            
            # Update shortcuts
            self.mute_shortcut_edit.setKeySequence(QKeySequence(default_config["mute_shortcut"]))
            self.settings_shortcut_edit.setKeySequence(QKeySequence(default_config["settings_shortcut"]))
            self.volume_up_shortcut_edit.setKeySequence(QKeySequence(default_config["volume_up_shortcut"]))
            self.volume_down_shortcut_edit.setKeySequence(QKeySequence(default_config["volume_down_shortcut"]))
            self.speed_up_shortcut_edit.setKeySequence(QKeySequence(default_config["speed_up_shortcut"]))
            self.speed_down_shortcut_edit.setKeySequence(QKeySequence(default_config["speed_down_shortcut"]))
            
            tooltip("All settings have been reset to default values")

    def _show_warning_on_non_mpv(self, checked: bool) -> None:
        if not checked:
            return

        if any(isinstance(player, MpvManager) for player in av_player.players):
            return

        QMessageBox.warning(self, 'mpv not found or too old',
                            'You need to install or update mpv and restart Anki '
                            'to use the loudness normalization feature.')

    def _reset_shortcuts(self):
        """Reset shortcuts to default values"""
        if QMessageBox.question(
            self,
            "Reset Shortcuts",
            "Are you sure you want to reset all shortcuts to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
            
        default_shortcuts = {
            'volume_up': "Ctrl+Alt+Up",
            'volume_down': "Ctrl+Alt+Down",
            'mute': "Ctrl+Alt+M",
            'settings': "Ctrl+Alt+V",
            'speed_up': "Ctrl+Alt+Right",
            'speed_down': "Ctrl+Alt+Left"
        }
        
        for name, shortcut in default_shortcuts.items():
            if hasattr(self, f"{name}_shortcut_edit"):
                editor = getattr(self, f"{name}_shortcut_edit")
                editor.setKeySequence(QKeySequence(shortcut))
        
        tooltip("Shortcuts reset to default values")

    def on_mute_changed_silent(self, state):
        """Handle mute state change without showing tooltip"""
        volume_config = config.load_config()
        volume_config.is_muted = bool(state)
        save_config(volume_config)
    
    def show(self) -> None:
        """Show the dialog window and its widgets."""
        volume_config = config.load_config()
        
        # Update the session state when dialog opens
        self._current_session_boost_enabled = volume_config.allow_volume_boost
        
        # Set volume boost checkbox state first
        self.volume_boost_check_box.setChecked(volume_config.allow_volume_boost)
        
        # Set maximum based on whether volume boost is allowed
        max_volume = 200 if volume_config.allow_volume_boost else 100
        self.volume_slider.setMaximum(max_volume)
        self.volume_spin_box.setMaximum(max_volume)
        
        # Now set the volume value after setting the maximum
        _set_value(volume_config.volume,
                   self.volume_slider, self.volume_spin_box)

        # Set mute state and update control states
        self.mute_check_box.setChecked(volume_config.is_muted)
        self.update_volume_controls(volume_config.is_muted)

        loudnorm = volume_config.loudnorm
        self.loudnorm_group_box.setChecked(loudnorm.enabled)
        _set_value(loudnorm.i, self.i_slider, self.i_spin_box)
        self.dual_mono_check_box.setChecked(loudnorm.dual_mono)
        
        # Set shortcuts, only set when there are values in the configuration
        if volume_config.volume_up_shortcut and volume_config.volume_up_shortcut.strip():
            self.volume_up_shortcut_edit.setKeySequence(QKeySequence(volume_config.volume_up_shortcut))
        else:
            self.volume_up_shortcut_edit.clear()
        
        if volume_config.volume_down_shortcut and volume_config.volume_down_shortcut.strip():
            self.volume_down_shortcut_edit.setKeySequence(QKeySequence(volume_config.volume_down_shortcut))
        else:
            self.volume_down_shortcut_edit.clear()

        if volume_config.mute_shortcut and volume_config.mute_shortcut.strip():
            self.mute_shortcut_edit.setKeySequence(QKeySequence(volume_config.mute_shortcut))
        else:
            self.mute_shortcut_edit.clear()
        
        if volume_config.settings_shortcut and volume_config.settings_shortcut.strip():
            self.settings_shortcut_edit.setKeySequence(QKeySequence(volume_config.settings_shortcut))
        else:
            self.settings_shortcut_edit.clear()

        # Set speed controls
        speed = volume_config.playback_speed
        self.speed_slider.setValue(int(speed * 100))
        self.speed_spin_box.setValue(speed)
        
        # Set speed shortcuts
        if volume_config.speed_up_shortcut and volume_config.speed_up_shortcut.strip():
            self.speed_up_shortcut_edit.setKeySequence(QKeySequence(volume_config.speed_up_shortcut))
        else:
            self.speed_up_shortcut_edit.clear()
            
        if volume_config.speed_down_shortcut and volume_config.speed_down_shortcut.strip():
            self.speed_down_shortcut_edit.setKeySequence(QKeySequence(volume_config.speed_down_shortcut))
        else:
            self.speed_down_shortcut_edit.clear()

        super().show()

    def accept(self) -> None:
        """Validate and save all settings"""
        # Check all shortcuts for validity
        for editor in self.shortcut_editors.values():
            sequence = editor.keySequence()
            if not sequence.isEmpty():
                key_combination = sequence[0]
                modifiers = key_combination.keyboardModifiers()
                has_modifier = bool(modifiers & (
                    Qt.KeyboardModifier.ControlModifier | 
                    Qt.KeyboardModifier.AltModifier | 
                    Qt.KeyboardModifier.ShiftModifier | 
                    Qt.KeyboardModifier.MetaModifier
                ))
                if not has_modifier:
                    tooltip("Invalid shortcut settings. Please ensure all shortcuts include modifier keys")
                    return
        
        # Check for duplicate shortcuts
        used_shortcuts = {}
        for name, editor in self.shortcut_editors.items():
            sequence = editor.keySequence()
            if not sequence.isEmpty():
                key_string = sequence.toString()
                if key_string in used_shortcuts:
                    tooltip(f"Shortcut '{key_string}' is used multiple times")
                    return
                used_shortcuts[key_string] = name

        # If validation passes, save settings
        volume_config = config.load_config()
        
        # Save volume settings
        volume_config.volume = self.volume_slider.value()
        volume_config.is_muted = self.mute_check_box.isChecked()
        volume_config.allow_volume_boost = self.volume_boost_check_box.isChecked()
        
        # Save playback speed (convert from percentage to float)
        volume_config.playback_speed = self.speed_slider.value() / 100.0
        
        # Save shortcut settings
        volume_config.volume_up_shortcut = self.volume_up_shortcut_edit.keySequence().toString() or ""
        volume_config.volume_down_shortcut = self.volume_down_shortcut_edit.keySequence().toString() or ""
        volume_config.mute_shortcut = self.mute_shortcut_edit.keySequence().toString() or ""
        volume_config.settings_shortcut = self.settings_shortcut_edit.keySequence().toString() or ""
        volume_config.speed_up_shortcut = self.speed_up_shortcut_edit.keySequence().toString() or ""
        volume_config.speed_down_shortcut = self.speed_down_shortcut_edit.keySequence().toString() or ""
        
        # Save audio normalization settings
        volume_config.loudnorm.enabled = self.loudnorm_group_box.isChecked()
        volume_config.loudnorm.i = self.i_spin_box.value()
        volume_config.loudnorm.dual_mono = self.dual_mono_check_box.isChecked()
        
        # Save configuration and update shortcuts
        save_config(volume_config)
        setup_shortcuts()
        
        # Process events to ensure immediate shortcut update
        from aqt.qt import QApplication
        QApplication.instance().processEvents()
        
        super().accept()

    def eventFilter(self, obj, event) -> bool:
        """Handle ESC key press to clear shortcut immediately"""
        if (isinstance(obj, QKeySequenceEdit) and 
            event.type() == event.Type.KeyPress and 
            event.key() == Qt.Key.Key_Escape):
            obj.clear()
            return True
        return super().eventFilter(obj, event)

    def update_volume_controls(self, state):
        """Update volume control enabled states based on mute status and volume level"""
        is_muted = bool(state)
        volume = self.volume_slider.value()
        
        # Volume controls should always be enabled except when manually muted
        self.volume_slider.setEnabled(not is_muted or volume == 0)
        self.volume_spin_box.setEnabled(not is_muted or volume == 0)
        
        # Handle mute checkbox state
        if volume == 0:
            self.mute_check_box.setEnabled(False)
            self.mute_check_box.setChecked(True)
        else:
            self.mute_check_box.setEnabled(True)

    def on_volume_changed(self, value):
        """Handle volume change events"""
        if value > 0:
            # Enable mute checkbox and uncheck it
            self.mute_check_box.setEnabled(True)
            self.mute_check_box.setChecked(False)
            # Enable volume controls
            self.volume_slider.setEnabled(True)
            self.volume_spin_box.setEnabled(True)
        else:
            # Disable and check mute checkbox
            self.mute_check_box.setEnabled(False)
            self.mute_check_box.setChecked(True)
            # Keep volume controls enabled at 0
            self.volume_slider.setEnabled(True)
            self.volume_spin_box.setEnabled(True)

    def on_mute_changed(self, state):
        """Handle mute state changes"""
        is_muted = bool(state)
        volume = self.volume_slider.value()
        
        # Only disable volume controls when manually muted and volume > 0
        if volume > 0:
            self.volume_slider.setEnabled(not is_muted)
            self.volume_spin_box.setEnabled(not is_muted)

    def on_volume_boost_changed(self, state):
        """Handle volume boost checkbox state change"""
        allow_boost = bool(state)
        current_volume = self.volume_slider.value()
        
        # Show warning when enabling boost and it wasn't enabled in current session
        if allow_boost and not self._current_session_boost_enabled:
            QMessageBox.warning(
                self,
                "Volume Boost Warning",
                "Warning: Setting volume above 100% may cause audio distortion and could "
                "potentially damage your speakers or headphones. Please use this feature carefully."
            )
        
        # Update current session state
        self._current_session_boost_enabled = allow_boost
        
        # Update volume slider and spinbox range
        max_volume = 200 if allow_boost else 100
        self.volume_slider.setMaximum(max_volume)
        self.volume_spin_box.setMaximum(max_volume)
        
        # If boost is disabled and current volume > 100%, limit it to 100%
        if not allow_boost and current_volume > 100:
            self.volume_slider.setValue(100)
            self.volume_spin_box.setValue(100)

    def validate_shortcut(self):
        """Handle shortcut validation"""
        editor = self.sender()
        if not isinstance(editor, QKeySequenceEdit):
            return
            
        sequence = editor.keySequence()
        if sequence.isEmpty():
            return
        
        # Get the first key combination
        key_combination = sequence[0]
        
        # Check for modifier keys
        modifiers = key_combination.keyboardModifiers()
        has_modifier = bool(modifiers & (
            Qt.KeyboardModifier.ControlModifier | 
            Qt.KeyboardModifier.AltModifier | 
            Qt.KeyboardModifier.ShiftModifier | 
            Qt.KeyboardModifier.MetaModifier
        ))
        
        if not has_modifier:
            editor.clear()
            tooltip("Shortcut must include at least one modifier key (Ctrl, Alt, Shift)")
            return
        
        # Check for duplicate shortcuts
        key_string = sequence.toString()
        current_shortcuts = {}
        for name, other_editor in self.shortcut_editors.items():
            if other_editor == editor:
                continue
            seq = other_editor.keySequence()
            if not seq.isEmpty():
                current_shortcuts[seq.toString()] = name
        
        if key_string in current_shortcuts:
            editor.clear()
            tooltip(f"Shortcut '{key_string}' is already used")
            return

    def _on_speed_slider_changed(self, value: int):
        """Handle slider value changes"""
        speed = value / 100
        rounded_speed = _round_to_nearest_step(speed)
        if self.speed_spin_box.value() != rounded_speed:
            self.speed_spin_box.setValue(rounded_speed)
            
    def _on_speed_spin_changed(self, value: float):
        """Handle spin box value changes"""
        rounded_speed = _round_to_nearest_step(value)
        if value != rounded_speed:
            self.speed_spin_box.setValue(rounded_speed)
        
        slider_value = int(rounded_speed * 100)
        if self.speed_slider.value() != slider_value:
            self.speed_slider.setValue(slider_value)
            
        # Update playback speed
        mw.pm.profile['playback_speed'] = rounded_speed
        if hasattr(mw, '_player'):
            mw._player.set_speed(rounded_speed)


def toggle_mute():
    """Toggle mute state only if volume is not 0"""
    volume_config = config.load_config()
    
    # Only toggle mute if volume is greater than 0
    if volume_config.volume > 0:
        volume_config.is_muted = not volume_config.is_muted
        save_config(volume_config)
        tooltip("Sound " + ("Muted" if volume_config.is_muted else "Unmuted"))
    else:
        tooltip("Cannot toggle mute when volume is 0")

def setup_shortcuts():
    """Setup global shortcuts for volume control"""
    volume_config = config.load_config()
    
    # Initialize shortcuts list if not exists
    if not hasattr(mw, '_volume_shortcuts'):
        mw._volume_shortcuts = []
    
    def register_shortcut(key, fn):
        if not key or key.isspace():  # Skip if shortcut is empty or whitespace
            return None
        action = QAction(mw)
        action.setShortcut(QKeySequence(key))
        # Use ApplicationShortcut to work across all Anki windows
        action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        action.triggered.connect(fn)
        # Add action to the main window to ensure it's always available
        mw.addAction(action)
        return action
    
    # Register new shortcuts
    shortcuts = [
        (volume_config.volume_up_shortcut, lambda: adjust_volume(10)),
        (volume_config.volume_down_shortcut, lambda: adjust_volume(-10)),
        (volume_config.mute_shortcut, toggle_mute),
        (volume_config.settings_shortcut, lambda: VolumeDialog(mw).show()),
        (volume_config.speed_up_shortcut, lambda: adjust_speed(0.1)),
        (volume_config.speed_down_shortcut, lambda: adjust_speed(-0.1))
    ]
    
    # Clear existing shortcuts
    if hasattr(mw, '_volume_shortcuts'):
        for action in mw._volume_shortcuts:
            action.setShortcut(QKeySequence(""))
            action.setEnabled(False)
            mw.removeAction(action)
            action.deleteLater()
        mw._volume_shortcuts = []
    
    # Register new shortcuts
    mw._volume_shortcuts = []  # Reset the list
    for shortcut, callback in shortcuts:
        if action := register_shortcut(shortcut, callback):
            mw._volume_shortcuts.append(action)
            # Ensure the action stays active
            action.setEnabled(True)
