"""The global menu remains clickable above either column of an editable diff."""
from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-diff-menu-') as directory:
    root = Path(directory)
    file = root / 'example.txt'
    file.write_text('A document\n')
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.diff").open(...)', str(file))
        active = editor.lua('return require("config.diff").active')
        for width in (100, 160, 240, 100):
            editor.call('nvim_ui_try_resize', width, 48)
            editor.lua('require("config.layout").reflow();vim.cmd("redraw!")')
            for mode in ('normal', 'insert'):
                editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert")', active['right'])
                if mode == 'insert':
                    editor.lua('vim.cmd("startinsert")')
                for name in ('File', 'Edit', 'Search', 'View', 'Project', 'Git', 'Debug', 'Terminal', 'Help'):
                    editor.lua('vim.cmd("redraw!")')
                    column = ''.join(editor.grid[0]).index(' ' + name + ' ') + 2
                    editor.click(0, column)
                    editor.wait(lambda: editor.lua('return require("config.ide").menu_name') == name,
                                f'{name} menu opens above diff at width {width} in {mode}')
                    editor.click(0, column)
                    editor.wait(lambda: editor.lua('return require("config.ide").menu_name') is None,
                                f'{name} menu closes on repeated click')
                    assert editor.lua('return require("config.diff").active.buf') == active['buf']
                for name in ('Terminal', 'Debug', 'Terminal', 'Help', 'Debug', 'Terminal'):
                    editor.lua('vim.cmd("redraw!")')
                    column = ''.join(editor.grid[0]).index(' ' + name + ' ') + 2
                    editor.click(0, column)
                    editor.wait(lambda: editor.lua('return require("config.ide").menu_name') == name,
                                f'Switch to {name} above diff at width {width} in {mode}')
                    time.sleep(.2)
                    assert editor.lua('return require("config.ide").menu_name') == name, 'Replacement menu stays open'
                    assert editor.lua('return #require("menu.state").bufids') == 1
                editor.lua('require("config.ide").close_menu()')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: all toolbar headings open/close over both diff columns in Normal/Insert and after resizing.')
    finally:
        editor.close()
