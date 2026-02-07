from dataclasses import dataclass, field
from aqt import mw
from aqt.utils import showWarning

@dataclass
class LoudnormConfig:
    """Configuration for the loudnorm filter"""
    enabled: bool = False
    i: int = -24
    dual_mono: bool = False


@dataclass
class VolumeConfig:
    """Main volume configuration"""
    volume: int = 100
    is_muted: bool = False
    allow_volume_boost: bool = False
    mute_shortcut: str = ""
    settings_shortcut: str = ""
    volume_up_shortcut: str = ""
    volume_down_shortcut: str = ""
    loudnorm: LoudnormConfig = field(default_factory=LoudnormConfig)
    playback_speed: float = 1.0
    speed_up_shortcut: str = ""
    speed_down_shortcut: str = ""


def load_config() -> VolumeConfig:
    """Load the sound volume configuration from Anki's configuration system"""
    volume_config = VolumeConfig()
    
    try:
        # Get addon config from Anki
        addon_config = mw.addonManager.getConfig(__name__)
        
        if not isinstance(addon_config, dict):
            showWarning("Invalid configuration format. Resetting to defaults.")
            return volume_config
        
        # If config exists, load it
        if addon_config:
            # Load configuration with type checking
            volume_config.volume = int(addon_config.get('volume', 100))
            volume_config.is_muted = bool(addon_config.get('is_muted', False))
            volume_config.allow_volume_boost = bool(addon_config.get('allow_volume_boost', False))
            volume_config.playback_speed = float(addon_config.get('playback_speed', 1.0))
            
            # Load shortcuts
            for shortcut_name in ['mute_shortcut', 'settings_shortcut', 
                                'volume_up_shortcut', 'volume_down_shortcut',
                                'speed_up_shortcut', 'speed_down_shortcut']:
                value = addon_config.get(shortcut_name, "")
                setattr(volume_config, shortcut_name, str(value) if value else "")

            # Load loudnorm settings
            loudnorm = addon_config.get('loudnorm', {})
            if isinstance(loudnorm, dict):
                volume_config.loudnorm.enabled = bool(loudnorm.get('enabled', False))
                volume_config.loudnorm.i = int(loudnorm.get('i', -24))
                volume_config.loudnorm.dual_mono = bool(loudnorm.get('dual_mono', False))
                
    except Exception as e:
        showWarning(f"Error loading configuration: {str(e)}\nResetting to defaults.")
        
    return volume_config


def save_config(volume_config: VolumeConfig) -> None:
    """Save configuration using Anki's configuration system"""
    if not isinstance(volume_config, VolumeConfig):
        showWarning("Invalid configuration object")
        return

    config = {
        'volume': volume_config.volume,
        'is_muted': volume_config.is_muted,
        'allow_volume_boost': volume_config.allow_volume_boost,
        'mute_shortcut': volume_config.mute_shortcut,
        'settings_shortcut': volume_config.settings_shortcut,
        'volume_up_shortcut': volume_config.volume_up_shortcut,
        'volume_down_shortcut': volume_config.volume_down_shortcut,
        'speed_up_shortcut': volume_config.speed_up_shortcut,
        'speed_down_shortcut': volume_config.speed_down_shortcut,
        'playback_speed': volume_config.playback_speed,
        'loudnorm': {
            'enabled': volume_config.loudnorm.enabled,
            'i': volume_config.loudnorm.i,
            'dual_mono': volume_config.loudnorm.dual_mono
        }
    }
    
    try:
        mw.addonManager.writeConfig(__name__, config)
    except Exception as e:
        showWarning(f"Failed to save volume settings: {str(e)}")