#!/usr/bin/env python3

# this program is for acting on joystick events: buttons and axes
# (c) 2020, Hayati Ayguen <h_ayguen@web.de>
# website: https://github.com/hayguen/pi_button_actions
# LICENSE: the Unlicense (unlicense.org)
#
# it is based on a simplified version of js_linux.py from
# https://gist.github.com/emdeex/97b771b264bebbd1e18dd897404040be
# or https://gist.github.com/rdb/8864666
# Released by rdb under the Unlicense (unlicense.org)
#
# alternative to above js_linux.py,
# the 'python3-pygame' package could be used.
# see  https://www.pygame.org/docs/ref/joystick.html


import os, sys, subprocess
import struct, array
from fcntl import ioctl
from pathlib import Path


verbose_output = False
print_device_info = False
axe_thresh_val = 0.8
max_duration = 1000   # in ms

dev_fn = ""
scriptdir = ""
argshift = 0

if 1 < len(sys.argv):
    if sys.argv[1] == '-v' or sys.argv[1] == '--verbose':
        verbose_output = True
        print_device_info = True
        argshift = 1
    elif sys.argv[1] == '-h' or sys.argv[1] == '--help':
        print("usage: {} [ -v | --verbose | -h | --help ] [ <device_name> [<script_dir>] ]".format(sys.argv[0]))
        print("    verbose         print (more) information")
        print("    help            prints this usage")
        print("    device_name     name of joystick device, e.g. /dev/input/js0")
        print("    script_dir      execute 'on_event' scripts from given directory, default: $HOME")
        print("")
        print("scripts are executed when joystick buttons are pressed.")
        print("to be more specific, the script is executed when the the button is released")
        print(" - except the button was pressed more than {} ms".format(max_duration))
        print("")
        sys.exit()

if 1+argshift < len(sys.argv):
    dev_fn = sys.argv[1+argshift]
else:
    # Iterate over the joystick devices
    if verbose_output:
        print("Available joystick devices:".format(dev_fn), file=sys.stderr)
    for inpname in os.listdir('/dev/input'):
        if inpname.startswith('js'):
            if verbose_output:
                print("  /dev/input/{}".format(inpname), file=sys.stderr)
            if len(dev_fn) <= 0:
                dev_fn = "/dev/input/" + inpname

if 2+argshift < len(sys.argv):
    scriptdir = sys.argv[2+argshift]
else:
    scriptdir = str(Path.home())

if verbose_output:
    print("Using JoyStick Device  '{}'".format(dev_fn), file=sys.stderr)
    print("Using Script Directory '{}'".format(scriptdir), file=sys.stderr)


# Open the joystick device
jsdev = open(dev_fn, 'rb')

if print_device_info:
    # Get the device name
    buf = array.array('B', [0] * 64)
    ioctl(jsdev, 0x80006a13 + (0x10000 * len(buf)), buf) # JSIOCGNAME(len)
    js_name = buf.tostring().rstrip(b'\x00').rstrip(b'\x20').decode('utf-8')

    # Get number of axes and buttons
    buf = array.array('B', [0])
    ioctl(jsdev, 0x80016a11, buf) # JSIOCGAXES
    num_axes = buf[0]

    buf = array.array('B', [0])
    ioctl(jsdev, 0x80016a12, buf) # JSIOCGBUTTONS
    num_buttons = buf[0]

    print("device '{}': {} buttons and {} axes".format(js_name, num_buttons, num_axes), file=sys.stderr)

button_press_time = {}
axes_prev_time = {}
axes_prev_value = {}
action_fn = ""

# Main event loop
while True:
    evbuf = jsdev.read(8)
    if evbuf:
        time, value, type, number = struct.unpack('IhBB', evbuf)
        action_fn = ""
        action_str = ""

        if type & 0x80:
            continue    #print("(initial)", file=sys.stderr)

        if type & 0x01:
            button = number
            if value:
                button_press_time[button] = time
                #print("button # {} pressed".format(button))
            else:
                if button in button_press_time:
                    duration = time - button_press_time[button]
                    if duration < max_duration:
                        action_fn = "on_button_" + str(button) + "_pressed"
                        action_str = ": => " + action_fn
                if verbose_output:
                    print("button # {} released{}".format(button, action_str), file=sys.stderr)

        if type & 0x02:
            axis = number
            fvalue = axis / 32767.0
            if axis in axes_prev_time and axis in axes_prev_value:
                duration = time - axes_prev_time[axis]
                if fvalue == 0 and duration < max_duration:
                    if axes_prev_value[axis] < -axe_thresh_val:
                        action_fn = "on_axis_" + str(axis) + "_negative"
                        action_str = ": => " + action_fn
                    elif axes_prev_value[axis] > axe_thresh_val:
                        action_fn = "on_axis_" + str(axis) + "_positive"
                        action_str = ": => " + action_fn
                if verbose_output:
                    print("axis # {}: {} -> {} after {} ms{}".format(axis, axes_prev_value[axis], fvalue, duration, action_str), file=sys.stderr)
            else:
                #print("axis # {}: -> {}".format(axis, fvalue))
                pass
            axes_prev_time[axis] = time
            axes_prev_value[axis] = fvalue

        if len(action_fn) > 0:
            script_file = scriptdir + "/" + action_fn
            if Path(script_file).is_file():
                subprocess.Popen( [script_file], shell=True)    # run in background
            elif verbose_output:
                print("warning: file '{}' does not exist".format(script_file), file=sys.stderr)

