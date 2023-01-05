# window.py
#
# Copyright 2022 mirkobrombin
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

import time
from gi.repository import Gtk, Adw

from vanilla_first_setup.utils.builder import Builder
from vanilla_first_setup.utils.parser import Parser
from vanilla_first_setup.utils.processor import Processor
from vanilla_first_setup.utils.run_async import RunAsync

from vanilla_first_setup.views.progress import VanillaProgress
from vanilla_first_setup.views.done import VanillaDone
from vanilla_first_setup.views.post_script import VanillaPostScript


@Gtk.Template(resource_path='/io/github/vanilla-os/FirstSetup/gtk/window.ui')
class VanillaWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'VanillaWindow'

    carousel = Gtk.Template.Child()
    carousel_indicator_dots = Gtk.Template.Child()
    headerbar = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    toasts = Gtk.Template.Child()

    def __init__(self, post_script: str, **kwargs):
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

        # if a post_script is provided, we are in the post setup
        # so we can skip the builder and just run the post script
        # in the Vte terminal
        if post_script:
            # set the initialization mode to 1
            self.__init_mode = 1

            # system views
            self.__view_done = VanillaDone(self, reboot=False,
                title=_("Done!"), description=_("Your device is ready to use."),
                fail_title=_("Error!"), fail_description=_("Something went wrong."))

            # this builds the UI for the post script only
            self.__build_post_script_ui(post_script)

            # connect system signals
            self.__connect_signals()

            return

        # this starts the builder and generates the widgets
        # to put in the carousel
        self.__builder = Builder(self)
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

    def __build_ui(self):
        for widget in self.__builder.widgets:
            self.carousel.append(widget)

        self.carousel.append(self.__view_progress)
        self.carousel.append(self.__view_done)

    def __on_page_changed(self, *args):
        def process():
            # this parses the finals to compatible commands, by replacing the
            # placeholders with the actual values and generating shell commands
            commands = Parser.parse(finals)

            # process the commands
            return Processor.run(
                self.recipe.get("log_file", "/tmp/vanilla_first_setup.log"), 
                self.recipe.get("pre_run", []),
                self.recipe.get("post_run"),
                commands
            )

        def on_done(result, *args):
            if self.__init_mode == 0:
                self.__view_done.set_result(result)
            self.next()

        pages_check = [self.__view_done]
        if self.__init_mode == 0:
            pages_check.append(self.__view_progress)

        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index)
        if page not in pages_check:
            self.btn_back.set_visible(cur_index != 0.0)
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

        # run the process in a thread
        RunAsync(process, on_done)

    def next(self, widget: Gtk.Widget=None, result: bool=None, *args):
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
