"""Main entry point for VDH_Audio_Keeper application."""
import sys
import wx
from data.config import SettingsStore, get_log_dir
from data.engine import Engine, Settings, make_logger
from data.tray import TrayIcon


class MainFrame(wx.Frame):
    def __init__(self, store: SettingsStore, engine: Engine):
        super().__init__(None, title="VDH_Audio_Keeper", size=(1, 1),
                         style=wx.FRAME_NO_TASKBAR | wx.NO_BORDER)
        self.store = store
        self.engine = engine
        self.tray = TrayIcon(self, self.store, self.engine)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, event):
        if self.tray:
            self.tray.RemoveIcon()
            self.tray.Destroy()
            self.tray = None
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.Destroy()


def main():
    app = wx.App(False)
    app.SetAppName("VDH_Audio_Keeper")

    # Ensure single instance running
    checker = wx.SingleInstanceChecker("VDH_Audio_Keeper_SingleInstance_Mutex")
    if checker.IsAnotherRunning():
        wx.MessageBox("VDH_Audio_Keeper is already running in the system tray.",
                      "VDH_Audio_Keeper", wx.OK | wx.ICON_INFORMATION)
        return 0

    log_dir = get_log_dir()
    logger = make_logger(log_dir)

    store = SettingsStore()
    engine = Engine(logger)
    engine.update(Settings.from_config(store.data))

    frame = MainFrame(store, engine)
    # Frame is kept hidden so application runs entirely in system tray
    frame.Hide()

    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
