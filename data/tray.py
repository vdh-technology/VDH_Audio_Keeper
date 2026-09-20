"""System tray icon management for VDH_Audio_Keeper."""
import os
from pathlib import Path
import wx
import wx.adv
from .gui import SettingsDialog
from .config import SettingsStore


def create_default_icon() -> wx.Icon:
    """Create a high-resolution programmatic icon if icon file is missing."""
    bmp = wx.Bitmap(32, 32)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(wx.Colour(30, 144, 255)))  # Dodger Blue
    dc.Clear()
    
    # Draw speaker wave icon symbol
    dc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 2))
    dc.SetBrush(wx.Brush(wx.Colour(255, 255, 255)))
    
    # Speaker body
    dc.DrawRectangle(6, 12, 6, 8)
    polygon_pts = [wx.Point(12, 12), wx.Point(18, 7), wx.Point(18, 25), wx.Point(12, 20)]
    dc.DrawPolygon(polygon_pts)
    
    # Sound waves
    dc.SetBrush(wx.NullBrush)
    dc.DrawArc(wx.Point(21, 10), wx.Point(21, 22), wx.Point(21, 16))
    dc.DrawArc(wx.Point(24, 7), wx.Point(24, 25), wx.Point(24, 16))
    
    dc.SelectObject(wx.NullBitmap)
    
    icon = wx.Icon()
    icon.CopyFromBitmap(bmp)
    return icon


class TrayIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame, store: SettingsStore, engine):
        super().__init__()
        self.frame = frame
        self.store = store
        self.engine = engine

        self.SetAppIcon()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.OnLeftClick)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.OnLeftClick)

    def SetAppIcon(self):
        icon_path = Path(__file__).resolve().parent.parent / "icon.ico"
        if icon_path.exists():
            icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO)
        else:
            icon = create_default_icon()
        self.SetIcon(icon, "VDH_Audio_Keeper")

    def CreatePopupMenu(self):
        menu = wx.Menu()
        
        item_settings = menu.Append(wx.ID_ANY, "&Settings...")
        menu.AppendSeparator()
        item_exit = menu.Append(wx.ID_ANY, "&Exit")

        self.Bind(wx.EVT_MENU, self.OnOpenSettings, item_settings)
        self.Bind(wx.EVT_MENU, self.OnExitApp, item_exit)

        return menu

    def OnLeftClick(self, event):
        self.OpenSettingsDialog()

    def OnOpenSettings(self, event):
        self.OpenSettingsDialog()

    def OpenSettingsDialog(self):
        # Trigger background audio device scan so dialog opens with fresh devices
        if self.engine:
            self.engine.request_scan()

        dlg = SettingsDialog(None, self.store, self.engine)
        dlg.ShowModal()
        dlg.Destroy()

    def OnExitApp(self, event):
        self.RemoveIcon()
        self.Destroy()
        if self.frame:
            self.frame.Close(True)
