# theme.py
#
# Copyright 2023 mirkobrombin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundationat version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gio, Adw


@Gtk.Template(resource_path="/org/vanillaos/FirstSetup/gtk/default-theme.ui")
class VanillaDefaultTheme(Adw.Bin):
    __gtype_name__ = "VanillaDefaultTheme"

    btn_next = Gtk.Template.Child()
    btn_default = Gtk.Template.Child()
    btn_dark = Gtk.Template.Child()

    def __init__(self, window, distro_info, key, step, **kwargs):
        super().__init__(**kwargs)
        self.__window = window
        self.__distro_info = distro_info
        self.__key = key
        self.__step = step
        self.__theme = "light"
        self.__style_manager = self.__window.style_manager

        self.btn_default.set_active(not self.__style_manager.get_dark())
        self.btn_dark.set_active(self.__style_manager.get_dark())

        self.btn_next.connect("clicked", self.__window.next)
        self.btn_default.connect("toggled", self.__set_theme, "light")
        self.btn_dark.connect("toggled", self.__set_theme, "dark")

    @property
    def step_id(self):
        return self.__key

    def __set_theme(self, widget, theme: str):
        pref = "prefer-dark" if theme == "dark" else "default"
        gtk = "Adwaita-dark" if theme == "dark" else "Adwaita"
        Gio.Settings.new("org.gnome.desktop.interface").set_string("color-scheme", pref)
        Gio.Settings.new("org.gnome.desktop.interface").set_string("gtk-theme", gtk)
        self.__theme = theme

    def get_finals(self):
        gs_cmd = "!nextBoot !noRoot gsettings set %s %s %s"
        cmds = []

        if self.__theme == "dark":
            cmds.append(
                gs_cmd % ("org.gnome.desktop.interface", "color-scheme", "prefer-dark")
            )
            cmds.append(
                gs_cmd % ("org.gnome.desktop.interface", "gtk-theme", "Adwaita-dark")
            )
        else:
            cmds.append(
                gs_cmd % ("org.gnome.desktop.interface", "color-scheme", "default")
            )
            cmds.append(
                gs_cmd % ("org.gnome.desktop.interface", "gtk-theme", "Adwaita")
            )

        return {
            "vars": {"setTheme": True},
            "funcs": [{"if": "setTheme", "type": "command", "commands": cmds}],
        }
