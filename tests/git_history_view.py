from pathlib import Path
import subprocess
import tempfile
import time

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-git-history-view-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode()

    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    file = repo / 'code.txt'
    file.write_text('Original\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    file.write_text('Committed edit\n')
    git('commit', '-am', 'Second commit')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");vim.api.nvim_buf_set_lines(0,0,1,false,{"Unsaved edit"})', str(file))
        main = editor.lua('return require("config.ide").main_editor')
        workspace = editor.lua('return vim.api.nvim_get_current_tabpage()')
        buffer = editor.lua('return vim.api.nvim_get_current_buf()')

        def menu(name, label):
            editor.lua('vim.cmd("stopinsert");require("config.ide").menu(...)', name)

            def location():
                editor.lua('vim.cmd("redraw!")')
                for row, cells in enumerate(editor.grid):
                    text = ''.join(cells)
                    if label in text:
                        return row, text.index(label) + 2

            editor.wait(location, label+' menu item visible')
            editor.click(*location())

        def settled():
            return editor.lua('return not require("config.layout").scaling and not require("config.sidebar").changing')

        for _ in range(2):
            menu('View', 'Project files')
            editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.name=="filesystem"'), 'Project files stays visible')
            menu('Git', 'Project history')
            editor.wait(lambda: editor.lua('local lib=package.loaded["diffview.lib"];local v=lib and lib.get_current_view();return v and v.ready and #v.panel.entries==2'), 'Project history loads in its own view')
            history = editor.lua('return vim.api.nvim_get_current_tabpage()')
            assert history != workspace
            for index in (1, 2, 1):
                editor.lua('local v=require("diffview.lib").get_current_view();v:set_file(v.panel.entries[...].files[1])', index)
                time.sleep(.2)
                assert editor.lua('local v=require("diffview.lib").get_current_view();return v and v.cur_layout:is_valid()'), 'History diff remains valid'
                assert editor.lua('local n=0;for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="DiffviewFileHistory" then n=n+1 end end;return n') == 1
                assert editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do local ft=vim.bo[vim.api.nvim_win_get_buf(w)].filetype;if ft=="neo-tree" or ft=="aerial" or ft=="ide_terminal_list" then return false end end;return true')
                assert editor.lua('return require("config.ide").main_editor') == main
                assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == buffer
            editor.lua('vim.cmd("DiffviewClose")')
            editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_tabpage()') == workspace, 'Closing history returns to workspace')
            menu('View', 'Project files')
            editor.wait(settled, 'Project files settles after history closes')
            assert editor.lua('local s=require("config.sidebar").state();return s and s.name=="filesystem"')
            assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == buffer
            assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', buffer) == ['Unsaved edit']
            assert editor.lua('return #vim.api.nvim_list_tabpages()') == 1
        messages = editor.lua('return vim.fn.execute("messages")')
        editor.lua('require("config.diff").open(...)', str(file))
        terminal_geometry = editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.win);return {left=p[2],width=vim.api.nvim_win_get_width(t.win)+1+vim.api.nvim_win_get_width(t.list_win)}')
        editor.lua('require("config.problems").open()')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win:valid()'), 'Problems replaces terminal below native diff')
        problems_geometry = editor.lua('local w=require("config.problems").view.win.win;return {left=vim.api.nvim_win_get_position(w)[2],width=vim.api.nvim_win_get_width(w)}')
        assert problems_geometry == terminal_geometry, (problems_geometry, terminal_geometry)
        editor.lua('require("config.problems").hide()')
        restored_geometry = editor.lua('local t=require("config.terminals");return {left=vim.api.nvim_win_get_position(t.win)[2],width=vim.api.nvim_win_get_width(t.win)+1+vim.api.nvim_win_get_width(t.list_win)}')
        assert restored_geometry == terminal_geometry, (restored_geometry, terminal_geometry)
        editor.lua('require("config.terminals").show_debug_console(false)')
        editor.wait(lambda: editor.lua('return require("config.terminals").console_active'), 'Select debug console below native diff')
        editor.lua('require("config.problems").open()')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win:valid()'), 'Problems replaces debug console')
        editor.lua('require("config.problems").hide()')
        editor.wait(lambda: editor.lua('local t=require("config.terminals");local d=require("config.diff").active;return t.win and t.list_win and t.console_active and d and vim.api.nvim_win_is_valid(d.left)'), 'Hide restores debug console and native diff')
        console_geometry = editor.lua('local t=require("config.terminals");return {left=vim.api.nvim_win_get_position(t.win)[2],width=vim.api.nvim_win_get_width(t.win)+1+vim.api.nvim_win_get_width(t.list_win)}')
        assert console_geometry == terminal_geometry, (console_geometry, terminal_geometry)
        editor.lua('require("config.terminals").hide();require("config.problems").open()')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win:valid()'), 'Problems spans native diff with hidden terminal')
        assert editor.lua('local p=require("config.problems").view.win.win;local d=require("config.diff").active;return vim.api.nvim_win_get_width(p)==vim.api.nvim_win_get_width(d.header)')
        editor.lua('require("config.problems").hide()')
        assert not editor.lua('return require("config.terminals").win')
        menu('Git', 'Project history')
        editor.wait(lambda: editor.lua('local v=require("diffview.lib").get_current_view();return v and v.ready and #v.panel.entries==2'), 'History opens from native diff')
        editor.lua('local v=require("diffview.lib").get_current_view();v:set_file(v.panel.entries[1].files[1])')
        assert editor.lua('return require("diffview.lib").get_current_view().cur_layout:is_valid()')
        editor.lua('vim.cmd("DiffviewClose")')
        editor.wait(lambda: editor.lua('local d=require("config.diff").active;return d and vim.api.nvim_win_is_valid(d.left) and vim.api.nvim_win_is_valid(d.right)'), 'Native comparison survives history')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Invalid window' not in messages, messages
        print('PASS: Project history and Project files menu clicks preserve workspace, unsaved content and one history panel; native diff survives history; Problems restores full-width terminal/debug console and preserves hidden terminal', flush=True)
    except Exception:
        print(editor.lua('local lib=package.loaded["diffview.lib"];local views={};for _,v in ipairs(lib and lib.views or {}) do '
                         'views[#views+1]={tab=v.tabpage,ready=v.ready,entries=v.panel and #v.panel.entries} end;'
                         'local wins={};for _,w in ipairs(vim.api.nvim_list_wins()) do wins[#wins+1]={win=w,tab=vim.api.nvim_win_get_tabpage(w),'
                         'name=vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(w)),ft=vim.bo[vim.api.nvim_win_get_buf(w)].filetype} end;'
                         'return {current=vim.api.nvim_get_current_tabpage(),views=views,wins=wins,messages=vim.fn.execute("messages")}'), flush=True)
        raise
    finally:
        editor.close()
