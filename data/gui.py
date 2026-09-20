"""Settings Dialog GUI for VDH_Audio_Keeper using wxPython."""
import wx
from .config import SettingsStore, get_autostart_status


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, store: SettingsStore, engine):
        super().__init__(parent, title="Settings - VDH_Audio_Keeper", size=(440, 260),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.store = store
        self.engine = engine
        self.device_ids = []

        self.InitUI()
        self.LoadSettings()
        self.CenterOnParent()

    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        content_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1. Enable continuous audio checkbox
        self.chk_enable = wx.CheckBox(self, label="Enable continuous audio")
        self.chk_enable.SetToolTip("Keep continuous imperceptible silent audio running to prevent sound hardware delays.")
        content_sizer.Add(self.chk_enable, 0, wx.ALL | wx.EXPAND, 8)

        # 2. Audio output device selection
        lbl_device = wx.StaticText(self, label="Audio output device:")
        content_sizer.Add(lbl_device, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.choice_device = wx.Choice(self, choices=[])
        content_sizer.Add(self.choice_device, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        # 3. Start with Windows checkbox
        self.chk_autostart = wx.CheckBox(self, label="Start with Windows")
        self.chk_autostart.SetToolTip("Automatically run VDH_Audio_Keeper when Windows boots up.")
        content_sizer.Add(self.chk_autostart, 0, wx.ALL | wx.EXPAND, 8)

        main_sizer.Add(content_sizer, 1, wx.ALL | wx.EXPAND, 12)

        # Separator line
        line = wx.StaticLine(self, wx.ID_ANY)
        main_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        # 4. OK and Cancel buttons
        btn_sizer = wx.StdDialogButtonSizer()
        self.btn_ok = wx.Button(self, wx.ID_OK, "OK")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        
        self.btn_ok.SetDefault()
        btn_sizer.AddButton(self.btn_ok)
        btn_sizer.AddButton(self.btn_cancel)
        btn_sizer.Realize()

        main_sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizer(main_sizer)

        # Event Binds
        self.btn_ok.Bind(wx.EVT_BUTTON, self.OnOK)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

    def LoadSettings(self):
        data = self.store.data
        self.chk_enable.SetValue(bool(data.get("enabled", True)))
        self.chk_autostart.SetValue(get_autostart_status())

        # Populate audio output devices from WASAPI scan snapshot
        devices = []
        if self.engine:
            devices = self.engine.snapshot().get("devices", [])

        self.device_ids = [""] + [dev_id for dev_id, name in devices]
        labels = ["Default output device"] + [name for dev_id, name in devices]

        saved_device = data.get("device", "")
        if saved_device and saved_device not in self.device_ids:
            self.device_ids.append(saved_device)
            labels.append("Saved device (currently offline)")

        self.choice_device.Set(labels)

        selected_idx = 0
        if saved_device in self.device_ids:
            selected_idx = self.device_ids.index(saved_device)
        self.choice_device.SetSelection(selected_idx)

    def OnOK(self, event):
        selected_idx = self.choice_device.GetSelection()
        selected_device = self.device_ids[selected_idx] if 0 <= selected_idx < len(self.device_ids) else ""

        new_settings = {
            "enabled": self.chk_enable.GetValue(),
            "device": selected_device,
            "volume": self.store.data.get("volume", 5),
            "start_with_windows": self.chk_autostart.GetValue()
        }

        # Save settings (which also updates registry startup entry)
        self.store.save(new_settings)

        # Apply settings to running audio engine
        if self.engine:
            from .engine import Settings
            self.engine.update(Settings.from_config(self.store.data))

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
