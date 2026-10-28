"""DAP row-wide mouse/keyboard actions, persistent Watches input and terminal Enter."""
from pathlib import Path
import shlex
import tempfile

from ui import Editor


adapter = Path.home() / '.local/share/nvim/mason/packages/debugpy/venv/bin/python'
with tempfile.TemporaryDirectory(prefix='nvim-debug-navigation-') as directory:
    root = Path(directory)
    source = root / 'example.py'
    source.write_text('payload = {"child": {"answer": 42}}\nscalar = 17\nprint(payload, scalar)\n')
    received, ready = root / 'terminal-bytes', root / 'ready'
    reader = root / 'reader.py'
    reader.write_text('import os,pathlib,tty\ntty.setraw(0)\n'
                      'os.write(1,b"\\x1b=\\x1b[?2004hConfirm prompt\\r\\n")\n'
                      f'pathlib.Path({str(ready)!r}).touch()\n'
                      f'with open({str(received)!r},"ab",buffering=0) as f:\n'
                      ' while True: f.write(os.read(0,1024))\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(source))
        main = editor.lua('return require("config.ide").editor_window()')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        editor.lua('local dap=require("dap");local program,python=...;'
                   'dap.adapters.nav_test={type="executable",command=python,args={"-m","debugpy.adapter"}};'
                   'require("dap.breakpoints").set({},vim.api.nvim_get_current_buf(),3);'
                   'dap.run({type="nav_test",request="launch",name="Navigation test",program=program,pythonPath=python,console="internalConsole"})', str(source), str(adapter))
        editor.wait(lambda: editor.lua('local s=require("dap").session();return s and s.current_frame and s.current_frame.line==3'), 'Paused at fixture breakpoint')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Debug panes mount')
        editor.lua('local t=require("config.terminals");t.show(t.active);'
                   'vim.fn.chansend(vim.b[t.active].terminal_job_id,...)', '/usr/bin/python3 -B ' + shlex.quote(str(reader)) + '\n')
        editor.wait(ready.exists, 'Raw terminal prompt is ready')

        def terminal_enter():
            editor.lua('local t=require("config.terminals");vim.api.nvim_set_current_win(t.win);vim.cmd("startinsert")')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 't', 'Terminal input')
            before = received.read_bytes() if received.exists() else b''
            editor.call('nvim_input', '<CR>')
            editor.wait(lambda: received.exists() and len(received.read_bytes()) > len(before), 'Enter reaches the paused-session terminal')
            assert received.read_bytes()[len(before):] == b'\r', 'Enter is a carriage return, without escape/selection keys'

        terminal_enter()
        editor.lua('local w=require("dapui").elements.watches;w.add("payload");w.add("scalar")')

        def pane(index):
            return editor.lua('return require("config.debugger").wins[...]', index)

        watches, scopes = pane(4), pane(1)
        collapsed_icon = editor.lua('return require("dapui.config").icons.collapsed')
        if editor.lua('return require("config.settings").icons'):
            assert collapsed_icon == '▸'
            assert editor.lua('return require("dapui.config").icons.expanded') == '▾'

        def lines(win):
            return editor.lua('return vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false)', win)

        def find(win, text):
            return next((i for i, line in enumerate(lines(win), 1) if text in line), None)

        def child_row():
            return next((i for i, line in enumerate(lines(watches), 1) if line.startswith(' ') and "'child'" in line), None)

        def mode():
            return editor.lua('return vim.fn.mode()')

        def key(keys, expected):
            editor.call('nvim_input', keys)
            editor.wait(lambda: mode() == expected, 'Mode after ' + keys)

        def point(win, row, column):
            editor.lua('local w,r=...;vim.api.nvim_win_call(w,function() vim.fn.winrestview({topline=math.max(1,r-2)}) end)', win, row)
            editor.lua('vim.cmd("redraw!")')
            return editor.lua('local w,r,c=...;local p=vim.fn.screenpos(w,r,1);local left=vim.api.nvim_win_get_position(w)[2];'
                              'return {p.row-1,left+c}', win, row, column)

        def click(win, row, column=5, repeats=''):
            row, column = point(win, row, column)
            editor.call('nvim_input_mouse', 'left', 'press', repeats, 0, row, column)
            editor.call('nvim_input_mouse', 'left', 'release', repeats, 0, row, column)
            editor.lua('vim.cmd("redraw!")')

        editor.wait(lambda: find(watches, collapsed_icon + ' payload'), 'Watch renders')
        pending = received.read_bytes()
        prompt_row = len(lines(watches))
        width = editor.call('nvim_win_get_width', watches)
        click(watches, prompt_row, width - 3)
        editor.wait(lambda: mode() == 'i' and editor.lua('return vim.api.nvim_get_current_win()') == watches, 'Blank end of prompt row enters Insert from terminal')
        key('pay<Esc>', 'i')
        assert lines(watches)[-1] == '> pay', 'Escape cannot leave the focused prompt'
        editor.lua('require("nio").run(function() require("dapui").elements.watches.render() end)')
        editor.wait(lambda: lines(watches)[-1] == '> pay', 'Asynchronous render preserves the draft')
        assert mode() == 'i'
        key('<Up>', 'n')
        assert editor.lua('return vim.api.nvim_win_get_cursor(0)[1]') == len(lines(watches)) - 1
        assert editor.lua('return vim.wo.cursorline and vim.wo.cursorlineopt=="both"')
        assert editor.lua('return vim.o.guicursor') == 'a:DesktopPanelCursor'
        editor.lua('vim.cmd("redraw!")')
        selected = editor.lua('local w=vim.api.nvim_get_current_win();local p=vim.fn.screenpos(w,vim.api.nvim_win_get_cursor(w)[1],1);'
                              'local left=vim.api.nvim_win_get_position(w)[2];return {row=p.row-1,left=left+vim.fn.getwininfo(w)[1].textoff,'
                              'right=left+vim.api.nvim_win_get_width(w)-1-require("config.vscroll").width(w),'
                              'color=vim.api.nvim_get_hl(0,{name="NeoTreeCursorLine",link=false}).bg}')
        assert all(editor.highlights[identifier].get('background') == selected['color']
                   for identifier in editor.attributes[selected['row']][selected['left']:selected['right']]), 'Rendered selection covers the whole content row'
        editor.lua('require("nio").run(function() require("dapui").elements.watches.render() end)')
        editor.wait(lambda: lines(watches)[-1] == '> pay' and mode() == 'n', 'Background render retains the draft and list mode')
        key('<Down>', 'i')
        key('load<CR>', 'i')
        editor.wait(lambda: editor.lua('return #require("dapui").elements.watches.get()') == 3, 'Native Enter adds one expression and keeps input')
        assert editor.lua('return require("dapui").elements.watches.get()[3].expression') == 'payload'
        editor.wait(lambda: lines(watches)[-1] == '> ', 'Submission clears the draft')
        assert received.read_bytes() == pending, 'Debug mouse/typing sends no keys to the terminal'

        row = find(watches, collapsed_icon + ' payload')
        click(watches, row, width - 3)
        editor.wait(child_row, 'Value-side click expands a watch')
        assert mode() == 'n'
        click(watches, row, 1, '2')
        editor.wait(lambda: child_row() is None, 'Repeated click in row margin collapses')
        key('<CR>', 'n')
        editor.wait(child_row, 'Enter expands the same watch')
        key('<CR>', 'n')
        editor.wait(lambda: child_row() is None, 'Enter collapses it')
        key('e', 'i')
        editor.wait(lambda: lines(watches)[-1] == '> payload', 'Native edit action fills the input row')
        key("<C-u>payload['child']<CR>", 'i')
        editor.wait(lambda: editor.lua('return require("dapui").elements.watches.get()[1].expression') == "payload['child']", 'Editing updates the watch through its native callback')
        assert editor.lua('return #require("dapui").elements.watches.get()') == 3

        # Focus from the keyboard preserves Normal in list rows. Down enters
        # the final prompt; Up exits it without losing the unfinished input.
        editor.lua('vim.api.nvim_set_current_win(...);vim.api.nvim_win_set_cursor(0,{1,0})', scopes)
        editor.wait(lambda: mode() == 'n', 'Scopes keyboard entry is Normal')
        click(scopes, 1, editor.call('nvim_win_get_width', scopes) - 3)
        collapsed = len(lines(scopes))
        key('<CR>', 'n')
        editor.wait(lambda: len(lines(scopes)) != collapsed, 'Scope header Enter toggles its contents')
        for index in (2, 3):
            editor.lua('vim.api.nvim_set_current_win(...);vim.api.nvim_win_set_cursor(0,{1,0})', pane(index))
            editor.wait(lambda: mode() == 'n', 'Debug list keyboard entry is Normal')
            key('<CR><CR>', 'n')
        editor.lua('vim.api.nvim_set_current_win(...);vim.api.nvim_win_set_cursor(0,{1,0})', watches)
        editor.wait(lambda: mode() == 'n', 'Watch list keyboard entry is Normal')
        editor.lua('vim.api.nvim_win_set_cursor(0,{vim.api.nvim_buf_line_count(0)-1,0})')
        key('<Down>', 'i')
        key('unsubmitted<Up>', 'n')
        key('<Down>', 'i')
        assert lines(watches)[-1] == '> unsubmitted'
        terminal_enter()
        # Commit real Alt+A keyboard panel selection into a Debug list, then
        # into Watches while its cursor is still on the unfinished input.
        key('<M-a>', 't')
        editor.lua('local n=require("config.panel_navigation");n.state.target=...;n.show()', scopes)
        key('<CR>', 'n')
        key('<M-a>', 'n')
        editor.lua('local n=require("config.panel_navigation");n.state.target=...;n.show()', watches)
        key('<CR>', 'i')
        assert lines(watches)[-1] == '> unsubmitted'
        terminal_enter()
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        assert not editor.lua('return vim.bo[...].modified', document)
        assert editor.lua('local s=require("dap").session();return s and s.current_frame and s.current_frame.line==3')
        print('PASS: row-wide clicks/repeated clicks and Enter; Normal lists with hidden caret/full-row selection; persistent Watches input, native submit, Up/Down and draft preservation; raw terminal Enter with a paused debugger; session/document preserved.')
    except Exception:
        print(editor.lua('return {mode=vim.fn.mode(),ft=vim.bo.filetype,messages=vim.fn.execute("messages"),watches=vim.api.nvim_buf_get_lines(require("dapui").elements.watches.buffer(),0,-1,false)}'))
        raise
    finally:
        try:
            if editor.process.poll() is None:
                editor.lua('require("dap").terminate();vim.wait(200)')
        finally:
            editor.close()
