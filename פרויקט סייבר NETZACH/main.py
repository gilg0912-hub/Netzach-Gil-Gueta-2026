import queue

from network_infra import Message_Manager

from network import Server_Communicator


from user_state import User_State
from gui_state_mgmt import GUI_State
from dispatcher import MsgDispatcher

from services import AuthService, ChatService

from main_gui import Chat_GUI
from app_constants import Contract

class App_Context:
    def __init__(self):
        self.user_state = User_State()
        self.gui_state = GUI_State()
        self.msg_manager = Message_Manager()
        self.dispatcher = MsgDispatcher(self.gui_state, self.msg_manager)
        self.services = {
            'auth': AuthService(self.dispatcher,self.gui_state, self.user_state),
            'chat': ChatService(self.dispatcher, self.gui_state)
        }

        self.chat_gui = Chat_GUI(self.user_state, self.gui_state, self.services)
        self.communicator = Server_Communicator("127.0.0.1", 8820, self.user_state, self.msg_manager)

    def run(self):
        self.communicator.start()
        self.listen_for_messages()
        self.chat_gui.run()

    def listen_for_messages(self):
        try:
            for _ in range (5):
                msg = self.msg_manager.incoming_queue.get_nowait()


                msg_type = msg.get(Contract.TYPE)
                if msg_type:
                    self.dispatcher._dispatch(msg_type, msg)

        except queue.Empty:
            pass
        finally:
            self.chat_gui.after(100, self.listen_for_messages)


# MAIN WINDOW
app = App_Context()
app.run()
