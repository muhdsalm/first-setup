# processor.py
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

import os
import shutil
import logging
import tempfile
import subprocess


logger = logging.getLogger("FirstSetup::Processor")


class Processor:

    @staticmethod
    def run(log_path, pre_run, post_run, commands):
        commands = pre_run + commands + post_run
        out_run = ""
        next_boot = []
        next_boot_script_path = os.path.expanduser("~/.local/org.vanillaos.FirstSetup.nextBoot")
        next_boot_autostart_path = os.path.expanduser("~/.config/autostart/org.vanillaos.FirstSetup.nextBoot.desktop")
        abroot_bin = shutil.which("abroot")

        logger.info("processing the following commands: \n%s" %
                    '\n'.join(commands))

        # connection check
        cn = subprocess.run(["wget", "-q", "--spider", "cloudflare.com"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        if cn.returncode != 0:
            logger.critical("No internet connection")
            return False, "No internet connection.", True

        # nextBoot commands are collected in ~/.local/org.vanillaos.FirstSetup.nextBoot
        # and executed at the next boot by a desktop entry
        for command in commands:
            if command.startswith("!nextBoot"):
                next_boot.append(command.replace("!nextBoot", ""))
                continue

        if len(next_boot) > 0:
            with open(next_boot_script_path, "w") as f:
                f.write("#!/bin/sh\n")
                f.write("# This file was created by FirstSetup\n")
                f.write("# Do not edit this file manually\n\n")

                for command in next_boot:
                    f.write(f"{command}\n")

                f.write(f"rm -f {next_boot_script_path}\n")
                f.write(f"rm -f {next_boot_autostart_path}\n")
                f.flush()
                f.close()

            # setting the file executable
            os.chmod(next_boot_script_path, 0o755)

            # creating the desktop entry
            with open(next_boot_autostart_path, "w") as f:
                f.write("[Desktop Entry]\n")
                f.write("Name=FirstSetup Next Boot\n")
                f.write("Comment=Run FirstSetup commands at the next boot\n")
                f.write("Exec=vanilla-first-setup --run-post-script 'sh %s'\n" % next_boot_script_path)
                f.write("Terminal=false\n")
                f.write("Type=Application\n")
                f.write("X-GNOME-Autostart-enabled=true\n")
                f.flush()
                f.close()

        # generating a temporary file to store all the commands so we can
        # run them all at once
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("#!/bin/sh\n")
            f.write("# This file was created by FirstSetup\n")
            f.write("# Do not edit this file manually\n\n")

            for command in commands:
                if command.startswith("!nextBoot"):
                    continue

                if command.startswith("!noSudo"):
                    command = command.replace("!noSudo", "sudo -u $USER")

                # outRun band is used to run a command outside of the main
                # shell script.
                if command.startswith("!outRun"):
                    out_run += command.replace("!outRun", "") + "\n"

                f.write(f"{command}\n")

            f.flush()
            f.close()

            # setting the file executable
            os.chmod(f.name, 0o755)

            # fake the process if VANILLA_FAKE is set
            if "VANILLA_FAKE" in os.environ:
                logger.info("VANILLA_FAKE is set, skipping the commands")
                return True, ""

            cmd = ["pkexec", "sh", f.name]
            if abroot_bin := shutil.which("abroot"):
                cmd = ["pkexec", abroot_bin, "exec", "-f", "sh", f.name]

            #proc = subprocess.run(cmd)
            # the above is wrong, we need to show the output in the console but also capture it
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.communicate()[0].decode("utf-8")

            # write the output to the log file so the packager can see what
            # happened during the installation process
            try:
                with open(log_path, 'a') as log:
                    log.write(out)
                    log.flush()
            except Exception as e:
                logger.warning("failed to write to the log file: %s" % e)
                logger.warning("the output of the commands is: %s" %
                                 out)

            if proc.returncode != 0:
                logger.critical(
                    "Error while processing commands, see log for details.")
                return False, out

        autostart_file = os.path.expanduser(
            "~/.config/autostart/org.vanillaos.FirstSetup.desktop")

        # run the outRun commands
        if out_run:
            logger.info("running outRun commands: \n%s" % out_run)
            subprocess.run(out_run, shell=True)

        return True, ""

    @staticmethod
    def hide_first_setup():
        desktop_file = os.path.expanduser(
            "~/.local/share/applications/org.vanillaos.FirstSetup.desktop")
        autostart_file = os.path.expanduser(
            "~/.config/autostart/org.vanillaos.FirstSetup.desktop")

        if os.path.exists(autostart_file):
            os.remove(autostart_file)

        with open(desktop_file, "w") as f:
            f.write("[Desktop Entry]\n")
            f.write("Name=FirstSetup\n")
            f.write("Comment=FirstSetup\n")
            f.write("Exec=vanilla-first-setup\n")
            f.write("Terminal=false\n")
            f.write("Type=Application\n")
            f.write("NoDisplay=true\n")
            f.flush()
            f.close()
