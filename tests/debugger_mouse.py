"""Mouse expansion, context actions and clipping with a real debugpy session."""
from pathlib import Path
import tempfile

from ui import Editor

adapter = Path.home() / '.local/share/nvim/mason/packages/debugpy/venv/bin/python'
with tempfile.TemporaryDirectory(prefix='nvim-debugger-mouse-') as directory:
    root = Path(directory)
    source = root / 'example.py'
    source.write_text('payload = {"child": {"answer": 42}, "long": "a very long value " * 30}\nscalar = 17\nprint(payload, scalar)\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('local content={""};local copy=function(lines) content=lines end;local paste=function() return {content,"v"} end;'
                   'vim.g.clipboard={name="Debugger test clipboard",copy={["+"]=copy,["*"]=copy},paste={["+"]=paste,["*"]=paste},cache_enabled=0}')
        editor.lua('require("config.ide").open_file(...)', str(source))
        editor.call('nvim_input', '\x1b')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_mode().mode') == 'n', 'Normal mode')
        main = editor.lua('return require("config.ide").main_editor')
        editor.lua('local dap=require("dap");dap.set_log_level("DEBUG");local program,python=...;'
                   'dap.adapters.test_python={type="executable",command=python,args={"-m","debugpy.adapter"}};'
                   'require("dap.breakpoints").set({},vim.api.nvim_get_current_buf(),3);'
                   'dap.run({type="test_python",request="launch",name="Mouse test",program=program,pythonPath=python,console="internalConsole"})', str(source), str(adapter))
        editor.wait(lambda: editor.lua('local s=require("dap").session();return s and s.stopped_thread_id and s.current_frame and s.current_frame.line==3'), 'Python stops at fixture breakpoint')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Debug panels mount')
        def pane(index):
            return editor.lua('return require("config.debugger").wins[...]', index)
        def contents(win):
            return editor.lua('return vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false)', win)
        def row_containing(win, text):
            names = editor.lua('local b=vim.api.nvim_win_get_buf(...);local ns=vim.api.nvim_get_namespaces().dapui;local out={};'
                               'for _,mark in ipairs(vim.api.nvim_buf_get_extmarks(b,ns,0,-1,{details=true})) do '
                               'if mark[4].hl_group=="DapUIVariable" then local line=vim.api.nvim_buf_get_lines(b,mark[2],mark[2]+1,false)[1];'
                               'out[#out+1]={mark[2]+1,line:sub(mark[3]+1,mark[4].end_col)} end end;return out', win)
            return next((row for row, name in names if name.strip("'\"") == text), None)
        scopes = pane(1)
        editor.wait(lambda: row_containing(scopes, 'payload'), 'Variables rendered')
        def location(win, row):
            editor.lua('local win,row=...;vim.api.nvim_set_current_win(win);vim.cmd("stopinsert");vim.api.nvim_win_set_cursor(win,{row,0});vim.cmd("redraw!")', win, row)
            return editor.lua('local w,l=...;local pos=vim.fn.screenpos(w,l,1);local left=vim.api.nvim_win_get_position(w)[2];return {pos.row-1,left+4}', win, row)
        def left_click(win, row):
            editor.click(*location(win, row))
        def right_click(win, row):
            position = location(win, row)
            editor.call('nvim_input_mouse', 'right', 'press', '', 0, *position)
            editor.call('nvim_input_mouse', 'right', 'release', '', 0, *position)
            editor.wait(lambda: editor.lua('return vim.bo.filetype') == 'NvMenu', 'Debugger context menu opens')
        def menu_item(label):
            def location():
                editor.lua('vim.cmd("redraw!")')
                for row, cells in enumerate(editor.grid):
                    text = ''.join(cells)
                    if label in text:
                        return row, text.index(label) + 2
            editor.wait(location, label+' visible in context menu')
            editor.click(*location())
        left_click(scopes, row_containing(scopes, 'payload'))
        editor.wait(lambda: row_containing(scopes, 'child'), 'Single click expands dict')
        left_click(scopes, row_containing(scopes, 'child'))
        editor.wait(lambda: row_containing(scopes, 'answer'), 'Single click expands nested dict')
        answer = row_containing(scopes, 'answer')
        right_click(scopes, answer)
        menu_item('Add to watches')
        editor.wait(lambda: editor.lua('return #require("dapui").elements.watches.get()') == 1, 'Nested expression added to watches')
        expression = editor.lua('return require("dapui").elements.watches.get()[1].expression')
        assert expression == "payload['child']['answer']", expression
        right_click(scopes, row_containing(scopes, 'answer'))
        menu_item('Copy value')
        editor.wait(lambda: editor.lua('return vim.fn.getreg(\'"\')') == '42', 'Full actual value copied')
        right_click(scopes, row_containing(scopes, 'answer'))
        menu_item('Copy expression')
        editor.wait(lambda: editor.lua('return vim.fn.getreg(\'"\')') == expression, 'Evaluate name copied')
        scalar = row_containing(scopes, 'scalar')
        right_click(scopes, scalar)
        editor.call('nvim_input', '\x17')
        editor.wait(lambda: editor.lua('return #require("dapui").elements.watches.get()') == 2, 'Menu Ctrl+W adds scalar watch')
        scalar_text = contents(scopes)[scalar - 1]
        right_click(scopes, scalar)
        menu_item('Copy sentence')
        editor.wait(lambda: editor.lua('return vim.fn.getreg(\'"\')') == scalar_text, 'Entire rendered sentence copied')
        right_click(scopes, scalar)
        menu_item('Evaluate in debug console')
        editor.wait(lambda: editor.lua('return require("config.terminals").console_active'), 'Evaluation uses shared console')
        editor.wait(lambda: editor.lua('local t=require("config.terminals");return table.concat(vim.api.nvim_buf_get_lines(t.console_buf,0,-1,false),"\\n"):find("17",1,true)~=nil'), 'Console evaluates scalar')
        left_click(scopes, row_containing(scopes, 'payload'))
        editor.wait(lambda: not row_containing(scopes, 'answer'), 'Second click collapses expanded descendants')
        # Click a long value; automatic line-hover floats must never cover the editor.
        left_click(scopes, row_containing(scopes, 'payload'))
        editor.wait(lambda: row_containing(scopes, 'long'), 'Long variable visible')
        left_click(scopes, row_containing(scopes, 'long'))
        editor.lua('vim.wait(200);vim.cmd("redraw!")')
        assert not editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do if vim.api.nvim_win_get_config(w).relative=="cursor" then return true end end;return false'), 'Long text stays inside sidebar'
        right_click(scopes, row_containing(scopes, 'payload'))
        menu_item('Add to watches')
        editor.wait(lambda: editor.lua('return #require("dapui").elements.watches.get()') == 3, 'Container added to watches')
        watches = pane(4)
        def payload_watch():
            icons = editor.lua('local i=require("dapui.config").icons;return {i.collapsed,i.expanded}')
            return next((i for i, text in enumerate(contents(watches), 1) if text.startswith(tuple(icon + ' payload ' for icon in icons))), None)
        editor.wait(payload_watch, 'Container watch renders')
        left_click(watches, payload_watch())
        editor.wait(lambda: row_containing(watches, 'child'), 'Watches expands with single click')
        left_click(watches, row_containing(watches, 'child'))
        editor.wait(lambda: row_containing(watches, 'answer'), 'Nested watch expands with Unicode markers')
        right_click(watches, row_containing(watches, 'answer'))
        menu_item('Copy expression')
        editor.wait(lambda: editor.lua('return vim.fn.getreg(\'"\')') == expression, 'Nested watch metadata survives multibyte expanders')
        right_click(watches, payload_watch())
        menu_item('Remove from watches')
        editor.wait(lambda: editor.lua('return #require("dapui").elements.watches.get()') == 2, 'Watch menu removes chosen expression')
        stacks = pane(3)
        left_click(stacks, 1)
        assert editor.lua('return vim.api.nvim_win_call(...,function() return vim.fn.foldclosed(2) end)', stacks) == 2, 'Thread header collapses stack frames'
        left_click(stacks, 1)
        assert editor.lua('return vim.api.nvim_win_call(...,function() return vim.fn.foldclosed(2) end)', stacks) == -1
        right_click(stacks, 2)
        menu_item('Go to source')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_win()') == main, 'Frame menu opens main editor')
        breakpoints = pane(2)
        left_click(breakpoints, 1)
        assert editor.lua('return vim.api.nvim_win_call(...,function() return vim.fn.foldclosed(2) end)', breakpoints) == 2, 'Breakpoint file group collapses'
        left_click(breakpoints, 1)
        right_click(breakpoints, 2)
        menu_item('Go to source')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_win()') == main, 'Breakpoint menu opens main editor')
        right_click(breakpoints, 2)
        menu_item('Enable / disable breakpoint')
        editor.wait(lambda: editor.lua('return vim.tbl_count(require("dap.breakpoints").get())') == 0, 'Breakpoint menu disables selected breakpoint')
        right_click(breakpoints, 2)
        menu_item('Enable / disable breakpoint')
        editor.wait(lambda: editor.lua('return vim.tbl_count(require("dap.breakpoints").get())') == 1, 'Breakpoint menu enables selected breakpoint')
        right_click(breakpoints, 2)
        menu_item('Remove breakpoint')
        editor.wait(lambda: editor.lua('return vim.tbl_count(require("dap.breakpoints").get())') == 0, 'Breakpoint menu removes selected breakpoint')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == editor.lua('return vim.fn.bufnr(...)', str(source))
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'E21' not in messages, messages
        print('PASS: real debugpy scopes/watches and stack/breakpoint groups expand on clicks; menus add/remove watches, copy values/expressions/sentences, evaluate in shared console, go to source and enable/disable/remove breakpoints; long text stays clipped', flush=True)
    except Exception:
        print(editor.lua('local s=require("dap").session();local f=s and s.current_frame;return {line=f and f.line,panes=require("config.debugger").wins,messages=vim.fn.execute("messages")}'), flush=True)
        print(editor.lua('local out={};for name,logger in pairs(require("dap.log")._loggers) do local ok,lines=pcall(vim.fn.readfile,logger:get_path());out[name]=ok and vim.list_slice(lines,math.max(1,#lines-30)) or {} end;return out'), flush=True)
        raise
    finally:
        try:
            if editor.process.poll() is None:
                editor.lua('require("dap").terminate();vim.wait(200)')
        finally:
            editor.close()
