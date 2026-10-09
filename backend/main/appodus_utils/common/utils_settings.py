from main.appodus_utils.config.settings import AppodusBaseSettings

appodus_base_settings = AppodusBaseSettings()
appodus_base_settings.set_env_vars() # Set the per-field env vars in os.environ

# The full settings snapshot stays in-process (`settings.get_full_settings_json()`), never in
# os.environ, so the aggregated secret blob cannot leak through the environment.
utils_settings = appodus_base_settings
