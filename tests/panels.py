from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import ui

with tempfile.TemporaryDirectory(prefix='nvim-panels-') as directory:
    root = Path(directory)
    project = root / 'project'
    project.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(project), *args], stderr=subprocess.STDOUT).decode()
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    tracked = project / 'tracked.txt'
    tracked.write_text('Original\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    added = project / 'new[1].txt'
    added.write_text('New first line\nNew second line\n')
    editor = ui.Editor(project, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(tracked))
        main = editor.lua('return require("config.ide").editor_window()')
        codebuf = editor.lua('return vim.api.nvim_get_current_buf()')
        def terminals():
            return editor.lua('local t=require("config.terminals");return {count=#t.items,active=t.active,win=t.win,list=t.list_win,rows=t.rows}')
        def list_click(row, cross=False):
            position = editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.list_win);return {p[1]+...,p[2]+(select(2,...) and vim.api.nvim_win_get_width(t.list_win)-2 or 4)}', row, cross)
            editor.click(*position)
        first = terminals()['active']
        first_job = editor.lua('return require("config.terminals").items[1].job')
        editor.lua('vim.fn.chansend(...,"cd ..\\n")', first_job)
        editor.wait(lambda: str(root) in editor.lua('return vim.wo[require("config.terminals").win].winbar'), 'Terminal title follows cd')
        editor.lua('vim.fn.chansend(...,"sleep 2\\n")', first_job)
        editor.wait(lambda: 'sleep - ' in editor.lua('return vim.wo[require("config.terminals").win].winbar'), 'Terminal title shows foreground program')
        editor.wait(lambda: 'bash - ' in editor.lua('return vim.wo[require("config.terminals").win].winbar'), 'Terminal title returns to shell after command finishes')
        editor.lua('require("config.ide").new_terminal()')
        editor.wait(lambda: terminals()['count'] == 2, 'New terminal creates one session')
        second = terminals()['active']
        assert first != second
        assert editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.win);local l=vim.api.nvim_win_get_position(t.list_win);return p[1]==l[1] and l[2]>p[2] and vim.api.nvim_win_get_width(t.win)>vim.api.nvim_win_get_width(t.list_win)')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == codebuf
        assert editor.lua('local n=0;for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.bo[vim.api.nvim_win_get_buf(w)].buftype=="terminal" then n=n+1 end end;return n') == 1
        list_click(2)
        editor.wait(lambda: terminals()['active'] == first, 'Click selects existing terminal from terminal mode')
        list_click(3, True)
        editor.wait(lambda: terminals()['count'] == 1 and not editor.lua('return vim.api.nvim_buf_is_valid(...)', second), 'Cross closes inactive terminal')
        list_click(1)
        editor.wait(lambda: terminals()['count'] == 2, 'New terminal button creates another terminal')
        editor.lua('require("config.terminals").hide();require("config.ide").terminal()')
        assert terminals()['count'] == 2
        list_click(3, True)
        list_click(2, True)
        editor.wait(lambda: terminals()['count'] == 0, 'Closing last session keeps the New terminal button')
        list_click(1)
        editor.wait(lambda: terminals()['count'] == 1, 'New terminal works after closing the last session')
        item = editor.lua('return require("config.terminals").items[1]')
        editor.lua('vim.fn.chansend(...,"exit\\n")', item['job'])
        editor.wait(lambda: terminals()['count'] == 0, 'Shell exit removes session')
        print('PASS: terminal layout, menu New, switching, close crosses, New button, hide/show, final-session close and shell exit', flush=True)

        def button(win):
            return editor.lua('local b=require("config.popup_ui").buttons[...];if b and vim.api.nvim_win_is_valid(b.win) then local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+1} end', win)
        def close_popup(win, description):
            editor.wait(lambda: button(win), description+' close button')
            editor.click(*button(win))
            editor.wait(lambda: not editor.lua('return vim.api.nvim_win_is_valid(...)', win), description+' closes')
        editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert");vim.cmd("Lazy")', main)
        lazywin = editor.lua('return require("lazy.view").view.win')
        close_popup(lazywin, 'Lazy')
        editor.wait(lambda: not editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="lazy_backdrop" then return true end end;return false'), 'Lazy backdrop removed')
        editor.lua('vim.cmd("Mason")')
        masonwin = editor.lua('return vim.api.nvim_get_current_win()')
        close_popup(masonwin, 'Mason')
        editor.lua('vim.g.test_input_done=false;vim.ui.input({prompt="Test prompt"},function(value) vim.g.test_input_done=true;vim.g.test_input_cancelled=value==nil end)')
        inputwin = editor.lua('return vim.api.nvim_get_current_win()')
        close_popup(inputwin, 'Input')
        editor.wait(lambda: editor.lua('return vim.g.test_input_done and vim.g.test_input_cancelled'), 'Input cross calls cancellation callback')
        editor.lua('Snacks.picker.files({cwd=...})', str(project))
        editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown and p.layout.root.win~=nil'), 'File picker opens')
        pickerwin = editor.lua('return Snacks.picker.get()[1].layout.root.win')
        close_popup(pickerwin, 'File picker')
        editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0'), 'Picker cross closes whole picker')
        editor.call('nvim_input', ':')
        editor.wait(lambda: editor.lua('return vim.fn.getcmdtype()==":"'), 'Command popup opens')
        def command_popup():
            return editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do local c=vim.api.nvim_win_get_config(w);'
                              'if c.relative=="editor" and c.zindex==200 and vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="noice" then return w end end')
        editor.wait(command_popup, 'Noice command popup becomes visible')
        commandwin = command_popup()
        editor.wait(lambda: button(commandwin), 'Command popup close button')
        editor.click(*button(commandwin))
        editor.wait(lambda: editor.lua('return vim.fn.getcmdtype()==""'), 'Command popup cross cancels command entry')
        print('PASS: actual close clicks on Lazy, Mason, input cancellation, entire file picker and command popup', flush=True)

        editor.lua('vim.env.LC_ALL="pl_PL.UTF-8";vim.env.LANGUAGE="pl";require("config.diff").open(...)', str(added))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'New file diff opens under Polish Git locale')
        assert editor.lua('local d=require("config.diff");local e=d.entries[d.active.buf];return vim.api.nvim_buf_get_lines(e.before,0,-1,false)') == ['']
        assert editor.lua('local d=require("config.diff");local e=d.entries[d.active.buf];return vim.api.nvim_buf_get_lines(e.buf,0,-1,false)') == ['New first line', 'New second line']
        assert editor.lua('local d=require("config.diff");return vim.wo[d.active.left].diff and vim.wo[d.active.right].diff')
        git('add', str(added))
        editor.lua('require("config.diff").open(...)', str(added))
        assert editor.lua('local d=require("config.diff");return vim.api.nvim_buf_get_lines(d.entries[d.active.buf].before,0,-1,false)') == ['']
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'istnieje na dysku' not in messages and 'Invalid buffer' not in messages and 'Error executing' not in messages, messages
        print('PASS: untracked and staged files (including literal brackets) compare empty HEAD to full content with Polish Git messages', flush=True)
    finally:
        editor.close()
