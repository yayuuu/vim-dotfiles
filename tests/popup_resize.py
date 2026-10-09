from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
import ui

with tempfile.TemporaryDirectory(prefix='nvim-popup-resize-') as directory:
    root = Path(directory)
    editor = ui.Editor(root, root / 'state')
    try:
        editor.lua('vim.cmd("stopinsert");vim.cmd("Lazy")')
        win = editor.lua('return require("lazy.view").view.win')
        editor.wait(lambda: editor.lua('return require("config.popup_ui").buttons[...]~=nil', win), 'Initial close button')
        # Reproduce repositioning an existing button when its parent changes width.
        editor.lua('local win=...;vim.api.nvim_win_set_config(win,{width=vim.api.nvim_win_get_width(win)-8});require("config.popup_ui").refresh()', win)

        def positioned_button():
            return editor.lua('local win=...;local p=require("config.popup_ui");local b=p.buttons[win];'
                              'if not b or not vim.api.nvim_win_is_valid(b.win) then return false end;'
                              'local c=vim.api.nvim_win_get_config(b.win);'
                              'return not p.scanning and c.relative=="win" and c.win==win and c.row==-1 '
                              'and c.col==vim.api.nvim_win_get_width(win)-3', win)

        for width in (140, 160, 128, 160):
            editor.call('nvim_ui_try_resize', width, 48)
            editor.wait(positioned_button, 'Close button follows resized dialog')
            editor.lua('vim.cmd("redraw!")')
            position = editor.lua('local b=require("config.popup_ui").buttons[...];local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+1}', win)
            assert editor.grid[position[0]][position[1]] == '×', (position, editor.grid[position[0]])
        messages = editor.lua('return vim.fn.execute("messages")')
        assert "Required: 'relative'" not in messages and 'Error executing' not in messages, messages
        editor.click(*position)
        editor.wait(lambda: not editor.lua('return vim.api.nvim_win_is_valid(...)', win), 'Resized dialog closes on click')
        editor.lua('vim.cmd("Lazy")')
        editor.wait(lambda: editor.lua('local p=require("config.popup_ui");local win=require("lazy.view").view.win;return p.buttons[win]~=nil and not p.scanning'), 'Popup refresh continues after reopening')
        print('PASS: repeated dialog resizing keeps a visible clickable close cross, without errors; reopened dialogs get a close button', flush=True)
    finally:
        editor.close()
