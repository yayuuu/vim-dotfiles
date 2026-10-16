"""Repository opens a resizable LazyGit popup with a close button, preserving panels."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-repository-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    source = root / 'sample.txt'
    source.write_text('Saved text\n')
    (root / '.git/info/exclude').write_text('state/\n')
    subprocess.run(['git', '-C', str(root), 'add', '--', source.name], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Initial'], check=True)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('Snacks.config.lazygit=vim.tbl_deep_extend("force",Snacks.config.lazygit or {},'
                   '{config={disableStartupPopups=true}})')
        editor.lua('require("config.ide").open_file(...)', str(source))
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.call('nvim_buf_set_lines', document, 0, -1, False, ['Unsaved text'])

        def repository_menu():
            editor.lua('vim.cmd("redraw!")')
            editor.click(0, ''.join(editor.grid[0]).index(' Git ') + 2)

            def action_position():
                editor.lua('vim.cmd("redraw!")')
                for row, cells in enumerate(editor.grid):
                    text = ''.join(cells)
                    if 'Repository' in text:
                        return row, text.index('Repository') + 2
            editor.wait(action_position, 'Git > Repository appears')
            editor.click(*action_position())

        editor.lua('RepositoryTest={executable=vim.fn.executable,notify=vim.notify,messages={}};'
                   'vim.fn.executable=function(cmd) if cmd=="lazygit" then return 0 end;'
                   'return RepositoryTest.executable(cmd) end;'
                   'vim.notify=function(msg,level) table.insert(RepositoryTest.messages,{msg,level}) end')
        repository_menu()
        editor.wait(lambda: editor.lua('return #RepositoryTest.messages') == 1, 'Missing executable hint')
        editor.call('nvim_input', '<M-g>')
        editor.wait(lambda: editor.lua('return #RepositoryTest.messages') == 2, 'Shortcut uses the same guard')
        messages = editor.lua('return RepositoryTest.messages')
        assert all('Install lazygit' in msg and 'Alt+R' in msg and level == 3 for msg, level in messages), messages
        assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved text']
        editor.lua('vim.fn.executable=RepositoryTest.executable;vim.notify=RepositoryTest.notify')

        if shutil.which('lazygit'):
            editor.lua('RepositoryTest.errors={};RepositoryTest.snacks_error=Snacks.notify.error;'
                       'Snacks.notify.error=function(msg,opts) table.insert(RepositoryTest.errors,msg);'
                       'return RepositoryTest.snacks_error(msg,opts) end')
            def lazygit_window():
                return editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do '
                                  'local b=vim.api.nvim_win_get_buf(w);'
                                  'if vim.api.nvim_buf_get_name(b):find("lazygit",1,true) and vim.bo[b].buftype=="terminal" '
                                  'then return w end end')

            def layout():
                return editor.lua('local r={};for _,w in ipairs(vim.api.nvim_list_wins()) do '
                                  'if vim.api.nvim_win_get_config(w).relative=="" then '
                                  'r[tostring(w)]={buf=vim.api.nvim_win_get_buf(w),'
                                  'width=vim.api.nvim_win_get_width(w),height=vim.api.nvim_win_get_height(w),'
                                  'pos=vim.api.nvim_win_get_position(w)} end end;return r')

            def close_button(win):
                return editor.lua('local b=require("config.popup_ui").buttons[...];'
                                  'if b and vim.api.nvim_win_is_valid(b.win) then '
                                  'local p=vim.api.nvim_win_get_position(b.win);return {p[1],p[2]+1} end', win)

            terminal = editor.lua('local t=require("config.terminals");if not t.active then t.new() end;'
                                 'return {buf=t.active,job=vim.b[t.active].terminal_job_id}')
            for bottom in ('terminal', 'hidden', 'problems'):
                if bottom == 'hidden':
                    editor.lua('require("config.terminals").hide()')
                elif bottom == 'problems':
                    editor.lua('require("config.problems").open()')
                    editor.wait(lambda: editor.lua('local p=require("config.problems");'
                                                  'return p.view and p.view.win and p.view.win.win '
                                                  'and vim.api.nvim_win_is_valid(p.view.win.win) and not p.suspended'),
                                'Problems appears')
                before = layout()
                if bottom == 'terminal':
                    repository_menu()
                else:
                    editor.call('nvim_input', '<M-g>')
                editor.wait(lazygit_window, 'Actual LazyGit popup opens')
                win = lazygit_window()
                config = editor.call('nvim_win_get_config', win)
                assert config['relative'] == 'editor', config
                assert config['width'] >= 120 and config['height'] >= 34, config
                assert config.get('border'), config
                assert layout() == before, 'Opening the popup preserves all native panels'
                job = editor.lua('return vim.b[vim.api.nvim_win_get_buf(...)].terminal_job_id', win)
                assert editor.lua('return vim.fn.jobwait({ ... },0)[1]', job) == -1, 'LazyGit stays running'
                editor.wait(lambda: close_button(win), 'Popup close button appears')
                if bottom == 'terminal':
                    editor.call('nvim_ui_try_resize', 100, 32)
                    editor.wait(lambda: editor.call('nvim_win_get_config', win)['width'] < config['width'],
                                'Popup adapts to smaller editor')
                    small = editor.call('nvim_win_get_config', win)
                    assert small['width'] >= 75 and small['height'] >= 22, small
                    editor.call('nvim_ui_try_resize', 160, 48)
                    editor.wait(lambda: editor.call('nvim_win_get_config', win)['width'] == config['width'],
                                'Popup expands again')
                    editor.wait(lambda: close_button(win)[1] > 100, 'Close button follows popup resizing')
                before_close = layout()
                # Browse panes without performing a Git operation.
                editor.lua('vim.fn.chansend(...,"12345")', job)
                # Mouse hit testing needs the new float to have been drawn.
                editor.lua('vim.cmd("redraw!")')
                editor.click(*close_button(win))
                editor.wait(lambda: not lazygit_window(), 'Clicking close removes the LazyGit popup: ' + bottom)
                time.sleep(.2)
                assert editor.lua('return RepositoryTest.errors') == [], 'Closing Repository is not a terminal failure'
                editor.wait(lambda: editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do '
                                              'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="snacks_win_backdrop" '
                                              'then return false end end;return true'), 'Popup backdrop removed')
                assert layout() == before_close, 'Closing the popup preserves all native panels'
                assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved text']
                assert editor.lua('return vim.bo[...].modified', document)
                assert source.read_text() == 'Saved text\n'
                assert editor.lua('return vim.api.nvim_buf_is_valid(...)', terminal['buf'])
                assert editor.lua('return vim.fn.jobwait({...},0)[1]', terminal['job']) == -1

            # Exercise LazyGit's real remote edit command, which briefly creates
            # a native tab that document routing moves into the main editor.
            target = root / "edit space ' quote Ω.lua"
            target.write_text('local value = 1\n' * 120)
            editor.lua('vim.v.errmsg="";RepositoryTest.tabs={};'
                       'vim.api.nvim_create_autocmd("TabEnter",{callback=function() '
                       'table.insert(RepositoryTest.tabs,vim.api.nvim_get_current_tabpage()) end})')
            for attempt in range(2):
                before = layout()
                tabs = editor.call('nvim_list_tabpages')
                editor.lua('require("config.ide").repository()')
                editor.wait(lazygit_window, 'Repository opens for editing')
                win = lazygit_window()
                job = editor.lua('return vim.b[vim.api.nvim_win_get_buf(...)].terminal_job_id', win)
                editor.wait(lambda: editor.lua('return table.concat(vim.api.nvim_buf_get_lines('
                                              'vim.api.nvim_win_get_buf(...),0,-1,false),"\\n")', win).find('edit space') >= 0,
                            'LazyGit lists the selected file')
                editor.lua('vim.cmd("startinsert")')
                editor.lua('vim.fn.chansend(...,"e")', job)
                editor.wait(lambda: editor.lua('return vim.api.nvim_buf_get_name('
                                              'vim.api.nvim_win_get_buf(require("config.ide").editor_window()))') == str(target),
                            'e opens selected file in the main editor')
                editor.wait(lambda: editor.call('nvim_list_tabpages') == tabs and not lazygit_window(),
                            'Temporary remote-edit tab and popup close')
                assert editor.lua('return vim.api.nvim_get_current_win()==require("config.ide").editor_window()')
                closed = editor.lua('return vim.tbl_filter(function(t)return not vim.api.nvim_tabpage_is_valid(t) end,'
                                    'RepositoryTest.tabs)')
                assert closed, 'Remote editing visits a temporary tab that document routing closes'
                for tab in closed:
                    # A late minimap refresh for that actual tab must be harmless,
                    # regardless of the timing of its original scheduled callback.
                    editor.lua('require("neominimap.window.float.internal").refresh_minimaps_in_tab(...)', tab)
                editor.wait(lambda: editor.lua('local w=require("config.ide").editor_window();'
                                              'local m=require("neominimap.window.float.window_map").get_minimap_winid(w);'
                                              'return m and vim.api.nvim_win_is_valid(m)'), 'Minimap follows opened file')
                # Let the queued TabEnter/minimap callbacks run before checking errors.
                time.sleep(.2)
                failures = editor.lua('return {messages=vim.fn.execute("messages"),'
                                      'errmsg=vim.v.errmsg}')
                assert 'Invalid tabpage' not in failures['errmsg'] and 'neominimap/util.lua' not in failures['errmsg'], failures
                assert 'Invalid tabpage' not in failures['messages'] and 'neominimap/util.lua' not in failures['messages'], failures
                assert set(layout()) == set(before), 'Editing does not add or remove native panels'
                assert editor.call('nvim_buf_get_lines', document, 0, -1, False) == ['Unsaved text']
                assert editor.lua('return vim.fn.jobwait({...},0)[1]', terminal['job']) == -1
                buf = editor.lua('return vim.api.nvim_get_current_buf()')
                if attempt == 0:
                    editor.call('nvim_buf_set_lines', buf, 0, 1, False, ['local value = 42 -- unsaved'])
                else:
                    assert editor.call('nvim_buf_get_lines', buf, 0, 1, False) == ['local value = 42 -- unsaved']
            errors = editor.lua('return vim.fn.execute("messages")')
            assert 'E475' not in errors and 'E21:' not in errors and 'Error executing' not in errors, errors
            assert editor.lua('return RepositoryTest.errors') == [], 'Remote editing also closes without failure notifications'

            # An unexpected process termination must still be reported, with
            # the terminal retained for inspection, rather than hidden globally.
            editor.lua('require("config.ide").repository()')
            editor.wait(lazygit_window, 'Repository reopens for process failure test')
            win = lazygit_window()
            job = editor.lua('return vim.b[vim.api.nvim_win_get_buf(...)].terminal_job_id', win)
            editor.wait(lambda: editor.lua('return vim.fn.jobwait({...},0)[1]', job) == -1, 'LazyGit process starts')
            editor.lua('vim.fn.jobstop(...)', job)
            editor.wait(lambda: editor.lua('return #RepositoryTest.errors') == 1, 'Unexpected process failure is reported')
            assert editor.call('nvim_win_is_valid', win), 'Failed terminal remains available for inspection'
            editor.lua('vim.cmd("redraw!")')
            editor.wait(lambda: close_button(win), 'Failed terminal retains close button')
            editor.click(*close_button(win))
            editor.wait(lambda: not lazygit_window(), 'Failed terminal can be closed')
            assert editor.lua('return #RepositoryTest.errors') == 1, 'Closing does not report the same failure again'
            editor.lua('Snacks.notify.error=RepositoryTest.snacks_error')
            print('PASS: large LazyGit popup, resizing, actual close clicks, reopening via Alt+G; '
                  'terminal/hidden/Problems layouts, running terminal and unsaved text preserved')
            print('PASS: actual LazyGit e opens/reopens a quoted Unicode file in the main editor; '
                  'minimap, tabs, unsaved text and running terminal preserved')
            print('PASS: browsing then closing Repository does not report an error; unexpected process failures remain visible')
        else:
            print('SKIP: actual LazyGit launch (executable unavailable)')
        print('PASS: missing LazyGit shows a helpful message through Git > Repository and Alt+G')
    finally:
        editor.lua('for _,t in ipairs(Snacks.terminal.list()) do t:close() end')
        editor.close()
