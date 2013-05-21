__author__ = "David Rusk <drusk@uvic.ca>"

import json
import os

DEFAULT_CONFIG_FILE = "config.json"


class AppConfig(object):
    """
    Provides programmatic access to contents of the application
    configuration file.
    """

    def __init__(self, configfile=None):
        if configfile is None:
            configfile = self._get_default_config_file_path()

        with open(configfile, "rb") as filehandle:
            self._data = json.loads(filehandle.read())

    def _get_default_config_file_path(self):
        return os.path.join(os.path.dirname(__file__), DEFAULT_CONFIG_FILE)

    def read(self, keypath):
        """
        Reads a value from the configuration file.

        Args:
          keypath: str
            Specifies the key for which the value is desired.  It can be a
            hierarchical path.  Example: "section1.subsection.key1"

        Returns:
          value from configuration file
        """
        curr_data = self._data
        for key in keypath.split("."):
            curr_data = curr_data[key]
        return curr_data
