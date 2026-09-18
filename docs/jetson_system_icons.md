# Jetson System Icon Troubleshooting

[English](jetson_system_icons.md) | [中文](jetson_system_icons_zh.md) | [Documentation index](README.md)

Applies to Jetson, Ubuntu 22.04, ARM64, and the GNOME desktop. Recorded on 2026-09-18.
This guide covers missing Wi-Fi and file-manager button icons, not damaged photos,
camera frames, or robot control faults. It is a repair guide, not a mandatory setup step.

## 1. Incident and Conclusions

System icons turned into red crosses after environment installation.

| Observation | Interpretation |
| --- | --- |
| Icon theme was `Yaru` | The theme name was normal; this did not verify the files or decoder |
| Root disk was 93% full, with about 17 GB available | Not full when checked; earlier resource problems cannot be ruled out |
| `.bashrc` globally added an Anaconda library path under another user's home | A library conflict risk, but removing it alone did not visibly restore icons |
| SVG thumbnailing failed even with relevant environment variables removed | The system SVG decoding chain was malfunctioning, not just the current shell environment |
| apt reported `dpkg was interrupted` | An unfinished package configuration operation was confirmed |
| The user confirmed recovery after following the package-manager repair procedure | The procedure worked; complete logs are unavailable, so no single command can be identified as the sole fix |

**The best-supported explanation is an interrupted system package operation,
leaving configuration incomplete. SVG decoder installation or registration,
including its loader cache, may have been affected.** The exact interrupted
package, trigger, or initiating installation cannot be established from the
available logs. Power loss, cancellation, terminal closure, or a failed package
script are possibilities, not confirmed causes. There is no proof that the
project's Conda/pip commands directly damaged system files.

Icon rendering depends on theme files, the SVG plugin, the GdkPixbuf loader
cache, and desktop processes. Rebuilding the cache registers loaders; it does
not modify image content. See the [Ubuntu loader utility manual](https://manpages.ubuntu.com/manpages/jammy/man1/gdk-pixbuf-query-loaders.1.html).

## 2. Recovery Procedure

### 2.1 Stop the Robot and Inspect the System

Safely stop the host, teleoperation, replay, and debug tools. Support components
that could fall when disabled, save work, and ensure stable power. Wait for any
active apt/dpkg or software update task to finish. Do not remove lock files or
kill the package manager merely because it holds a lock.

Run these read-only checks from any directory:

```bash
df -h / /home
df -i / /home
sudo dpkg --audit
gsettings get org.gnome.desktop.interface icon-theme
printenv | grep -E 'LD_LIBRARY_PATH|LD_PRELOAD|GDK_PIXBUF|GTK_PATH|GTK_DATA_PREFIX'
grep -nE 'LD_LIBRARY_PATH|LD_PRELOAD|GDK_PIXBUF|GTK_PATH|GTK_DATA_PREFIX|anaconda|conda|source ' ~/.bashrc ~/.profile /etc/environment
```

No matching environment variables is not an error. Run `gsettings` in the
Jetson desktop terminal. If space or inodes are exhausted, free only data known
to be expendable, not system libraries, the dpkg database, or JetPack files.

### 2.2 Complete Interrupted Package Configuration First

If the audit reports unfinished configuration or apt displays:

```text
E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem.
```

run:

```bash
sudo dpkg --configure -a
```

This completes all pending package configurations and associated triggers, not
just icon packages. Do not shut down or interrupt a normally progressing task.
On failure, retain the complete error and identify the failing package instead
of repeatedly forcing operations or removing NVIDIA packages.
See the [dpkg manual](https://manpages.ubuntu.com/manpages/jammy/man1/dpkg.1.html).

Only if broken dependencies are reported, inspect a simulated repair first:

```bash
sudo apt-get -s --fix-broken install
```

After reviewing the plan, repair and retry configuration:

```bash
sudo apt-get --fix-broken install
sudo dpkg --configure -a
```

**Stop if the plan removes NVIDIA, JetPack, CUDA, ROS, or many desktop packages.
Investigate repositories and dependencies first. Simulation does not change
the system; do not add automatic confirmation (`-y`) to the real repair.**
See the [APT repair and simulation options](https://manpages.ubuntu.com/manpages/jammy/man8/apt-get.8.html).

### 2.3 Reinstall Image Decoders if SVG Icons Still Fail

```bash
sudo apt update
sudo apt install --reinstall libgdk-pixbuf-2.0-0 librsvg2-2 librsvg2-common
```

Review the operation list before accepting it. A full OS upgrade or CUDA
reinstallation is not needed for this step. Even if icons recover now, verify
that package configuration is complete.

### 2.4 Rebuild the System Loader Cache

Use the Ubuntu 22.04 ARM64 system utility, not a tool from Conda:

```bash
sudo env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders --update-cache
```

Success usually produces no output. On missing libraries, `undefined symbol`,
or a missing tool, retain the error; do not replace system `.so` files with
copies from another machine or use a Conda utility to update the system cache.

### 2.5 Verify SVG Decoding and Log In Again

```bash
env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/bin/gdk-pixbuf-thumbnailer \
  /usr/share/icons/Adwaita/scalable/actions/go-previous-symbolic.svg \
  /tmp/jetson-icon-test-clean.png

file /tmp/jetson-icon-test-clean.png
sudo dpkg --audit
sudo apt-get check
```

Expect no SVG warning, `PNG image data` for the generated file, no outstanding
issues from the audit, and a successful dependency check. If the source icon
does not exist, use an existing system SVG before diagnosing decoder failure.

Save work, **log out of the desktop, and log in again**. Existing desktop
processes do not inherit changes made by `unset` or `source ~/.bashrc` in a
terminal. If package tools require a reboot, schedule it after configuration
has finished, not during installation.

## 3. If the Problem Persists

Check whether the SVG plugin exists and can be loaded:

```bash
ls -l /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so
env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so
```

| Result | Next check |
| --- | --- |
| Plugin missing | Verify that `librsvg2-common` installed successfully |
| Missing dependency, symbol error, or load failure | Investigate library versions, `/usr/local/lib`, and global library paths; do not delete system libraries |
| Plugin loads but SVG thumbnailing fails | Check SVG cache registration, the actual icon file, and the complete error |
| SVG works but desktop icons remain broken | Verify a fresh login, the active theme, and desktop logs |

Reinstall themes only if their files are missing:

```bash
sudo apt install --reinstall adwaita-icon-theme yaru-theme-icon
```

Keep terminal output and inspect `/var/log/apt/history.log`,
`/var/log/apt/term.log`, and `/var/log/dpkg.log` to identify interrupted packages
and times. A Nautilus sharing warning about a missing `net` command does not
diagnose icon failure; installing Samba is not an icon fix. Clearing photo
thumbnail caches is not the repair for this system-icon incident.

## 4. Prevention

- Install project dependencies in separate Conda environments; do not use `sudo pip install` against system Python.
- Do not globally add Conda library directories in `.bashrc`, `.profile`, or `/etc/environment`. Remove obsolete injections such as the other-user Anaconda path seen in this incident.
- Back up startup files before editing. Remove only confirmed conflicting entries; retain normal Conda initialization and necessary ROS/CUDA paths. Do not globally clear Jetson library paths.
- Apply special library settings only to the process needing them, not to the desktop session. See [Conda's shared-library guidance](https://docs.conda.io/projects/conda-build/en/stable/resources/use-shared-libraries.html).
- Keep power, network, and terminals stable during apt/dpkg operations. For SSH maintenance, consider `tmux`; reconnect to an existing task rather than launching another installation.
- Check disk space and inodes before installing. This device was already 93% full; plan storage for datasets, models, and caches.
- Avoid blind `apt autoremove`, forced downgrades, mixing Ubuntu release repositories, or overwriting `/usr/lib`. Keep JetPack/NVIDIA repositories compatible with the device OS.

No Jetson system repair commands were executed remotely by the coding agent;
the recovery report came from the user's hardware test.
