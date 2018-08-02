# Copyright 2018 David Zhao Akeley (akeley98)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# Note: It's GPL v3 because the GRUB config file I patch has a GPL v3
# header, so perhaps this script is a "derived work". Off-the-record,
# I don't really care if you use this script in a non-GPL way (but the
# risk is yours).

"""Library for the demented igpu tool. Other files implement the front-end."""
import time
import sys
import os
from subprocess import Popen, PIPE
from hashlib import sha256
import re

def remark(text):
    """Print remark with blue prefix."""
    sys.stderr.write("\x1b[36mDementedIGPU: \x1b[0m")
    sys.stderr.write(text)
    sys.stderr.write("\n")
    sys.stderr.flush()

def warning(text):
    """Print warning with purple prefix."""
    sys.stderr.write("\x1b[35m\x1b[1mDementedIGPU Warning: \x1b[0m")
    sys.stderr.write(text)
    sys.stderr.write("\n")
    sys.stderr.flush()

def error(text="(see above for possible reason)"):
    """Print error message with red prefix, then exit."""
    sys.stderr.write("\x1b[31m\x1b[1mDementedIGPU Error: \x1b[0m")
    sys.stderr.write(text)
    sys.stderr.write("\n")
    sys.stderr.flush()
    sys.exit(1)

# Change working directory to wherever this library is, and check that
# we're root.  I'm the only user of this library, so I don't worry
# about making global state changes like this. (Also I just call error
# instead of throwing an exception for the same reason; better error
# formatting and no one's trying to recover from errors here).
if os.geteuid() != 0: error("Need to be root (run with sudo).")
working_dir = os.path.split(sys.argv[0])[0]
if working_dir:
    os.chdir(working_dir)
    remark(f"Changing to {working_dir} directory.")

def process(*args):
    """Run a command line process with given args, and return a tuple
of its stdout output and return code. Stderr goes to stderr."""

    p = Popen(args, stdout=PIPE)
    text = p.stdout.read()
    cs = 0
    while 1:
        cs += 1
        code = p.poll()
        if code is not None:
            return (text, code)
        time.sleep(0.01)
        if cs % 1000 == 999:
            remark(f"waited{cs}0ms args={args}")
    error("Subprocess timed out")

def process_strict(*args):
    """Run a command line process with the given args: if successful (code
0), return the stdout text emitted, otherwise, call error(). Stderr
goes to stderr.
    """
    text, code = process(*args)
    if code != 0: error(f"error code ({code}) running command f{args}")
    return text
    
def detect_nvidia():
    """Return True iff we think nvidia is installed."""

    # They warn that apt has no stable interface but we do it anyway.
    text = process_strict("apt", "list", "--installed")

    return re.search(b"nvidia-[0-9]", text) is not None

def install_nvidia():
    """Install nvidia drivers (and add apt repo).

We call os.system directly instead of Popen since we must not capture
stdout; apt may ask the user questions.
    """
    remark("Adding nvidia repository.")
    code = os.system("add-apt-repository ppa:graphics-drivers/ppa") >> 8
    if code != 0: error()

    code = os.system("apt-get update") >> 8
    if code != 0: error()

    remark("Installing nvidia-384.")
    code = os.system("apt-get install nvidia-384") >> 8
    if code != 0: error()


def prime_select_nvidia():
    """Do prime-select nvidia. prime-select must not be tampering with the GPU for my scheme to work."""
    text, code = process("which", "prime-select")
    if code == 1:
        remark("nvidia-prime not found (we don't need it anyway).")
        return

    text, code = process("sh", "-c", "prime-select nvidia")
    if code != 0:
        warning("prime-select nvidia maybe didn't work.")
        remark("If you never used prime-select this isn't a problem.")
    else:
        remark("Did prime-select nvidia so it's not messing with "
               "the driver.")
    
def find_graphical_target():
    """Return the filename of the graphical.target systemd file. It seems
that it could be at any random place depending on distro, and there
could be multiple. In that case, prefer /lib, then /run, then /etc."""

    remark("Looking for graphical.target file.")
    def find(prefix):
        # There's supposed to be some option for using nul instead of
        # newline for find (-print0?) but it doesn't seem to work.
        # So just assume no one put a newline in the file name
        # of some graphical.target file.
        text, code = process("find", prefix, "-name", "graphical.target")
        names = text.split(b'\n')
        if len(names) == 0 or len(names) == 1 and not names[0]:
            return None
        elif len(names) == 1 or len(names) == 2 and not names[1]:
            filename = str(names[0], 'utf-8')
            remark(f"Found {filename}.")
            return filename
        else:
            error(f"Multiple graphical.target files found in {prefix}")

    return find("/lib") or find("/run") or find("/etc") or \
        error("Couldn't find graphical.target file.")

def create_igpu_target():
    """Create DementedIGPU.target file based on graphical.target file with added bumblebee service in "Wants" list. Put the file where we found the graphical.target file."""

    graphical_filename = find_graphical_target()
    path = os.path.split(graphical_filename)[0]

    lines = open(graphical_filename, "r").read().split('\n')

    for i, line in enumerate(lines):
        if line.strip().startswith("Wants"):
            wants_idx, wants_line = i, line
            break
    else:
        error(f"Could not find 'Wants' listing in {graphical_filename} .")

    lines[wants_idx] = wants_line + " bumblebeed.service"
    text = '\n'.join(lines) + '\n'
    igpu_filename = os.path.join(path, "DementedIGPU.target")
    
    open(igpu_filename, "w").write(text)
    remark(f"Wrote {igpu_filename}.")


def maybe_patch_10_linux_file():
    """Patch the 10_linux grub.d file if we think we need to. This makes
it so that there's 2 menu entries in GRUB, one for nvidia and one for
iGPU graphics. Return True iff we did the patch."""

    filename = "/etc/grub.d/10_linux"
    before = "d2d52571736ed1dcd05069249154a09f2f0935be041e7cadd180dc94ad6e4db9"
    after = "2e29c9a1eeb7c470910f6db86f0a2200f997d261d5b21f719fbcfcda8c271406"

    do_patch = True
    
    # Look for demented_linux_entry function.
    text, code = process("grep", "demented_linux_entry", filename)
    if code == 0:
        remark(f"{filename} appears to be patched already.")
        do_patch = False
    elif code != 1:
        error("grep failed while checking 10_linux file.")

    # Patch it if it doesn't seem to be patched.
    if do_patch:
        # Check the before hash.
        contents = open(filename, "rb").read()
        if sha256(contents).hexdigest() != before:
            warning(f"{filename} hash is not as expected.")
            warning("Have you manually modified the file? The patch may fail.")
            warning("Pausing for 15 seconds in case you want to cancel (^C).")
            time.sleep(15)
            remark(f"Patching {filename} anyway.")
        else:
            remark(f"Patching {filename}.")
        
        process("patch", filename, "DementedIGPU.patch")

    # Check the after hash.
    contents = open(filename, "rb").read()
    if sha256(contents).hexdigest() != after:
        warning(f"{filename} hash is not as expected.")
    
    return do_patch