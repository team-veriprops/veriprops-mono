import json

from main.appodus_utils import Utils
from main.appodus_utils.config.settings import AppodusBaseSettings

appodus_base_settings = AppodusBaseSettings()
appodus_base_settings.set_env_vars() # Set the env vars in os.environ

appodus_settings = Utils.get_from_env_fail_if_not_exists('APPODUS_SETTINGS')
appodus_settings_dict = json.loads(appodus_settings)

appodus_base_settings.copy(update=appodus_settings_dict)

utils_settings = appodus_base_settings
