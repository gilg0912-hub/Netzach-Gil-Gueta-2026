from app_constants import StateKey
import threading

class User_State:
    def __init__(self):
        # נתונים
        self._data = {
            StateKey.CONNECTED: False,
            StateKey.IS_ACTIVE: True,
            StateKey.USERNAME: "",
            StateKey.IDENTITY: None,
            StateKey.TOKEN: None,
            StateKey.AUTHENTICATED: False,
        }

        self._locks = {key: threading.Lock() for key in self._data}

        # מאזינים גנריים



    def set_state(self, key, value):
        if key in self._data:

            with self._locks[key]:
                if self._data[key]!=value:
                    self._data[key] = value


    def get_state(self, key):
        if key in self._data:
            with self._locks[key]:
                return self._data.get(key)