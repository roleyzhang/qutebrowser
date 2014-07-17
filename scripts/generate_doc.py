# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Generate asciidoc source for qutebrowser based on docstrings."""

import os
import sys
import cgi
import shutil
import inspect
import subprocess
from collections import Counter
from tempfile import mkstemp

sys.path.insert(0, os.getcwd())

# We import qutebrowser.app so all @cmdutils-register decorators are run.
import qutebrowser.app  # pylint: disable=unused-import
import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.configdata as configdata
from qutebrowser.utils.usertypes import enum


def _open_file(name, mode='w'):
    """Open a file with a preset newline/encoding mode."""
    return open(name, mode, newline='\n', encoding='utf-8')


def _parse_docstring(func):  # noqa
    """Generate documentation based on a docstring of a command handler.

    The docstring needs to follow the format described in HACKING.

    Args:
        func: The function to generate the docstring for.

    Return:
        A (short_desc, long_desc, arg_descs) tuple.
    """
    # pylint: disable=too-many-branches
    State = enum('short', 'desc',  # pylint: disable=invalid-name
                 'desc_hidden', 'arg_start', 'arg_inside', 'misc')
    doc = inspect.getdoc(func)
    lines = doc.splitlines()

    cur_state = State.short

    short_desc = []
    long_desc = []
    arg_descs = {}
    cur_arg_name = None

    for line in lines:
        if cur_state == State.short:
            if not line:
                cur_state = State.desc
            else:
                short_desc.append(line.strip())
        elif cur_state == State.desc:
            if line.startswith('Args:'):
                cur_state = State.arg_start
            elif line.startswith('Emit:') or line.startswith('Raise:'):
                cur_state = State.misc
            elif line.strip() == '//':
                cur_state = State.desc_hidden
            elif line.strip():
                long_desc.append(line.strip())
        elif cur_state == State.misc:
            if line.startswith('Args:'):
                cur_state = State.arg_start
            else:
                pass
        elif cur_state == State.desc_hidden:
            if line.startswith('Args:'):
                cur_state = State.arg_start
        elif cur_state == State.arg_start:
            cur_arg_name, argdesc = line.split(':', maxsplit=1)
            cur_arg_name = cur_arg_name.strip()
            arg_descs[cur_arg_name] = [argdesc.strip()]
            cur_state = State.arg_inside
        elif cur_state == State.arg_inside:
            if not line:
                break
            elif line[4:].startswith(' '):
                arg_descs[cur_arg_name].append(line.strip())
            else:
                cur_arg_name, argdesc = line.split(':', maxsplit=1)
                cur_arg_name = cur_arg_name.strip()
                arg_descs[cur_arg_name] = [argdesc.strip()]

    return (short_desc, long_desc, arg_descs)


def _get_cmd_syntax(name, cmd):
    """Get the command syntax for a command."""
    # pylint: disable=no-member
    words = []
    argspec = inspect.getfullargspec(cmd.handler)
    if argspec.defaults is not None:
        defaults = dict(zip(reversed(argspec.args),
                        reversed(list(argspec.defaults))))
    else:
        defaults = {}
    words.append(name)
    minargs, maxargs = cmd.nargs
    i = 1
    for arg in argspec.args:
        if arg in ['self', 'count']:
            continue
        if minargs is not None and i <= minargs:
            words.append('<{}>'.format(arg))
        elif maxargs is None or i <= maxargs:
            words.append('[<{}>]'.format(arg))
        i += 1
    return (' '.join(words), defaults)


def _get_command_quickref(cmds):
    """Generate the command quick reference."""
    out = []
    out.append('[options="header",width="75%",cols="25%,75%"]')
    out.append('|==============')
    out.append('|Command|Description')
    for name, cmd in cmds:
        desc = inspect.getdoc(cmd.handler).splitlines()[0]
        out.append('|<<cmd-{},{}>>|{}'.format(name, name, desc))
    out.append('|==============')
    return '\n'.join(out)


def _get_setting_quickref():
    """Generate the settings quick reference."""
    out = []
    for sectname, sect in configdata.DATA.items():
        if not getattr(sect, 'descriptions'):
            continue
        out.append(".Quick reference for section ``{}''".format(sectname))
        out.append('[options="header",width="75%",cols="25%,75%"]')
        out.append('|==============')
        out.append('|Setting|Description')
        for optname, _option in sect.items():
            desc = sect.descriptions[optname]
            out.append('|<<setting-{}-{},{}>>|{}'.format(
                sectname, optname, optname, desc))
        out.append('|==============')
    return '\n'.join(out)


def _get_command_doc(name, cmd):
    """Generate the documentation for a command."""
    output = ['[[cmd-{}]]'.format(name)]
    output += ['==== {}'.format(name)]
    syntax, defaults = _get_cmd_syntax(name, cmd)
    output.append('+:{}+'.format(syntax))
    output.append("")
    short_desc, long_desc, arg_descs = _parse_docstring(cmd.handler)
    output.append(' '.join(short_desc))
    output.append("")
    output.append(' '.join(long_desc))
    if arg_descs:
        output.append("")
        for arg, desc in arg_descs.items():
            item = "* +{}+: {}".format(arg, ' '.join(desc))
            if arg in defaults:
                item += " (default: +{}+)".format(defaults[arg])
            output.append(item)
        output.append("")
    output.append("")
    return '\n'.join(output)


def generate_header(f):
    """Generate an asciidoc header."""
    f.write('= qutebrowser manpage\n')
    f.write('Florian Bruhin <mail@qutebrowser.org>\n')
    f.write(':toc:\n')
    f.write(':homepage: http://www.qutebrowser.org/\n')


def generate_commands(f):
    """Generate the complete commands section."""
    f.write('\n')
    f.write("== Commands\n")
    normal_cmds = []
    hidden_cmds = []
    debug_cmds = []
    for name, cmd in cmdutils.cmd_dict.items():
        if cmd.hide:
            hidden_cmds.append((name, cmd))
        elif cmd.debug:
            debug_cmds.append((name, cmd))
        else:
            normal_cmds.append((name, cmd))
    normal_cmds.sort()
    hidden_cmds.sort()
    debug_cmds.sort()
    f.write("\n")
    f.write("=== Normal commands\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(normal_cmds) + "\n")
    for name, cmd in normal_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")
    f.write("\n")
    f.write("=== Hidden commands\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(hidden_cmds) + "\n")
    for name, cmd in hidden_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")
    f.write("\n")
    f.write("=== Debugging commands\n")
    f.write("These commands are mainly intended for debugging. They are "
            "hidden if qutebrowser was started without the `--debug`-flag.\n")
    f.write("\n")
    f.write(".Quick reference\n")
    f.write(_get_command_quickref(debug_cmds) + "\n")
    for name, cmd in debug_cmds:
        f.write(_get_command_doc(name, cmd) + "\n")


def generate_settings(f):
    """Generate the complete settings section."""
    f.write("\n")
    f.write("== Settings\n")
    f.write(_get_setting_quickref() + "\n")
    for sectname, sect in configdata.DATA.items():
        f.write("\n")
        f.write("=== {}".format(sectname) + "\n")
        f.write(configdata.SECTION_DESC[sectname] + "\n")
        if not getattr(sect, 'descriptions'):
            pass
        else:
            for optname, option in sect.items():
                f.write("\n")
                f.write('[[setting-{}-{}]]'.format(sectname, optname) + "\n")
                f.write("==== {}".format(optname) + "\n")
                f.write(sect.descriptions[optname] + "\n")
                f.write("\n")
                valid_values = option.typ.valid_values
                if valid_values is not None:
                    f.write("Valid values:\n")
                    f.write("\n")
                    for val in valid_values:
                        try:
                            desc = valid_values.descriptions[val]
                            f.write(" * +{}+: {}".format(val, desc) + "\n")
                        except KeyError:
                            f.write(" * +{}+".format(val) + "\n")
                    f.write("\n")
                if option.default:
                    f.write("Default: +pass:[{}]+\n".format(cgi.escape(
                        option.default)))
                else:
                    f.write("Default: empty\n")


def regenerate_authors(filename):
    """Re-generate the authors inside README based on the commits made."""
    commits = subprocess.check_output(['git', 'log', '--format=%aN'])
    cnt = Counter(commits.decode('utf-8').splitlines())
    oshandle, tmpname = mkstemp()
    with _open_file(filename, mode='r') as infile, \
            _open_file(oshandle, mode='w') as temp:
        ignore = False
        for line in infile:
            if line.strip() == '// QUTE_AUTHORS_START':
                ignore = True
                temp.write(line)
                for author in sorted(cnt, key=lambda k: cnt[k]):
                    temp.write('* {}\n'.format(author))
            elif line.strip() == '// QUTE_AUTHORS_END':
                temp.write(line)
                ignore = False
            elif not ignore:
                temp.write(line)
    os.remove(filename)
    shutil.move(tmpname, filename)


if __name__ == '__main__':
    with _open_file('doc/qutebrowser.asciidoc') as fobj:
        generate_header(fobj)
        generate_settings(fobj)
        generate_commands(fobj)
    regenerate_authors('README.asciidoc')