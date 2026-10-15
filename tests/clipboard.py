"""Copy/Cut/Paste reaches another process through the session's clipboard provider."""
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from ui import Editor


# Isolate clipboard transport from the user's desktop while exercising Neovim's
# real provider detection, subprocess jobs, mappings, menus and text encoding.
transport = '''#!/usr/bin/python3
import os
from pathlib import Path
import sys
name = Path(sys.argv[0]).name
if name == "xsel":
    sys.exit(1)
root = Path(os.environ["NVIM_TEST_CLIPBOARD_DIR"])
primary = "--primary" in sys.argv or "primary" in sys.argv
target = root / ("primary" if primary else "clipboard")
reading = name == "wl-paste" or "-o" in sys.argv
if reading:
    if target.exists():
        sys.stdout.buffer.write(target.read_bytes())
else:
    target.write_bytes(sys.stdin.buffer.read())
    (root / "writer").write_text(name)
'''

with tempfile.TemporaryDirectory(prefix='nvim-clipboard-') as directory:
    root = Path(directory)
    binaries = root / 'bin'
    binaries.mkdir()
    for name in ('wl-copy', 'wl-paste', 'xclip', 'xsel'):
        path = binaries / name
        path.write_text(transport)
        path.chmod(0o755)
    original = ['Alpha beta', 'Zażółć gęślą jaźń 🦊', 'Third line']
    project = root / 'project'
    project.mkdir()
    file = project / 'example.txt'
    file.write_text('\n'.join(original) + '\n')

    for profile in ('wayland', 'x11', 'explicit'):
        channel = root / profile
        channel.mkdir()
        env = {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
               'DISPLAY': ':clipboard-test', 'NVIM_TEST_CLIPBOARD_DIR': str(channel)}
        if profile == 'x11':
            env.pop('WAYLAND_DISPLAY', None)
        else:
            env['WAYLAND_DISPLAY'] = 'wayland-clipboard-test'
        args = ()
        if profile == 'explicit':
            args = ('--cmd', 'lua vim.g.clipboard={name="Explicit test provider",'
                    'copy={["+"]={"wl-copy"},["*"]={"wl-copy","--primary"}},'
                    'paste={["+"]={"wl-paste","--no-newline"},'
                    '["*"]={"wl-paste","--no-newline","--primary"}},cache_enabled=0}')
        with patch.dict(os.environ, env, clear=True):
            editor = Editor(project, root / ('state-' + profile), args=args)
            try:
                editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
                expected_provider = {'wayland': 'wl-copy', 'x11': 'xclip', 'explicit': 'Explicit test provider'}[profile]
                assert editor.lua('return vim.fn["provider#clipboard#Executable"]()') == expected_provider
                assert 'unnamedplus' in editor.lua('return vim.opt.clipboard:get()')
                reader = ['xclip', '-o', '-selection', 'clipboard'] if profile == 'x11' else ['wl-paste', '--no-newline']
                writer = ['xclip', '-i', '-selection', 'clipboard'] if profile == 'x11' else ['wl-copy']

                def external():
                    return subprocess.check_output(reader).decode()

                def copy_key():
                    # Feed the mapped key through Neovim's input machinery;
                    # raw CTRL-C via nvim_input may interrupt the RPC itself.
                    editor.lua('vim.api.nvim_feedkeys(vim.keycode("<C-c>"),"mtx!",false)')

                def copied(text):
                    def transferred():
                        # Drain UI/RPC output so startup redraws cannot block
                        # processing nvim_input before the provider job starts.
                        editor.lua('return true')
                        return (channel / 'clipboard').exists() and external() == text
                    try:
                        editor.wait(transferred,
                                    profile + ': another process reads the copied text')
                    except AssertionError:
                        print({'profile': profile, 'expected': text,
                               'actual': external() if (channel / 'clipboard').exists() else None,
                               'writer': (channel / 'writer').read_text() if (channel / 'writer').exists() else None,
                               'state': editor.lua('local m=vim.fn.maparg("<C-c>","n",false,true);'
                                                   'return {mode=vim.fn.mode(),ft=vim.bo.filetype,buf=vim.api.nvim_buf_get_name(0),'
                                                   'mapping=m.desc,clipboard=vim.o.clipboard,provider=vim.g.loaded_clipboard_provider,'
                                                   'messages=vim.fn.execute("messages")}')})
                        raise
                    assert (channel / 'writer').read_text() == ('xclip' if profile == 'x11' else 'wl-copy')

                def reset(line=1):
                    editor.lua('local lines,line=...;vim.cmd("stopinsert");'
                               'vim.api.nvim_feedkeys(vim.keycode("<Esc>"),"nx",false);'
                               'vim.api.nvim_buf_set_lines(0,0,-1,false,lines);'
                               'vim.api.nvim_win_set_cursor(0,{line,0})', original, line)

                for mode, line in (('normal', 1), ('insert', 2)):
                    reset(line)
                    if mode == 'insert':
                        editor.lua('vim.cmd("startinsert")')
                        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Insert mode')
                    copy_key()
                    copied(original[line - 1] + '\n')
                    assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == original

                for mode in ('select', 'visual'):
                    reset()
                    editor.call('nvim_input', '<S-End>')
                    editor.wait(lambda: editor.lua('return vim.fn.mode()') == 's', 'Shift selection')
                    if mode == 'visual':
                        editor.lua('vim.api.nvim_feedkeys(vim.keycode("<C-g>"),"nx",false)')
                    copy_key()
                    copied(original[0])
                    assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == original

                reset()
                editor.call('nvim_input', '<S-End>')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 's', 'Cut selection')
                editor.call('nvim_input', '<C-x>')
                copied(original[0])
                assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == ['', *original[1:]]

                # Pasting text written by an independent process must bypass old data.
                incoming = 'Outside: żółw 🦊\nSecond external line'
                subprocess.run(writer, input=incoming.encode(), check=True)
                editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"prefix "});'
                           'vim.api.nvim_win_set_cursor(0,{1,7});vim.cmd("startinsert")')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Paste into Insert')
                editor.call('nvim_input', '<C-v>')
                editor.wait(lambda: editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)')
                            == ['prefix Outside: żółw 🦊', 'Second external line'], 'External clipboard paste')

                reset(2)
                editor.lua('vim.cmd("redraw!")')
                heading = ''.join(editor.grid[0]).index(' Edit ') + 2
                editor.click(0, heading)
                editor.wait(lambda: editor.lua('return vim.bo.filetype') == 'NvMenu', 'Edit menu')
                editor.lua('vim.cmd("redraw!")')
                point = next((row, ''.join(cells).index('Copy') + 2)
                             for row, cells in enumerate(editor.grid) if 'Copy' in ''.join(cells))
                editor.click(*point)
                copied(original[1] + '\n')
                assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
                print('PASS:', profile, 'provider; external reads after Normal/Insert/Select/Visual Ctrl+C, Ctrl+X and Edit > Copy; external Unicode/multiline Ctrl+V.')
            finally:
                editor.close()
