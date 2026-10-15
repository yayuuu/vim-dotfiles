"""Find's Replace button, singleton lifecycle, editable inputs and active file."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-search-replace-') as directory:
    root = Path(directory)
    first, second, notes = root / 'first.txt', root / 'second file.txt', root / 'notes.txt'
    first.write_text('needle first\nneedle again\n')
    second.write_text('needle second\n')
    notes.write_text('original notes\n')
    for args in [('init', '-b', 'main'), ('config', 'user.name', 'UI Test'),
                 ('config', 'user.email', 'ui@example.invalid'),
                 ('add', 'first.txt', 'second file.txt', 'notes.txt'), ('commit', '-m', 'Baseline')]:
        subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert");'
                   'vim.api.nvim_buf_set_lines(0,0,-1,false,{"Unsaved notes"})', str(notes))
        editor.lua('require("config.ide").open_file(...)', str(first))

        def inst(code):
            return editor.lua('local g=require("grug-far");local i=g.has_instance("desktop-replace") and g.get_instance("desktop-replace") or nil;' + code)

        def values():
            return inst('return require("grug-far.inputs").getValues(i._context,i:get_buf())')

        def click_button(win):
            editor.lua('vim.cmd("redraw!")')
            position = editor.lua('return vim.fn.screenpos(...,1,2)', win)
            editor.click(position['row'] - 1, position['col'] - 1)

        editor.call('nvim_input', '<C-f>')
        editor.wait(lambda: editor.lua('return require("config.search").find_button ~= nil'), 'Find has a Replace button')
        editor.call('nvim_input', 'needle')
        editor.wait(lambda: editor.lua('return require("config.search").find_input:text()') == 'needle', 'Find accepts text')
        # Resize Find itself, including the parent-relative Replace button.
        editor.lua('vim.v.errmsg=""')
        for width in (120, 80, 160):
            editor.call('nvim_ui_try_resize', width, 48)
            editor.lua('vim.cmd("redraw!")')
            error = editor.lua('return vim.v.errmsg')
            assert error == '', error
            editor.wait(lambda: editor.lua('local s=require("config.search");local c=vim.api.nvim_win_get_config(s.find_button);'
                                          'return c.relative=="win" and c.win==s.find_input.win and c.row==-1 '
                                          'and c.col==vim.api.nvim_win_get_width(s.find_input.win)'), 'Find button follows resizing')
            assert editor.lua('return require("config.search").find_input:text()') == 'needle'
        find_button = editor.lua('return require("config.search").find_button')
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false)', find_button) == [' ⇄ ']
        click_button(find_button)
        editor.wait(lambda: editor.lua('local s=require("config.search");return s.win and vim.api.nvim_win_is_valid(s.win)'), 'Replace opens from the arrow button')
        editor.wait(lambda: values()['search'] == 'needle', 'Replace receives the Find text')
        assert values()['paths'] == str(first)
        assert not editor.lua('return require("config.search").find_button ~= nil'), 'Find button is removed with Find'
        panel = editor.lua('return require("config.search").win')
        panel_buf = inst('return i:get_buf()')
        assert editor.lua('local w=require("config.search").win;local e=require("config.ide").editor_window();'
                          'return vim.api.nvim_win_get_width(w)<=78 and vim.api.nvim_win_get_width(w)<vim.api.nvim_win_get_width(e) '
                          'and vim.api.nvim_win_get_height(w)<=22')
        assert editor.lua('local w=require("config.search").win;local e=require("config.ide").editor_window();'
                          'local p=vim.api.nvim_win_get_position(e);local c=vim.api.nvim_win_get_config(w);'
                          'return c.row==p[1]+2 and c.col==p[2]+vim.api.nvim_win_get_width(e)-c.width-2'), 'Replace sits at the upper right'

        for _ in range(3):
            editor.call('nvim_input', '<C-h>')
            editor.lua('vim.cmd("redraw!")')
            assert editor.lua('return require("config.search").win') == panel
            assert inst('return i:get_buf()') == panel_buf
        assert editor.lua('local n=0;for _,w in ipairs(vim.api.nvim_list_wins()) do '
                          'if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="grug-far" then n=n+1 end end;return n') == 1

        # Empty fields contain only virtual placeholders. Click well past EOL.
        inst('i:update_input_values({search="",replacement="",filesFilter="",flags=""},false)')
        editor.wait(lambda: values()['search'] == '', 'Fields are empty before clicking')
        for name, text in [('search', 'needle'), ('replacement', 'changed'), ('filesFilter', '*.txt'), ('flags', '--fixed-strings'), ('paths', None)]:
            editor.lua('vim.cmd("stopinsert")')
            position = editor.lua(
                'local name=...;local i=require("grug-far").get_instance("desktop-replace");'
                'local row=vim.api.nvim_buf_get_extmark_by_id(i:get_buf(),i._context.namespace,i._context.extmarkIds[name],{})[1];'
                'return vim.fn.screenpos(vim.fn.bufwinid(i:get_buf()),row+1,1)', name)
            editor.click(position['row'] - 1, position['col'] + 12)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', name + ' click enters Insert mode')
            if text:
                editor.call('nvim_input', text)
                editor.wait(lambda: values()[name] == text, name + ' accepts typed text')

        # Switch through the actual document strip while the panel stays open.
        editor.lua('require("config.ide").open_file(...)', str(second))
        editor.wait(lambda: values()['paths'] == str(second).replace(' ', r'\ '), 'Replace follows second file')
        assert values()['search'] == 'needle' and values()['replacement'] == 'changed'
        editor.wait(lambda: editor.lua('return require("config.editor_tabs").hits ~= nil'), 'Tabs are rendered')
        tab = editor.lua('local t=require("config.editor_tabs");local b=vim.fn.bufnr(...);'
                         'for _,hit in ipairs(t.hits) do if hit.id==b and not hit.close then '
                         'local p=vim.api.nvim_win_get_position(t.win);return {p[1],p[2]+hit.first} end end', str(first))
        assert tab, 'First document has a clickable tab'
        editor.click(*tab)
        editor.wait(lambda: values()['paths'] == str(first), 'Tab click updates Replace target')
        editor.lua('require("config.ide").open_file(...)', str(second))
        editor.wait(lambda: values()['paths'] == str(second).replace(' ', r'\ '), 'Target follows the file with spaces')
        inst('i:replace()')
        editor.wait(lambda: second.read_text() == 'changed second\n', 'Replace modifies the selected file')
        assert first.read_text() == 'needle first\nneedle again\n'
        assert editor.lua('return vim.api.nvim_buf_get_lines(vim.fn.bufnr(...),0,-1,false)', str(notes)) == ['Unsaved notes']

        editor.lua('require("config.diff").open(...)', str(first))
        editor.wait(lambda: values()['paths'] == str(first), 'Replace follows the real path of the editable diff')
        assert inst('return i:get_buf()') == panel_buf
        assert values()['search'] == 'needle' and values()['replacement'] == 'changed'
        editor.lua('require("config.ide").open_file(...)', str(second))
        editor.wait(lambda: values()['paths'] == str(second).replace(' ', r'\ '), 'Replace follows the ordinary tab after leaving a diff')

        for width in (140, 160):
            editor.call('nvim_ui_try_resize', width, 48)
            editor.wait(lambda: editor.lua('local p=require("config.popup_ui");local s=require("config.search");'
                                          'local b=p.buttons[s.win];return b and vim.api.nvim_win_is_valid(b.win)'), 'Replace keeps its close button after resize')
        editor.lua('Snacks.notifier.hide();require("noice").cmd("dismiss")')
        close = editor.lua('return require("config.popup_ui").buttons[require("config.search").win].win')
        click_button(close)
        editor.wait(lambda: not editor.lua('return vim.api.nvim_win_is_valid(...)', panel), 'Cross closes Replace')
        editor.call('nvim_input', '<C-h>')
        editor.wait(lambda: inst('return i ~= nil and i:is_open()'), 'Ctrl+H reopens Replace after closing')
        editor.lua('require("config.search").close();require("config.ide").find()')
        editor.wait(lambda: editor.lua('return require("config.search").find_input ~= nil'), 'Find reopens')
        editor.call('nvim_input', 'second<CR>')
        editor.wait(lambda: editor.lua('return vim.fn.getreg("/")') == r'\Vsecond', 'Ordinary Find confirmation still searches')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Find-to-Replace arrow, shared Ctrl+H singleton, clickable empty inputs, active tab/file tracking, '
              'scoped replacement, preserved unsaved notes, resizing, cross close/reopen and ordinary Find.')
    except Exception:
        print(editor.lua('local s=require("config.search");return vim.inspect({win=s.win,instance=require("grug-far").has_instance("desktop-replace"),'
                         'popup=require("config.popup_ui").buttons[s.win],owner=require("config.popup_ui").owners[s.win]})'))
        print(editor.lua('local m=vim.fn.getmousepos();return vim.inspect({mouse=m,input=require("config.search").input_at_mouse(m),'
                         'row=require("config.panel_mouse").row(m),capture=require("config.mouse_capture").owner})'))
        print(editor.lua('return vim.fn.execute("messages")'))
        print('\n'.join(''.join(row) for row in editor.grid))
        raise
    finally:
        editor.close()
