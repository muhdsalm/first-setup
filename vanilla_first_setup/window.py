# window.py
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

from gettext import gettext as _
from gi.repository import Gtk, GObject, Adw

import contextlib

from vanilla_first_setup.utils.builder import Builder
from vanilla_first_setup.utils.parser import Parser
from vanilla_first_setup.utils.processor import Processor
from vanilla_first_setup.utils.tests import Tests

from vanilla_first_setup.views.progress import VanillaProgress
from vanilla_first_setup.views.done import VanillaDone
from vanilla_first_setup.views.post_script import VanillaPostScript


@Gtk.Template(resource_path="/org/vanillaos/FirstSetup/gtk/window.ui")
class VanillaWindow(Adw.ApplicationWindow):
    __gtype_name__ = "VanillaWindow"
    __gsignals__ = {
        "page-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    carousel = Gtk.Template.Child()
    carousel_indicator_dots = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    toasts = Gtk.Template.Child()

    def __init__(self, post_script: str, user: str, new_user: bool = False, **kwargs):
        super().__init__(**kwargs)

        # prepare a variable for the initialization mode:
        # 0 = normal
        # 1 = post script
        self.__init_mode = 0

        # some modes handle the result on their own, so we set
        # a new variable where to store the result:
        # None = no managed result
        # True/False = managed result
        self.__last_result = None

        # Create and run the tests to make sure the previous run installed
        # all the packages properly
        if self.__init_mode == 1:
            self.__tests = Tests()
            self.__tests.load()
            self.__tests_succeeded = self.__tests.test()
        else:
            # Set them to false anyway if it's the first boot
            self.__tests_succeeded = False

        # if a post_script is provided, we are in the post setup
        # so we can skip the builder and just run the post script
        # in the Vte terminal
        if post_script and self.__tests_succeeded:
            # set the initialization mode to 1
            self.__init_mode = 1

            # delete the tests file
            self.__tests.remove()

            # system views
            self.__view_done = VanillaDone(
                self,
                reboot=False,
                title=_("Done!"),
                description=_("Your device is ready to use."),
                fail_title=_("Error!"),
                fail_description=_("Something went wrong."),
            )

            # this builds the UI for the post script only
            self.__build_post_script_ui(post_script)

            # connect system signals
            self.__connect_signals()

            return

        # this starts the builder and generates the widgets
        # to put in the carousel
        self.__builder = Builder(self, new_user=new_user)
        self.recipe = self.__builder.recipe

        # system views
        self.__view_progress = VanillaProgress(self, self.recipe.get("tour", {}))
        self.__view_done = VanillaDone(self)

        # this builds the UI with the widgets generated by the builder
        self.__build_ui()

        # connect system signals
        self.__connect_signals()

    def __build_post_script_ui(self, post_script):
        self.__view_post_script = VanillaPostScript(self, post_script)

        self.carousel.append(self.__view_post_script)
        self.carousel.append(self.__view_done)

    @property
    def builder(self):
        return self.__builder

    def __connect_signals(self):
        self.btn_back.connect("clicked", self.back)
        self.carousel.connect("page-changed", self.__on_page_changed)

    def __build_ui(self, mode=0, rebuild=False):
        if rebuild:
            self.carousel.remove(self.__view_progress)
            self.carousel.remove(self.__view_done)

        for widget, status, protected in self.__builder.widgets:
            if rebuild:
                if protected:
                    continue
                self.carousel.remove(widget)

            if mode == 0 and not status:
                continue

            self.carousel.append(widget)

        self.carousel.append(self.__view_progress)
        self.carousel.append(self.__view_done)

    def rebuild_ui(self, mode=0):
        self.__build_ui(mode, rebuild=True)

    def __on_page_changed(self, *args):
        pages_check = [self.__view_done]
        if self.__init_mode == 0:
            pages_check.append(self.__view_progress)

        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index)
        with contextlib.suppress(AttributeError):
            self.emit("page-changed", page.step_id)

        if page not in pages_check:
            self.btn_back.set_visible(cur_index not in [0.0, 2.0])
            self.carousel_indicator_dots.set_visible(cur_index != 0.0)
            self.headerbar.set_show_end_title_buttons(cur_index != 0.0)
            return

        self.btn_back.set_visible(False)
        self.carousel_indicator_dots.set_visible(False)
        self.headerbar.set_show_end_title_buttons(False)

        # if there is a managed result, we can skip the processing
        # and manage it directly instead
        if self.__last_result is not None:
            self.__view_done.set_result(self.__last_result)
            self.__last_result = None
            return

        # keep the btn_back button locked if this is the last page
        if page == self.__view_done:
            return

        # collect all the finals
        finals = self.__builder.get_finals()

        # this parses the finals to compatible commands, by replacing the
        # placeholders with the actual values and generating shell commands
        commands = Parser.parse(finals)

        # process the commands
        res = Processor.get_setup_commands(
            self.recipe.get("log_file", "/tmp/vanilla_first_setup.log"),
            self.recipe.get("pre_run", []),
            self.recipe.get("post_run"),
            commands
        )

        self.__view_progress.start(res, Processor.hide_first_setup, self.__user)

    def set_installation_result(self, result, terminal):
        self.__view_done.set_result(result, terminal)
        self.next()

    def next(
        self,
        widget: Gtk.Widget = None,
        result: bool = None,
        rebuild: bool = False,
        mode: int = 0,
        *args
    ):
        if rebuild:
            self.rebuild_ui(mode)

        if result is not None:
            self.__last_result = result

        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index + 1)
        self.carousel.scroll_to(page, True)

    def back(self, *args):
        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index - 1)
        self.carousel.scroll_to(page, True)

    def toast(self, message, timeout=3):
        toast = Adw.Toast.new(message)
        toast.props.timeout = timeout
        self.toasts.add_toast(toast)

    def set_user(self, user):
        self.__user = user
