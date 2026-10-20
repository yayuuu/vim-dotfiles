"""Terminal mouse and keyboard focus route typed commands to the shell."""
import tempfile
from pathlib import Path
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-terminal-input-') as directory:
    root = Path(directory)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(require("config.ide").editor_window())')
        position = editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.win);return {p[1]+2,p[2]+5}')
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Clicking terminal starts terminal input')
        def command(label):
            target = root / label
            editor.call('nvim_input', 'printf ok > ' + str(target) + '<CR>')
            editor.wait(lambda: target.exists() and target.read_text() == 'ok', 'Typed command executes: ' + label)
        command('mouse.txt')
        editor.call('nvim_input', '<Esc><Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Esc Esc exits terminal input')
        # Use a different column so this gesture is a single click, not a double click selection.
        editor.click(position[0], position[1] + 1)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Clicking same terminal resumes input')
        command('resume.txt')
        editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(require("config.ide").editor_window())')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') != 't', 'Focus leaves terminal input')
        editor.lua('vim.api.nvim_set_current_win(require("config.terminals").win)')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Keyboard focus starts terminal input')
        command('focus.txt')
        editor.lua('require("config.terminals").new()')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'New terminal starts input')
        command('new.txt')
        # A native prompt may finish leaving Insert after WinEnter. Delayed
        # terminal entry must still yield to an immediate, deliberate Esc Esc.
        editor.lua('vim.api.nvim_set_current_win(require("config.ide").editor_window());'
                   'vim.api.nvim_set_current_win(require("config.terminals").win)')
        editor.call('nvim_input', '<Esc><Esc>')
        editor.lua('vim.wait(80)')
        assert editor.lua('return vim.fn.mode()') == 'n', 'Quick Esc Esc cancels pending terminal entry'
        editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(require("config.ide").editor_window())')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') != 't', 'Editor retains its own input mode')
        print('PASS: terminal accepts typed commands after mouse click, same-pane click after Esc Esc, keyboard focus, and New terminal.')
    finally:
        editor.close()
