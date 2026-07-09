import json

from main.appodus_utils.config.settings import AppodusBaseSettings, get_full_settings_json

appodus_base_settings = AppodusBaseSettings()
appodus_base_settings.set_env_vars() # Set the per-field env vars in os.environ

# Full settings snapshot is held in-process (not in os.environ) to avoid leaking the
# aggregated secret blob via the environment. See settings.get_full_settings_json().
appodus_settings = get_full_settings_json()
appodus_settings_dict = json.loads(appodus_settings) if appodus_settings else {}

appodus_base_settings.copy(update=appodus_settings_dict)

utils_settings = appodus_base_settings
