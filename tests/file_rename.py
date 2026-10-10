"""F2 renames files/folders without LSP symbol support or losing edited buffers."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-file-rename-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    file = root / 'old [name].txt'
    file.write_text('Disk content\n')
    existing = root / 'existing.txt'
    existing.write_text('Keep this file\n')
    folder = root / 'folder'
    folder.mkdir()
    child = folder / 'child.txt'
    child.write_text('Child content\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(file))
        buf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', buf, 0, -1, False, ['Unsaved text'])

        def f2(name=None, cancel=False):
            editor.call('nvim_input', '<F2>')
            editor.wait(lambda: editor.lua('return vim.bo.filetype=="snacks_input"'), 'F2 opens rename input')
            if cancel:
                editor.lua('require("config.popup_ui").close(vim.api.nvim_get_current_win())')
            else:
                editor.lua('vim.api.nvim_buf_set_lines(0,0,-1,false,{...})', name)
                editor.call('nvim_input', '<CR>')
            editor.wait(lambda: editor.lua('return vim.bo.filetype~="snacks_input"'), 'Rename input closes')

        f2(cancel=True)
        assert file.exists()
        assert editor.call('nvim_buf_get_name', buf) == str(file)
        f2(existing.name)
        assert file.read_text() == 'Disk content\n'
        assert existing.read_text() == 'Keep this file\n'
        renamed = root / 'new [name].txt'
        f2(renamed.name)
        editor.wait(lambda: renamed.exists() and not file.exists(), 'Rename moves the file')
        assert editor.call('nvim_buf_get_name', buf) == str(renamed)
        assert editor.call('nvim_buf_get_lines', buf, 0, -1, False) == ['Unsaved text']
        assert editor.lua('return vim.bo[...].modified', buf)
        assert renamed.read_text() == 'Disk content\n', 'Rename must not silently save edits'
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                                      'return s.tree and s.tree:get_node(...)~=nil', str(renamed)), 'Files tree refreshes')

        # Rename from an editable diff and then save through its existing proxy.
        editor.lua('require("config.diff").open(...);vim.cmd("stopinsert")', str(renamed))
        proxy = editor.lua('return require("config.diff").active.buf')
        final = root / 'final.txt'
        f2(final.name)
        editor.wait(lambda: final.exists(), 'F2 renames the diff file')
        assert editor.lua('return require("config.diff").paths[...]', str(final)) == proxy
        assert editor.lua('return require("config.diff").paths[...]', str(renamed)) is None
        assert editor.call('nvim_buf_get_name', buf) == str(final)
        assert editor.lua('return vim.b[...].ide_diff_file', proxy) == str(final)
        editor.lua('require("config.ide").save_buffer(...)', proxy)
        editor.wait(lambda: final.read_text() == 'Unsaved text\n', 'Saving diff writes renamed file')
        assert not renamed.exists()

        # A folder selected in Files retargets its open children in place.
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(child))
        childbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', childbuf, 0, -1, False, ['Unsaved child'])
        editor.lua('require("config.ide").explorer()')
        editor.wait(lambda: editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                                      'return s.tree and s.tree:get_node(...)~=nil', str(folder)), 'Folder in Files')
        editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                   'local _,line=s.tree:get_node(...);vim.api.nvim_set_current_win(s.winid);'
                   'vim.api.nvim_win_set_cursor(s.winid,{line,0});vim.cmd("stopinsert")', str(folder))
        f2('renamed-folder')
        target = root / 'renamed-folder' / child.name
        editor.wait(target.exists, 'Folder rename moves its contents')
        assert editor.call('nvim_buf_get_name', childbuf) == str(target)
        assert editor.call('nvim_buf_get_lines', childbuf, 0, -1, False) == ['Unsaved child']
        assert editor.lua('return vim.bo[...].modified', childbuf)
        assert target.read_text() == 'Child content\n'
        editor.call('nvim_input', '<C-s>')
        editor.wait(lambda: target.read_text() == 'Unsaved child\n', 'Ctrl+S saves a renamed child without confirmation')
        assert not editor.lua('return vim.bo[...].modified', childbuf)
        assert not editor.lua('return vim.o.writeany'), 'Save restores native write protection'

        # A disk change made after rename must not be overwritten by the first save.
        protected = root / 'protected.txt'
        editor.lua('require("config.rename").move(...)', str(target), str(protected))
        protected.write_text('External edit\n')
        editor.call('nvim_buf_set_lines', childbuf, 0, -1, False, ['Still unsaved'])
        editor.lua('require("config.ide").save_buffer(...,false,function(ok) vim.g.rename_save_ok=ok end)', childbuf)
        assert editor.lua('return vim.g.rename_save_ok') is False
        assert protected.read_text() == 'External edit\n'
        assert editor.lua('return vim.bo[...].modified', childbuf)
        assert not editor.lua('return vim.o.writeany')
        assert 'no matching language servers with rename capability' not in editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: F2 rename/cancel/collision, Files refresh, unsaved buffers, editable diff/save, and selected folder children; no LSP symbol requirement.')
    finally:
        editor.close()
