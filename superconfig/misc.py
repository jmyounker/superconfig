import getpass
import pathlib

from superconfig import config
from superconfig import gtrs


class UsernameGetter(gtrs.Getter):
    @staticmethod
    def read(key, rest, context, lower_layer):
        return config.Response.found(getpass.getuser())


class HomeDirGetter(gtrs.Getter):
    @staticmethod
    def read(key, rest, context, lower_layer):
        return config.Response.found(pathlib.Path.home())
