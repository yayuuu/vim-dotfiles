"""New file always creates a visible empty card and preserves prior documents."""
from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-new-file-') as directory:
    root = Path(directory)
    file = root / 'example.txt'
    file.write_text('Original\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        original = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved original"})')
        created = []
        def visible(buf):
            return editor.lua('local buf=...;for _,h in ipairs(require("config.editor_tabs").hits or {}) do '
                              'if h.id==buf then return true end end;return false', buf)
        for index in range(3):
            if index == 0:
                editor.lua('vim.cmd("stopinsert");require("config.ide").menu("File")')
                def menu_position():
                    editor.lua('vim.cmd("redraw!")')
                    for row, cells in enumerate(editor.grid):
                        text = ''.join(cells)
                        if 'New file' in text:
                            return row, text.index('New file') + 2
                editor.wait(menu_position, 'File menu New file action')
                editor.click(*menu_position())
            else:
                editor.call('nvim_input', '<C-n>')
            current = editor.lua('return vim.api.nvim_get_current_buf()')
            assert current != original and current not in created, 'New file must allocate a new document'
            created.append(current)
            assert editor.lua('return vim.api.nvim_buf_get_name(0)') == ''
            assert editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == ['']
            editor.wait(lambda: visible(current), 'Empty document has a visible card')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'New document starts input')
            assert all(editor.lua('return vim.api.nvim_buf_is_valid(...)', buf) and visible(buf) for buf in created), 'Earlier empty cards remain available'
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', original) == ['Unsaved original']
        assert editor.lua('return vim.bo[...].modified', original)
        editor.call('nvim_input', 'New content')
        editor.wait(lambda: editor.lua('return vim.api.nvim_buf_get_lines(0,0,-1,false)') == ['New content'], 'Typing edits the new document')
        print('PASS: File > New file and Ctrl+N create separate visible empty cards in Insert mode without losing earlier documents.')
    finally:
        editor.close()
