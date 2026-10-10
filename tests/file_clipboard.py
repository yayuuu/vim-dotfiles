"""Files keeps keyboard ownership; clipboard actions copy files, not editor text."""
from pathlib import Path
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-file-clipboard-') as directory:
    root = Path(directory)
    source, other = root / 'original.txt', root / 'other'
    source.write_bytes(b'Original on disk\n')
    other.mkdir()
    binary = root / 'binary.bin'
    binary.write_bytes(b'\x00\xff\x80\x00Binary\n')
    nested = root / 'folder'
    nested.mkdir()
    (nested / 'child.bin').write_bytes(binary.read_bytes())
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(source))
        buf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', buf, 0, -1, False, ['Unsaved text'])

        def click(path):
            def position():
                return editor.lua('local s=require("config.sidebar").state();if not s or not s.tree then return end;'
                                  'local _,line=s.tree:get_node(...);if not line then return end;'
                                  'local p=vim.fn.screenpos(s.winid,line,1);local x=vim.api.nvim_win_get_position(s.winid);'
                                  'return {p.row-1,x[2]+8}', str(path))
            editor.wait(position, 'Files row: ' + path.name)
            editor.click(*position())
            editor.wait(lambda: editor.lua('return vim.bo.filetype=="neo-tree" and vim.fn.mode()=="n"'), 'Keyboard stays in Files')

        def keys(value):
            editor.call('nvim_input', value)
            time.sleep(.12)
            editor.lua('vim.cmd("redraw!")')

        def copied(path, content):
            editor.wait(path.exists, 'Created ' + path.name)
            assert path.read_bytes() == content
            assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['Unsaved text']
            assert editor.lua('return vim.bo.filetype=="neo-tree"'), 'Paste keeps tree focus'

        editor.lua('require("config.ide").explorer()')
        click(source)
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == buf
        keys('<C-c><C-c>')  # Repeating Copy must not toggle the clipboard off.
        keys('<C-v>')
        copied(root / 'Copy of original.txt', source.read_bytes())
        keys('<C-v>')
        copied(root / 'Copy (2) of original.txt', source.read_bytes())
        click(other)
        keys('<C-v>')
        copied(other / source.name, source.read_bytes())
        # A selected file chooses its parent as the destination; collisions are safe.
        click(other / source.name)
        keys('<C-v>')
        copied(other / 'Copy of original.txt', source.read_bytes())
        assert (other / source.name).read_bytes() == source.read_bytes()

        click(binary)
        keys('<C-c>')
        click(other)
        keys('<C-v>')
        copied(other / binary.name, binary.read_bytes())
        click(nested)
        keys('<C-c>')
        click(other)
        keys('<C-v>')
        copied(other / nested.name / 'child.bin', binary.read_bytes())

        # Delete confirmation is exercised through the UI. Cancel must keep the file.
        copy = root / 'Copy of original.txt'
        click(copy)
        keys('<Del>')
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_get_config(0).relative~=""'), 'Delete confirmation')
        keys('n<CR>')
        assert copy.exists()
        click(copy)
        keys('<Del>')
        editor.wait(lambda: editor.lua('return vim.api.nvim_win_get_config(0).relative~=""'), 'Delete confirmation again')
        keys('y<CR>')
        editor.wait(lambda: not copy.exists(), 'Confirmed deletion')
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['Unsaved text']
        click(source)
        keys('<Del>')
        assert source.exists(), 'Do not discard modified documents during file deletion'
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['Unsaved text']

        # Returning to the editor restores text editing, including native Delete.
        position = editor.lua('local w=require("config.ide").editor_window();local p=vim.fn.screenpos(w,1,1);return {p.row-1,p.col-1}')
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.fn.mode()=="i" and vim.api.nvim_get_current_buf()==...', buf), 'Editor input active')
        editor.call('nvim_win_set_cursor', editor.lua('return vim.api.nvim_get_current_win()'), [1, 0])
        keys('<Del>')
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['nsaved text']
        assert source.exists()
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: file click retains Files focus; repeated Copy/Paste, same/different folder, collisions, binary/folder copies; Delete cancel/confirm; unsaved text preserved and editor Delete still edits text.')
    finally:
        editor.close()
