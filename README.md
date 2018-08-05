# Demented IGPU

My solution for getting Nvidia GTX 10xx laptop GPUs working on
GNU/Linux, with a GRUB boot menu choice between integrated (iGPU) and
Nvidia graphics. If you have Ubuntu 18.04 you can download and run the
`DementedIGPU` Python 3 script to implement the GRUB menu (it's the
only distro I tested on – my hardware was a Dell XPS 15 9560). If you
have some other `systemd` based distribution, you may be able to run
the script as-is or with some tweaking. The script tries to be smart
and not just blindly overwrite you system files. And of course, you
can just follow the steps below manually instead of using the
automatic script.

I also have a guide (written for a beginner audience) at the bottom
about installing Ubuntu 18.04 on an XPS 15 9560.

# The Short Version

Download or clone this repo, unzip if needed, open a terminal and
navigate to the `DementedIGPU` (or `DementedIGPU-master`) directory,
and run `sudo DementedIGPU`. There's also this `notify` script that
you can target with a keyboard shortcut in order to quickly find out
which GPU is running.

# Overview

(To be clear, you don't have to read all this if you just want to run
the script instead of configuring the menu manually).

My plan is to use Nvidia proprietary drivers in Nvidia mode and use
bumblebee and bbswitch for iGPU mode (along with the
`acpi_rev_override=1` kernel option). `optirun` doesn't seem to work
so well these days, but bbswitch seems to do a better job shutting
off the Nvidia GPU than `prime-select intel`, so that's what I'm
using. As long as we use bumblebee only when we want to keep the GPU
off (instead of using it for switching), we should be okay. I do this
by adding 2 GRUB menu entries: one that instructs systemd to load
bbswitch (iGPU mode) and one that excludes bbswitch (Nvidia mode).

I've tried to comment and log liberally so that when you look at a
line of code you can immediately get an idea of what the hell was
going through my head when I wrote it. If it doesn't work for your
laptop or distro, tweak it. Then fork the repo and publish your
changes for everyone else; this is free software!

# Step 1: Nvidia drivers

(Corresponds to part of the `configure_dependencies` script).

For me, I installed the `nvidia-384` driver. I haven't tested the
script with other versions. If you're running a
proprietary-software-friendly distro, this should be a fairly simple
task. On Ubuntu, it's

```
add-apt-repository ppa:graphics-drivers/ppa
apt-get update
apt-get install nvidia-384
```

If your distro takes a stricter stance on free software, then I salute
you, but you're on your own for this first step.

After this, if you have `prime-select` you need to make sure that you
set it to `nvidia` mode! As far as I can tell `prime-select intel`
uses a Rube Goldberg solution involving switching between nvidia and
nouveau drivers and reinstalling GRUB each time a switch is done. So
make sure it's in `nvidia` mode and not interfering with what we're
trying to do!

# Step 2: bbswitch

(Corresponds to the other part of the
`configure_dependencies` script).

Now we need to install bumblebee (which should install
bbswitch). Once this is done, since we plan to enable bumblebee
only when we want iGPU graphics, we need to disable bumblebee by
default like so:

```
systemctl disable bumblebeed.service
```

(Note the `d` at the end of `bumblebeed`).

# Step 3: Creating a systemd target

(Corresponds to the `create_igpu_target_file` script).

This is certainly an oversimplification, but when your systemd-based
system boots, systemd looks for a target file to know what
services to initialize. We want to make a new target file that's
like your default target file but additionally initializes the
bumblebee service. Then, we'll target this file when we want iGPU
graphics.

Usually `graphical.target` is the default target. For some stupid
reason it seems that this file can be at any odd place depending on
your distro. Once you find it (possibly with a command like `find /lib
-name graphical.target` – also try `/bin` and `/etc` I'm told), make
a copy of it in the same directory. Remember the name of the copy
(it's called `DementedIGPU.target`) in the script. Then, in the
`Wants:` line, add `bumblebeed.service`. It should look something like
this:

```
Wants=your-other-services-here.service bumblebeed.service
```

# Step 4: Modifying the GRUB menu

(Corresponds to the `patch_grub_config` script).

I'll just describe roughly what needs to be accomplished in this step
because the exact steps depend on the specifics of your GRUB config
files.  We need to add a menu entry with

```systemd.unit=```target file name from the last step

and

```acpi_rev_override=1```

passed as kernel parameters. GRUB runs the bash scripts in
`/etc/grub.d` to create its menus (the scripts writes the menus to
`stdout` and remarks to `stderr`). I noticed that the `linux_entry`
function in the `10_linux` file was responsible for writing a menu
entry for booting the current OS. The last (4th) parameter is the list
of arguments for the kernel. So I just added extra calls to
`linux_entry` with the above two arguments tacked on at the end.

The way the script does it is that it applies the `DementedIGPU.patch`
file to `/etc/grub.d/10_linux`, making a backup of `10_linux` (named
`.10_linux` in the DementedIGPU directory). So, in case the patch
messed up the config file, you can run `restore_10_linux_backup` to
fix it.

Instead of patching the `10_linux` file, you may find it cleaner to
create your own `40_custom` file. The reason I chose this hacky
`10_linux` solution is that it guarantees that the iGPU entry will be
updated as well along with the default entry if the GRUB configuration
is changed elsewhere.

Once the file's patched, obviously you need to run `update-grub` and
restart the computer. In my test installs I sometimes had to reboot 2
or 3 times before the system was stable. I'm not sure why this is but
after those restarts the computer was completely stable (I'm eating my
own dog food here; my main Ubuntu 18.04 work partition was the final
test case for the `DementedIGPU` script).

If it still doesn't work try editing the `/etc/default/grub` file and
removing all arguments from `GRUB_CMD_LINE_LINUX_DEFAULT` and
`GRUB_CMD_LINE_LINUX`:

```
GRUB_CMDLINE_LINUX_DEFAULT=""
GRUB_CMDLINE_LINUX=""
```

# Step 0: Ubuntu 18.04 on the XPS 15 9560

I decided to test out reinstalling Ubuntu 18.04 from scratch (on a
different partition) to see what the UX for this script is like for a
first-time user. Here's my notes from that experience. These notes
probably are also useful for other Nvidia laptops.

First, follow the "Prep work with Windows" step from
https://github.com/rcasero/doc/wiki/Ubuntu-linux-on-Dell-XPS-15-(9560)
and disable secure boot in the BIOS. (Just for the record, I disagree
with the author's assessment of Ubuntu 17.10; I thought it was a fine
distro). For other laptops you'll have to adapt for this step, but
after this things will probably be similar for all Nvidia GTX 10xx
laptops.

Boot the laptop using a Ubuntu 18.04 live usb (Google it for
instructions for creating one). Make sure all external monitors and
all other usb devices are removed for this step, including USB hubs –
that was the problem for me. Go into the boot menu (`F12` on the XPS)
and select the UEFI USB device boot option. Do NOT select legacy boot!
Once you get to the GRUB menu, use the arrow keys to highlight the
"Try Ubuntu Without Installing" option, and press `e` (not `Enter`).

You should be in an editor now. Use the arrow keys to go to the line
that starts with `linux` and find the `quiet splash` part. Backspace
that and replace it with `nomodeset vga=791`, then press `F10` to boot.

Hopefully the computer boots after this. Once you're in, install
Ubuntu as usual. Just make sure you connect to wi-fi at this point!
(Unless you have ethernet, that's even better).  If you want to
replicate what I did exactly, I chose minimal install, no to
proprietary software, and yes to updates.

Reboot to the new Ubuntu install. Once you get to the login page, do
NOT log in. It'll probably crash if you try to run a graphical system
right now. Instead, press `Ctrl-Alt-F3` to switch to a console and
log in with your username and password.

Now for the fun part, downloading and running my script. Hopefully
Ubuntu remembers the wi-fi from before. Type in

```
wget goo.gl/ZZxKxB
```

or

```
wget https://github.com/akeley98/DementedIGPU/archive/master.zip
```

to download my stuff, then run

```
unzip ZZxKxB
```

or


```
unzip master.zip
```

and finally

```
sudo DementedIGPU-master/DementedIGPU
```

to run my script. Say yes (`y`) whenever it asks. Hopefully this
works. File an issue if it doesn't.

Finally, run

```
sudo shutdown -r now
```

to restart, but before doing that, optionally run

```
sudo DementedIGPU-master/clear_default_grub
sudo update-grub
```

to clear your GRUB linux cmd settings.

In my experience, it took 2 or 3 reboots before the system becomes
stable; I don't know why. If it's still not stable, run the above
command from the `Ctrl-Alt-F3` console as before (or from recovery
mode).

# Sources

Various stuff I consulted through my Nvidia graphics ordeal.

https://wiki.archlinux.org/index.php/Dell_XPS_15_9560#Power_Saving

https://bbs.archlinux.org/viewtopic.php?id=211027

https://wiki.archlinux.org/index.php/systemd#Create_custom_target

https://ubuntuforums.org/showthread.php?t=2354834#5

https://unix.stackexchange.com/questions/304085/trying-to-understand-what-a-systemd-target-wants


