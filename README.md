# Demented IGPU

My solution for getting Nvidia GTX 10xx laptop GPUs working on
GNU/Linux, with a GRUB boot menu choice between integrated (iGPU) and
Nvidia graphics. If you have Ubuntu 18.04 you can download and run the
`DementedIGPU` Python 3 script to implement the GRUB menu (it's the
only distro I tested on). If you have some other `systemd` based
distribution, you may be able to run the script as-is or with some
tweaking. The script tries to be smart and not just blindly overwrite
you system files. And of course, you can just follow the steps below
manually instead of using the automatic script.

I also have a guide (written for a beginner audience) at the bottom
about installing Ubuntu 18.04 on an XPS 15 9560.

# Overview

(To be clear, you don't have to read all this if you just want to run
the script instead of configuring the menu manually).

My plan is to use Nvidia proprietary drivers in Nvidia mode and use
bumblebee and `bbswitch` for iGPU mode (along with the
`acpi_rev_override=1` kernel option). `optirun` doesn`t seem to work
so well these days, but `bbswitch` seems to do a better job shutting
off the Nvidia GPU than `prime-select intel`, so that's what I'm
using. As long as we use `bumblebee` only when we want to keep the GPU
off (instead of using it for switching), we should be okay. I do this
by adding 2 GRUB menu entries: one that instructs `systemd` to load
`bbswitch` (iGPU mode) and one that excludes `bbswitch` (Nvidia mode).

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
uses a Rube Goldberg solution involving switching between `nvidia` and
`nouveau` drivers and reinstalling GRUB each time a switch is done. So
make sure it's in `nvidia` mode and not interfering with what we're
trying to do!

# Step 2: bbswitch

(Corresponds to the other part of the
`configure_dependencies` script).

Now we need to install `bumblebee` (which should install
`bbswitch`). Once this is done, since we plan to enable `bumblebee`
only when we want iGPU graphics, we need to disable `bumblebee` by
default like so:

```
systemctl disable bumblebeed.service
```

(Note the `d` at the end of `bumblebeed`).

# Step 3: Creating a systemd target

(Corresponds to the `create_igpu_target_file` script).

This is certainly an oversimplification, but when your `systemd`-based
system boots, `systemd` looks for a `target` file to know what
services to initialize. We want to make a new `target` file that's
like your default `target` file but additionally initializes the
`bumblebee` service. Then, we'll target this file when we want iGPU
graphics.

Usually `graphical.target` is the default target. For some stupid
reason it seems that this file can be at any odd place depending on
your distro. Once you find it (possibly with a command like `find /lib
-name graphical.target` -- also try `/bin` and `/etc` I'm told), make
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
files.  We need to add a menu entry with the arguments

```
systemd.unit=DementedIGPU.target acpi_rev_override=1
```

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
create your own `40_custom` file. The reason I chose this `10_linux`
hacky solution is that it guarantees that the iGPU entry will be
updated as well along with the default entry if the GRUB configuration
is changed elsewhere.

Once the file's patched, obviously you need to run `update-grub` and
restart the computer. In my test installs I sometimes had to reboot 2
or 3 times before the system was stable. I'm not sure why this is but
after those restarts the computer was completely stable (I'm eating my
own dog food here; my main Ubuntu 18.04 work computer was the final
test case for the `DementedIGPU` script).

# Step 0: Ubuntu 18.04 on the XPS 15 9560



# Sources