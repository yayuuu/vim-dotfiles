"""Vertical native dividers remain draggable beside blank lists and scrollbars."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-sidebar-resize-') as directory:
    root = Path(directory)
    for overflow in (False, True):
        project = root / ('overflow' if overflow else 'compact')
        project.mkdir()
        code = project / 'code.txt'
        code.write_text('Keep this document\n')
        if overflow:
            for index in range(80):
                (project / f'file-{index:02}.txt').write_text('content\n')
        editor = Editor(project, root / f'state-{overflow}')
        try:
            editor.lua('require("config.ide").open_file(...)', str(code))
            main = editor.lua('return require("config.ide").editor_window()')
            document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
            tree = editor.lua('return require("config.sidebar").state().winid')
            editor.wait(lambda: editor.lua('return not require("config.layout").scaling and '
                                          'not require("config.sidebar").changing'), 'Sidebar settles')
            if overflow:
                editor.wait(lambda: editor.lua('local s=require("config.vscroll").sources[...];return s and s.bar~=nil', tree),
                            'Vertical tree scrollbar appears')
            for mode in ('normal', 'insert', 'terminal'):
                if mode == 'terminal':
                    editor.lua('require("config.terminals").show(require("config.terminals").items[1].buf)')
                    editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
                else:
                    editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(...);'
                               'vim.cmd("startinsert")' if mode == 'insert' else
                               'vim.cmd("stopinsert");vim.api.nvim_set_current_win(...)', main)
                    editor.wait(lambda: editor.lua('return vim.fn.mode()') == ('i' if mode == 'insert' else 'n'), 'Editor mode')
                position = editor.call('nvim_win_get_position', tree)
                width = editor.call('nvim_win_get_width', tree)
                height = editor.call('nvim_win_get_height', tree)
                # This is the native separator, one column beyond the tree body/bar.
                row, column = position[0] + height - 3, position[1] + width
                editor.call('nvim_input_mouse', 'left', 'press', '', 0, row, column)
                editor.lua('vim.cmd("redraw!")')
                mouse = editor.lua('return vim.fn.getmousepos()')
                owner = editor.lua('return require("config.mouse_capture").active()')
                editor.call('nvim_input_mouse', 'left', 'drag', '', 0, row, column + 5)
                editor.lua('vim.cmd("redraw!")')
                editor.call('nvim_input_mouse', 'left', 'release', '', 0, row, column + 5)
                try:
                    editor.wait(lambda: editor.call('nvim_win_get_width', tree) == width + 5, 'Native sidebar width changes')
                except AssertionError:
                    raise AssertionError((overflow, mode, mouse, 'captured', owner))
                assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
                assert editor.lua('return not require("config.mouse_capture").active()')
        finally:
            editor.close()
    print('PASS: native sidebar dividers resize from Normal/Insert/terminal input beside blank content and vertical scrollbars without opening files.')
