"""Shared terminal menus preserve PTY input, clipboard, selections and child mouse events."""
import json
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-terminal-menu-') as directory:
    root = Path(directory)
    source = root / 'document.txt'
    source.write_text('Document\n')
    clipboard = root / 'clipboard'
    clipboard.write_bytes(b'')
    transport = root / 'clipboard.py'
    transport.write_text('import pathlib,sys\np=pathlib.Path(sys.argv[2])\n'
                         'if sys.argv[1]=="copy": p.write_bytes(sys.stdin.buffer.read())\n'
                         'else: sys.stdout.buffer.write(p.read_bytes())\n')
    copy = ['/usr/bin/python3', '-B', str(transport), 'copy', str(clipboard)]
    paste = ['/usr/bin/python3', '-B', str(transport), 'paste', str(clipboard)]
    copy_lua = '{' + ','.join(json.dumps(arg) for arg in copy) + '}'
    paste_lua = '{' + ','.join(json.dumps(arg) for arg in paste) + '}'
    bootstrap = ('lua vim.g.clipboard={name="Isolated terminal test",cache_enabled=0,'
                 'copy={["+"]=' + copy_lua + ',["*"]=' + copy_lua + '},'
                 'paste={["+"]=' + paste_lua + ',["*"]=' + paste_lua + '}}')
    (root / 'reader.py').write_text(
        'import os,pathlib,tty\n'
        'tty.setraw(0)\n'
        'os.write(1,"\\x1b[3J\\x1b[2J\\x1b[HCopy żółw\\r\\nSecond line\\r\\n\\x1b[?2004h".encode())\n'
        'pathlib.Path("ready").touch()\n'
        'with open("input","ab",buffering=0) as log:\n'
        '    while True:\n'
        '        data=os.read(0,4096)\n'
        '        if data==b"enable":\n'
        '            os.write(1,b"\\x1b[?1000;1006h");pathlib.Path("enabled").touch()\n'
        '        elif data==b"disable":\n'
        '            os.write(1,b"\\x1b[?1000;1006l");pathlib.Path("disabled").touch()\n'
        '        else: log.write(data)\n')
    editor = Editor(root, root / 'state', args=('--cmd', bootstrap))
    try:
        editor.lua('require("config.ide").open_file(...);'
                   'vim.api.nvim_buf_set_lines(0,0,1,false,{"Unsaved document"});'
                   'local t=require("config.terminals");t.show(t.active);'
                   'vim.fn.chansend(t.items[1].job,"/usr/bin/python3 -B reader.py\\n")', str(source))
        editor.wait((root / 'ready').exists, 'Raw PTY reader starts')
        win, buf, job = editor.lua('local t=require("config.terminals");return {t.win,t.active,t.items[1].job}')
        document = editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())')

        def right_click():
            row, column = editor.lua('local p=vim.fn.screenpos(...,1,1);return {p.row-1,p.col+2}', win)
            editor.call('nvim_input_mouse', 'right', 'press', '', 0, row, column)
            editor.call('nvim_input_mouse', 'right', 'release', '', 0, row, column)

        def menu():
            editor.wait(lambda: editor.lua('return vim.bo.filetype') == 'NvMenu', 'Shared terminal menu opens')
            editor.lua('vim.cmd("redraw!")')
            names = editor.lua('return vim.tbl_map(function(item) return item.name end,'
                               'require("menu.state").bufs[vim.api.nvim_get_current_buf()].items)')
            assert names in (['Copy line', 'Paste', 'Select all', 'separator', 'New terminal'],
                             ['Copy', 'Paste', 'Select all', 'separator', 'New terminal']), names
            return names

        def choose(name):
            names = menu()
            row = names.index(name) + 1
            point = editor.lua('local p=vim.fn.screenpos(vim.api.nvim_get_current_win(),...,3);return {p.row-1,p.col-1}', row)
            editor.click(*point)
            editor.wait(lambda: editor.lua('return #require("menu.state").bufids') == 0, 'Menu action closes popup')

        def input_mode():
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input resumes')

        input_mode()
        before = (root / 'input').read_bytes()
        right_click()
        menu()
        editor.call('nvim_input', '<Down><Down><Up><Esc>')
        input_mode()
        assert (root / 'input').read_bytes() == before, 'Menu keys must not reach the child'

        editor.call('nvim_input', '<Esc><Esc>')
        input_mode()
        right_click()
        menu()
        editor.call('nvim_input', '<Esc>')
        input_mode()

        right_click()
        choose('Select all')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'V', 'Select all selects terminal output')
        selection = editor.lua('return {vim.fn.getpos("v"),vim.fn.getpos(".")}')
        selected_text = editor.lua('return table.concat(vim.fn.getregion(vim.fn.getpos("v"),vim.fn.getpos("."),'
                                   '{type="V"}),"\\n").."\\n"')
        assert 'Copy żółw' in selected_text
        right_click()
        assert menu()[0] == 'Copy'
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'V', 'Dismissal restores terminal selection')
        assert editor.lua('return {vim.fn.getpos("v"),vim.fn.getpos(".")}') == selection
        right_click()
        choose('Copy')
        editor.wait(lambda: subprocess.check_output(paste).decode() == selected_text,
                    'External clipboard reader receives the selected terminal output')

        editor.lua('require("config.terminals").show(...)', buf)
        input_mode()
        before = (root / 'input').stat().st_size
        incoming = 'Clipboard żółw\nSecond pasted line'
        subprocess.run(copy, input=incoming.encode(), check=True)
        terminal_lines = editor.call('nvim_buf_get_lines', buf, 0, -1, False)
        right_click()
        choose('Paste')
        input_mode()
        editor.wait(lambda: (root / 'input').stat().st_size > before, 'Paste reaches the child')
        received = (root / 'input').read_bytes()[before:]
        assert received == b'\x1b[200~' + incoming.encode() + b'\x1b[201~', received
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == terminal_lines

        editor.call('nvim_chan_send', job, 'enable')
        editor.wait((root / 'enabled').exists, 'Child enables mouse reporting')
        editor.wait(lambda: editor.lua('return require("config.terminals").mouse_enabled(...)', buf), 'Mouse mode observed')
        before = (root / 'input').stat().st_size
        right_click()
        editor.wait(lambda: (root / 'input').read_bytes()[before:].endswith(b'm'), 'Child receives press and release')
        received = (root / 'input').read_bytes()[before:]
        assert received.startswith(b'\x1b[<2;') and b'M' in received and received.endswith(b'm'), received
        assert editor.lua('return vim.fn.mode()') == 't'
        assert editor.lua('return #require("menu.state").bufids') == 0
        editor.call('nvim_chan_send', job, 'disable')
        editor.wait((root / 'disabled').exists, 'Child disables mouse reporting')
        editor.wait(lambda: not editor.lua('return require("config.terminals").mouse_enabled(...)', buf), 'Mouse mode cleared')
        right_click()
        choose('New terminal')
        editor.wait(lambda: editor.lua('return #require("config.terminals").items') == 2, 'Create another session')
        assert editor.lua('return vim.fn.jobwait({...},0)[1]', job) == -1, 'Original terminal job remains alive'
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == document
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: terminal uses shared menu/navigation; dismissal restores input and selection; '
              'external clipboard Copy and native bracketed Paste work; mouse-aware child receives full right clicks; '
              'new session preserves running child and unsaved document.')
    finally:
        editor.close()
