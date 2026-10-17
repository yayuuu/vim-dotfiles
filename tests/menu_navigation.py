"""Menus share one full-row selection between keyboard and pointer, without a caret."""
from pathlib import Path
import tempfile
import time

from ui import Editor


class MenuEditor(Editor):
    cursor_modes = []
    cursor_mode = 0

    def notify(self, message):
        super().notify(message)
        if message[0] == 2 and message[1] == 'redraw':
            for event in message[2]:
                if event[0] == 'mode_info_set':
                    self.cursor_modes = event[-1][1]
                elif event[0] == 'mode_change':
                    self.cursor_mode = event[-1][1]


with tempfile.TemporaryDirectory(prefix='nvim-menu-navigation-') as directory:
    root = Path(directory)
    path = root / 'document.txt'
    path.write_text('Preserve this document\n')
    editor = MenuEditor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(path))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor is ready')
        original_cursor = editor.lua('return vim.o.guicursor')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, 1, False, ['Unsaved document'])

        def pump():
            time.sleep(.05)
            editor.lua('return true')

        def window():
            return editor.lua('local b=require("config.ide").popup_buffer;return b and vim.fn.bufwinid(b)')

        def open_menu():
            editor.lua('vim.g.menu_choice=nil;require("config.ide").popup({'
                       '{name="First action",rtxt="F6",cmd=function() vim.g.menu_choice="first" end},'
                       '{name="separator"},'
                       '{name="Second action",rtxt="F7",cmd=function() vim.g.menu_choice="second" end},'
                       '{name="Last action",rtxt="F8",cmd=function() vim.g.menu_choice="last" end}})')
            pump()

        def position(row):
            return editor.lua('local p=vim.fn.screenpos(...,select(2,...),1);return {p.row-1,p.col-1}', window(), row)

        def highlighted():
            win = window()
            count = editor.call('nvim_win_get_height', win)
            width = editor.call('nvim_win_get_width', win)
            color = editor.lua('return vim.api.nvim_get_hl(0,{name="ExBlack3Bg",link=false}).bg')
            result = []
            for row in range(1, count + 1):
                screenrow, column = position(row)
                backgrounds = [editor.highlights.get(identifier, {}).get('background')
                               for identifier in editor.attributes[screenrow][column:column + width]]
                if color in backgrounds:
                    assert all(background == color for background in backgrounds), ('Partial row highlight', row)
                    result.append(row)
            return result

        def check(rows):
            editor.wait(lambda: highlighted() == rows, 'Visible selected rows: ' + repr(rows))
            assert editor.lua('return vim.o.guicursor') == 'a:DesktopMenuCursor'
            style = editor.cursor_modes[editor.cursor_mode]
            assert editor.highlights[style['attr_id']].get('blend') == 100, ('Caret is visible', style)

        def key(keys, rows):
            editor.call('nvim_input', keys)
            pump()
            check(rows)

        def hover(row, rows):
            screenrow, column = position(row)
            editor.call('nvim_input_mouse', 'move', '', '', 0, screenrow, column + 4)
            pump()
            check(rows)

        def leave(rows):
            editor.call('nvim_input_mouse', 'move', '', '', 0, 20, 140)
            pump()
            check(rows)

        def closed(choice=None):
            editor.wait(lambda: editor.lua('return #require("menu.state").bufids') == 0, 'Menu closes')
            if choice:
                editor.wait(lambda: editor.lua('return vim.g.menu_choice') == choice, 'Selected action runs')
            assert editor.lua('return vim.o.guicursor') == original_cursor, 'Restore editor caret'

        open_menu()
        check([])
        key('<CR>', [])  # No hidden first-row selection.
        assert editor.lua('return vim.g.menu_choice') is None
        key('<Down>', [1])
        key('<Right><Right><Left><Home><End>llhh', [1])
        assert editor.call('nvim_win_get_cursor', window())[1] == 0
        key('<Down>', [3])  # Skip the separator.
        hover(4, [4])
        leave([3])
        hover(2, [])  # A separator cannot retain either row highlight.
        leave([3])
        hover(1, [1])
        key('<Down>', [4])  # Continue the keyboard's own previous selection.
        leave([4])
        key('<Up><Up>', [1])
        key('<Up>', [4])
        key('<Down>', [1])
        editor.call('nvim_input', '<CR>')
        closed('first')

        open_menu()
        check([])
        key('<Up>', [4])
        editor.call('nvim_input', '<CR>')
        closed('last')

        open_menu()
        hover(3, [3])
        leave([])  # No keyboard history in this popup.
        key('<Down><Down>', [3])
        hover(4, [4])
        editor.call('nvim_input', '<CR>')
        closed('last')

        open_menu()
        hover(3, [3])
        screenrow, column = position(3)
        editor.click(screenrow, column + 4)
        closed('second')

        # Real toolbar menus share the same behavior, with no stale selection
        # or cursor restoration from the popup being replaced.
        editor.lua('vim.cmd("redraw!")')
        for name in ('File', 'Debug', 'Terminal', 'Debug'):
            editor.click(0, ''.join(editor.grid[0]).index(' ' + name + ' ') + 2)
            check([])
            key('<Down>', [1])
        editor.call('nvim_input', '<Esc>')
        closed()
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: initially unselected menus, hidden/restored caret, full-row arrows with wrapping and separator skipping, '
              'blocked horizontal movement, single mouse/keyboard highlight, keyboard fallback on pointer exit, '
              'Enter/mouse actions and clean menu switching; unsaved document preserved.')
    finally:
        editor.close()
