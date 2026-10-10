"""Blank panel space never activates the last item clamped by Neovim."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-panel-empty-click-') as directory:
    root = Path(directory)
    source = root / 'source.lua'
    source.write_text('local function first() return 1 end\nlocal function second() return 2 end\n')
    def git(*args):
        subprocess.run(['git', '-C', str(root), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    git('add', '.')
    git('commit', '-m', 'First commit')
    editor = Editor(root, root / 'state')
    try:
        def window(ft):
            return editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do if vim.bo[vim.api.nvim_win_get_buf(w)].filetype==... then return w end end', ft)
        def blank(win):
            editor.wait(lambda: editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing'), 'Layout settled')
            p = editor.call('nvim_win_get_position', win)
            height = editor.call('nvim_win_get_height', win)
            editor.click(p[0]+height-2, p[1]+5)
            assert not editor.lua('return require("config.mouse_capture").active()'), 'Blank click releases capture'
        editor.lua('require("config.ide").open_file(...);require("config.ide").explorer()', str(source))
        tree = window('neo-tree')
        editor.wait(lambda: window('aerial') and editor.lua('return vim.b[vim.api.nvim_win_get_buf(...)].source_buffer~=nil', window('aerial')), 'Symbols loaded')
        main = editor.lua('return require("config.ide").editor_window()')
        buf = editor.call('nvim_win_get_buf', main)
        editor.call('nvim_win_set_cursor', main, [1, 0])
        blank(tree)
        blank(window('aerial'))
        assert editor.call('nvim_win_get_buf', main) == buf
        assert editor.call('nvim_win_get_cursor', main)[0] == 1, 'Blank Symbols must not jump to last function'

        t = editor.lua('local t=require("config.terminals");return {win=t.win,list=t.list_win,active=t.active,serial=t.serial}')
        blank(t['list'])
        assert editor.lua('local t=require("config.terminals");return not t.console_active and t.active==... and t.serial==select(2,...)', t['active'], t['serial']), 'Blank sessions must not select Debug console or create a terminal'
        # Top menus close on otherwise inactive clicks, without selecting the
        # terminal list's final row; switching menu-bar buttons still works.
        editor.click(0, 3)
        editor.wait(lambda: window('NvMenu'), 'File dropdown opens')
        editor.click(0, 9)
        editor.wait(lambda: editor.lua('local s=require("menu.state");return s.bufids[1] and s.bufs[s.bufids[1]].items[1].name=="Undo"'), 'Menu bar switches to Edit')
        editor.click(0, 9)
        editor.wait(lambda: not window('NvMenu'), 'Clicking Edit again closes it')
        editor.click(0, 3)
        editor.wait(lambda: window('NvMenu'), 'File menu reopens after toggle')
        blank(t['list'])
        try:
            editor.wait(lambda: not window('NvMenu'), 'Blank click outside dropdown closes it')
        except AssertionError:
            print(editor.lua('return {mode=vim.fn.mode(),mouse=vim.fn.getmousepos(),menus=require("menu.state").bufids,capture=require("config.mouse_capture").active(),messages=vim.fn.execute("messages")}'))
            raise
        assert editor.lua('return not require("config.terminals").console_active')
        # The empty editor body, Symbols body, and unused menu-bar area also
        # dismiss the dropdown without moving the source document's cursor.
        for target in (main, window('aerial'), None):
            editor.click(0, 3)
            editor.wait(lambda: window('NvMenu'), 'File dropdown reopens')
            if target is None:
                editor.click(0, 150)
            else:
                blank(target)
            editor.wait(lambda: not window('NvMenu'), 'Outside blank space dismisses dropdown')
            assert editor.call('nvim_win_get_cursor', main)[0] == 1

        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: window('ide_git_history') and editor.lua('return require("config.sidebar").commits and next(require("config.sidebar").commits)~=nil'), 'Commits loaded')
        blank(window('ide_git_history'))
        assert editor.lua('return #Snacks.picker.get()') == 0, 'Blank commits must not open preview'
        blank(window('neo-tree'))
        assert not editor.lua('return require("config.diff").active'), 'Blank Git Status must not open diff'

        editor.lua('require("config.debugger").show()')
        editor.wait(lambda: window('dapui_watches'), 'Debugger panels')
        for ft in ('dapui_scopes', 'dapui_breakpoints', 'dapui_stacks', 'dapui_watches'):
            blank(window(ft))
        assert editor.call('nvim_win_get_buf', main) == buf
        assert editor.lua('return vim.fn.mode()') == 'n', 'Blank Watches must not start input'

        editor.lua('Snacks.picker({items={{text="One"},{text="Two"}},format="text",preview=false})')
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown and p.list:count()==2'), 'Picker ready')
        before = editor.lua('return Snacks.picker.get()[1].list.cursor')
        blank(editor.lua('return Snacks.picker.get()[1].list.win.win'))
        assert editor.lua('return Snacks.picker.get()[1].list.cursor') == before, 'Blank picker must not select last item'
        editor.lua('Snacks.picker.get()[1]:close()')
        print('PASS: blank Files, Symbols, terminal sessions, commits, Git Status, Debug panes and picker lists do not activate the last item; outside clicks close menus; menu switching works; captures release; editor is preserved.')
    finally:
        editor.close()
