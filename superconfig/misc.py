import getpass

from superconfig import config
from superconfig import smarts

class UsernameGetter(smarts.Getter):
    @staticmethod
    def read(key, rest, context, lower_layer):
        return config.Response.found(getpass.getuser())