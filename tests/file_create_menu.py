"""File creation and blank-space context menus use the actual clicked destination."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-file-create-menu-') as directory:
    root = Path(directory)
    project = root / 'project'
    project.mkdir()
    source = project / 'source.txt'
    source.write_text('Original document\n')
    folder = project / 'folder'
    folder.mkdir()
    child = folder / 'child.txt'
    child.write_text('Child\n')
    editor = Editor(project, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(source))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, -1, False, ['Unsaved document'])

        def position(path=None):
            return editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                              'if not s.tree or not s.winid or not vim.api.nvim_win_is_valid(s.winid) then return end;'
                              'local p=vim.api.nvim_win_get_position(s.winid);local path=...;'
                              'if not path or path==vim.NIL then return {p[1]+vim.api.nvim_win_get_height(s.winid)-2,p[2]+6} end;'
                              'local _,line=s.tree:get_node(path);if not line then return end;'
                              'local screen=vim.fn.screenpos(s.winid,line,1);'
                              'if screen.row>0 then return {screen.row-1,p[2]+6} end', str(path) if path else None)

        def labels():
            return editor.lua('local s=require("menu.state");local b=s.bufids[1];'
                              'if not b or not vim.api.nvim_buf_is_valid(b) then return end;'
                              'local r={};for _,item in ipairs(s.bufs[b].items) do r[#r+1]=item.name end;return r')

        def context(path=None):
            editor.wait(lambda: position(path), 'Visible context target')
            row, col = position(path)
            editor.call('nvim_input_mouse', 'right', 'press', '', 0, row, col)
            editor.call('nvim_input_mouse', 'right', 'release', '', 0, row, col)
            editor.wait(labels, 'Context menu opens')
            return labels()

        def choose(label):
            def location():
                editor.lua('vim.cmd("redraw!")')
                for row, cells in enumerate(editor.grid):
                    text = ''.join(cells)
                    if label in text:
                        return row, text.index(label) + 2
            editor.wait(location, 'Visible menu action ' + label)
            editor.click(*location())

        def create(label, name, destination):
            choose(label)
            finish_create(name, destination)

        def finish_create(name, destination):
            editor.wait(lambda: editor.lua('return vim.bo.filetype=="neo-tree-popup" and vim.fn.mode()=="i"'),
                        'Creation prompt opens without a callback error')
            editor.call('nvim_input', name + '<CR>')
            editor.wait(destination.exists, 'Created ' + str(destination))
            editor.wait(lambda: position(destination), 'Created item appears in Files')
            assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
            assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == document

        # Exercise the reported crash before any tree key initializes state.config.
        assert 'New file' in context(source)
        create('New file', 'beside.txt', project / 'beside.txt')
        context(folder)  # A collapsed directory still receives its new children.
        create('New file', 'inside.txt', folder / 'inside.txt')
        context(child)
        create('New directory', 'nested', folder / 'nested')

        # Blank space must not reuse a selected file/directory, even below EOF.
        for mode in ('normal', 'insert', 'visual', 'select', 'terminal'):
            editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(source))
            if mode == 'insert':
                editor.lua('vim.cmd("startinsert")')
            elif mode in ('visual', 'select'):
                editor.lua('vim.api.nvim_feedkeys(vim.keycode(...),"nx",false)', 'v' if mode == 'visual' else 'v<C-g>')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == ('v' if mode == 'visual' else 's'), mode)
            elif mode == 'terminal':
                editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
            menu = context()
            assert all(label in menu for label in ('New file', 'New directory', 'Paste', 'Terminal', 'Repository')), menu
            assert not any(label in menu for label in ('Open', 'Rename', 'Copy', 'Delete...')), menu
            create('New file', mode + '.txt', project / (mode + '.txt'))
            assert not (folder / (mode + '.txt')).exists()

        context()
        create('New directory', 'root-directory', project / 'root-directory')
        context(folder)
        assert 'Copy' in labels()
        assert 'Copy' not in context(), 'Right-click can replace an existing file menu with a blank-space menu'
        editor.lua('require("config.ide").close_menu()')
        context(child)
        choose('Copy')
        editor.wait(lambda: not labels(), 'Copy closes the menu')
        assert editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                          'return s.clipboard[select(1,...)]~=nil', str(child)), 'Copy uses the right-clicked file'
        context()
        choose('Paste')
        try:
            editor.wait((project / 'child.txt').exists, 'Blank-space Paste targets the root')
        except AssertionError:
            print(editor.lua('local s=require("neo-tree.sources.manager").get_state("filesystem");'
                             'return {path=s.path,clipboard=vim.inspect(s.clipboard),messages=vim.fn.execute("messages"),'
                             'mode=vim.fn.mode(),mouse=vim.fn.getmousepos()}'))
            print('Created paths:', [str(p.relative_to(project)) for p in project.rglob('*')])
            raise
        assert (project / 'child.txt').read_bytes() == child.read_bytes()

        # Cancel and existing names cannot modify files or the unsaved document.
        context()
        choose('New file')
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="neo-tree-popup"'), 'Cancel prompt')
        editor.call('nvim_input', 'canceled.txt<Esc>')
        editor.wait(lambda: editor.lua('return vim.bo.filetype') != 'neo-tree-popup', 'Prompt closes on cancel')
        assert not (project / 'canceled.txt').exists()
        context(source)
        choose('New file')
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="neo-tree-popup" and vim.fn.mode()=="i"'), 'Collision prompt')
        editor.call('nvim_input', source.name + '<CR>')
        editor.wait(lambda: editor.lua('return vim.bo.filetype') != 'neo-tree-popup', 'Collision prompt closes')
        assert source.read_text() == 'Original document\n'
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved document']
        # Native tree keys share the same destination-aware creation actions.
        context(folder)
        editor.lua('require("config.ide").close_menu();vim.cmd("stopinsert")')
        editor.call('nvim_input', 'a')
        finish_create('keyboard.txt', folder / 'keyboard.txt')
        context(folder)
        editor.lua('require("config.ide").close_menu();vim.cmd("stopinsert")')
        editor.call('nvim_input', 'A')
        finish_create('keyboard-directory', folder / 'keyboard-directory')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: creation from file/directory/blank-space menus; root destination below EOF; Normal/Insert/Visual/Select/Terminal; root Paste; cancel/collisions; unsaved document preserved.')
    finally:
        editor.close()
