from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-sidebar-scroll-') as directory:
    root = Path(directory)
    repo = root / 'project'
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode()
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    source = repo / 'heading.md'
    source.write_text('# ' + 'Long_heading_' * 12 + '\n')
    git('add', '.')
    git('commit', '-m', 'Long commit subject ' + 'description ' * 12)
    editor = Editor(repo, root / 'state')
    try:
        def win(ft):
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do if vim.bo[vim.api.nvim_win_get_buf(w)].filetype==... then return w end end', ft)
        def view(w):
            return editor.lua('return vim.api.nvim_win_call(...,vim.fn.winsaveview)', w)
        def bar(w):
            return editor.lua('local b=require("config.hscroll").bars[...];return b and vim.api.nvim_win_is_valid(b.win)', w)
        editor.wait(lambda: win('aerial'), 'Symbols panel')
        aerial = win('aerial')
        editor.wait(lambda: not bar(aerial), 'No scrollbar for compact No symbols message')
        before = view(aerial)
        p = editor.lua('return vim.api.nvim_win_get_position(...)', aerial)
        for wheel in ['down', 'right', 'left', 'up']:
            for _ in range(4):
                editor.call('nvim_input_mouse', 'wheel', wheel, '', 0, p[0]+3, p[1]+5)
        editor.wait(lambda: view(aerial)['leftcol'] == 0 and view(aerial)['topline'] == 1, 'Content that fits cannot move into blank space')
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(source))
        editor.wait(lambda: bar(aerial), 'Long symbol names get a bottom scrollbar')
        bounds = editor.lua('return {require("config.hscroll").bounds(...)}', aerial)
        assert bounds[0] > 60, bounds
        position = editor.lua('local b=require("config.hscroll").bars[...];local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+vim.api.nvim_win_get_width(b.win)-1}', aerial)
        editor.click(*position)
        editor.wait(lambda: view(aerial)['leftcol'] > 0, 'Symbols scrollbar click moves content')
        editor.lua('require("config.hscroll").set(...,99999)', aerial)
        assert view(aerial)['leftcol'] <= bounds[0]
        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: win('ide_git_history'), 'Commit history panel')
        history = win('ide_git_history')
        editor.wait(lambda: bar(history), 'Long commit messages get a scrollbar')
        editor.wait(lambda: editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing'), 'Sidebar layout settles before clicking commit scrollbar')
        position = editor.lua('local b=require("config.hscroll").bars[...];local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+vim.api.nvim_win_get_width(b.win)-1}', history)
        editor.click(*position)
        editor.wait(lambda: view(history)['leftcol'] > 0, 'Commit scrollbar click moves content')
        # A fixed-height native split can still absorb spare rows when the
        # whole sidebar grows. The scrollbar must remain a single visible row.
        def compact_bar():
            return editor.lua('local b=require("config.hscroll").bars[...];'
                              'if not b or not vim.api.nvim_win_is_valid(b.win) then return false end;'
                              'local v=vim.api.nvim_win_call(b.win,vim.fn.winsaveview);'
                              'return vim.api.nvim_win_get_height(b.win)==1 and v.topline==1 and v.leftcol==0', history)
        for width, height in ((200, 80), (128, 36), (160, 48)):
            editor.call('nvim_ui_try_resize', width, height)
            editor.wait(compact_bar, 'Resize keeps the commit scrollbar one row high and unscrolled')
            editor.wait(lambda: not editor.lua('return require("config.layout").scaling'), 'Resized layout settles')
            assert compact_bar(), 'Restoring proportions must not enlarge the scrollbar'
        editor.lua('vim.api.nvim_set_current_win(require("config.ide").editor_window());vim.cmd("stopinsert")')
        editor.call('nvim_input', 'i')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Insert mode in editor beside commit panel')
        editor.wait(compact_bar, 'Commit scrollbar stays visible in Insert mode')
        editor.call('nvim_input', '<Esc>v')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'v', 'Visual mode in editor beside commit panel')
        editor.wait(compact_bar, 'Commit scrollbar stays visible in Visual mode')
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal mode in editor beside commit panel')
        editor.wait(compact_bar, 'Commit scrollbar stays visible in Normal mode')
        editor.lua('require("neo-tree.command").execute({source="buffers",action="focus"})')
        editor.wait(lambda: not editor.lua('local b=require("config.hscroll").bars[...];return b~=nil', history), 'Switching sidebar source cleans up its scrollbar')
        long_file = repo / ('long_document_name_' * 8 + '.txt')
        long_file.write_text('Short content\n')
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(long_file))
        editor.lua('require("neo-tree.command").execute({source="buffers",action="focus"})')
        tree = win('neo-tree')
        editor.wait(lambda: bar(tree), 'Unshortened document paths get a tree scrollbar')
        position = editor.lua('local b=require("config.hscroll").bars[...];local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+vim.api.nvim_win_get_width(b.win)-1}', tree)
        editor.click(*position)
        editor.wait(lambda: view(tree)['leftcol'] > 0, 'Tree scrollbar click moves document paths')
        print('PASS: compact sidebar content stays fixed; long symbols/commits get working one-row bars across resize and editing modes; scrolling clamps to width; source switches clean up bars', flush=True)
    finally:
        editor.close()
