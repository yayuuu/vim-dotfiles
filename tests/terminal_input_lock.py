"""Managed terminal commands never reach Normal, even after native scrollback."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-terminal-input-lock-') as directory:
    root = Path(directory)
    source = root / 'document.txt'
    source.write_text('Document\n')
    (root / 'reader.py').write_text(
        'import os,pathlib,tty\ntty.setraw(0)\n'
        'os.write(1,("\\x1b[3J\\x1b[2J\\x1b[H"+"\\r\\n".join("Row-"+str(i) for i in range(100))+"\\r\\n").encode())\n'
        'pathlib.Path("ready").touch()\n'
        'with open("input","ab",buffering=0) as log:\n'
        '    while True: log.write(os.read(0,4096))\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved document"});'
                   'local t=require("config.terminals");t.show(t.active);vim.fn.chansend(t.items[1].job,"/usr/bin/python3 -B reader.py\\n")', str(source))
        document = editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())')
        terminal, buf, job = editor.lua('local t=require("config.terminals");return {t.win,t.active,t.items[1].job}')
        editor.wait((root / 'ready').exists, 'Raw PTY reader starts')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')

        def receive(keys, expected):
            before = (root / 'input').stat().st_size
            editor.call('nvim_input', keys)
            editor.wait(lambda: (root / 'input').stat().st_size >= before + len(expected), 'PTY receives literal input')
            time.sleep(.06)
            assert (root / 'input').read_bytes()[before:] == expected
            assert editor.lua('return vim.fn.mode()') == 't'
            assert editor.lua('return vim.api.nvim_get_current_win()') == terminal
            assert editor.lua('return vim.api.nvim_win_get_buf(...)', terminal) == buf

        receive('<C-\\><C-n>q:bd<CR>', b'q:bd\r')
        receive('<C-\\><C-o>dd', b'dd')
        receive('<Esc><Esc>', b'\x1b\x1b')
        editor.lua('vim.cmd("stopinsert")')
        receive('q:delete<CR>', b'q:delete\r')
        editor.lua('vim.cmd("stopinsert")')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'External mode changes recover terminal input')

        def bar():
            return editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar', terminal)

        editor.wait(bar, 'History scrollbar')
        b = bar()
        pos = editor.call('nvim_win_get_position', b['win'])
        editor.click(pos[0], pos[1])
        editor.wait(lambda: bar()['start'] == 0, 'History remains scrollable')
        editor.lua('require("lualine").refresh({force=true});vim.cmd("redrawstatus")')
        time.sleep(.1)
        editor.lua('return true')
        assert 'TERMINAL' in ''.join(editor.grid[-1]) and 'NORMAL' not in ''.join(editor.grid[-1])
        receive('q:bd<CR>', b'q:bd\r')
        editor.wait(lambda: bar()['start'] == bar()['span'], 'Typing resumes the live terminal viewport')
        editor.click(pos[0], pos[1])
        editor.wait(lambda: bar()['start'] == 0, 'Scroll history before Unicode input')
        receive('żółw<CR>', 'żółw\r'.encode())
        editor.click(pos[0], pos[1])
        editor.wait(lambda: bar()['start'] == 0, 'Scroll history again')
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Esc exits history directly to input')
        editor.lua('require("config.terminals").hide()')
        editor.lua('require("config.terminals").toggle()')
        terminal = editor.lua('return require("config.terminals").win')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Reopening retains locked input')
        receive('typing<CR>', b'typing\r')
        assert editor.lua('return vim.fn.jobwait({...},0)[1]', job) == -1
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        assert editor.lua('return vim.bo[...].modified', document)
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: native escape shortcuts are blocked; queued text/Enter after external mode changes and history reaches the real PTY; '
              'Terminal badge, scrollback, Esc-to-input, reopening, child process and unsaved editor are preserved.')
    finally:
        editor.close()
