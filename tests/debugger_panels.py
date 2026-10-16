from pathlib import Path
import tempfile

from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-debugger-panels-') as directory:
    root = Path(directory)
    file = root / 'code.lua'
    file.write_text('local function example()\n  return 42\nend\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        terminal = editor.lua('return require("config.terminals").active')

        def source():
            return editor.lua('local s=require("config.sidebar").state();return s and s.name')

        def choose_menu(label):
            editor.lua('vim.cmd("stopinsert");require("config.ide").menu("View")')

            def location():
                editor.lua('vim.cmd("redraw!")')
                for row, cells in enumerate(editor.grid):
                    text = ''.join(cells)
                    if label in text:
                        return row, text.index(label) + 2

            editor.wait(location, label+' visible in View menu')
            editor.click(*location())

        def click_source(label):
            editor.lua('vim.cmd("stopinsert");vim.cmd("redraw!")')
            position = editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);return {p[1],p[2],vim.api.nvim_win_get_width(w)}')
            row, left, width = position
            text = ''.join(editor.grid[row][left:left+width])
            editor.click(row, left + text.index(label) + 1)

        # Ensure all six labels are visible while exercising their real clicks.
        editor.lua('local s,w=require("config.sidebar").state();vim.api.nvim_win_set_width(w,46);require("config.layout").save()')
        choose_menu('Debugger')
        editor.wait(lambda: source() == 'debug' and editor.lua('return require("config.debugger").is_open()'), 'Debug source has four panes')
        def geometry():
            return editor.lua('local s,w=require("config.sidebar").state();local p=vim.api.nvim_win_get_position(w);local out={};'
                              'for _,win in ipairs(require("config.debugger").wins) do out[#out+1]={ft=vim.bo[vim.api.nvim_win_get_buf(win)].filetype,'
                              'title=vim.wo[win].winbar,left=vim.api.nvim_win_get_position(win)[2],width=vim.api.nvim_win_get_width(win)} end;'
                              'return {panes=out,left=p[2],width=vim.api.nvim_win_get_width(w),bar=vim.api.nvim_eval_statusline(vim.wo[w].winbar,{winid=w,use_winbar=true}).str}')
        state = geometry()
        assert [p['ft'] for p in state['panes']] == ['dapui_scopes', 'dapui_breakpoints', 'dapui_stacks', 'dapui_watches'], state
        assert all(p['left'] == state['left'] and p['width'] == state['width'] for p in state['panes']), state
        assert all(label in state['panes'][i]['title'] for i, label in enumerate(('Scopes', 'Breakpoints', 'Call stack', 'Watches'))), state
        labels = ['Projects', 'Files', 'Search', 'Debug', 'Git', 'Tabs']
        assert [state['bar'].index(label) for label in labels] == sorted(state['bar'].index(label) for label in labels), state
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        editor.lua('require("dap.breakpoints").set({},...,2);require("nio").run(function() require("dapui").elements.breakpoints.render() end)', document)
        editor.wait(lambda: editor.lua('return table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(require("config.debugger").wins[2]),0,-1,false),"\\n"):find("code.lua",1,true)~=nil'), 'Breakpoints pane renders live DAP state')
        for target in ('Files', 'Tabs', 'Debug'):
            click_source(target)
            editor.wait(lambda: source() == {'Files': 'filesystem', 'Tabs': 'buffers', 'Debug': 'debug'}[target], target+' source selected')
            if target == 'Debug':
                editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Four debug panes restored')
            else:
                editor.wait(lambda: not editor.lua('return require("config.debugger").is_open()'), 'Debug panes close when switching sources')
        editor.lua('require("config.terminals").show_debug_console()')
        editor.wait(lambda: editor.lua('local t=require("config.terminals");return t.console_active and vim.api.nvim_win_get_buf(t.win)==t.console_buf'), 'Debug console replaces terminal content')
        editor.lua('require("dap.repl").append("Test debugger output")')
        editor.wait(lambda: editor.lua('local t=require("config.terminals");return table.concat(vim.api.nvim_buf_get_lines(t.console_buf,0,-1,false),"\\n"):find("Test debugger output",1,true)~=nil'), 'Debug output reaches shared console')
        assert editor.lua('local t=require("config.terminals");local line=vim.api.nvim_buf_get_lines(t.list_buf,t.console_row-1,t.console_row,false)[1];return not line:find("×",1,true)')
        position = editor.lua('local t=require("config.terminals");local p=vim.api.nvim_win_get_position(t.list_win);return {p[1]+t.console_row,p[2]+vim.api.nvim_win_get_width(t.list_win)-2}')
        editor.click(*position)
        assert editor.lua('return require("config.terminals").console_active')
        editor.lua('require("config.terminals").show(...)', terminal)
        assert not editor.lua('return require("config.terminals").console_active')
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.terminals").win)') == terminal
        editor.lua('local ns=vim.api.nvim_create_namespace("StatusProblemsTest");'
                   'vim.diagnostic.set(ns,...,{{lnum=0,col=0,severity=1,message="Status bar error"},'
                   '{lnum=1,col=0,severity=2,message="Status bar warning"}})', document)

        def click_diagnostic(severity):
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("startinsert")', main)
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor input before status click')
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Diagnostics update in Normal')
            symbol = editor.lua('return vim.trim(require("lualine.components.diagnostics.config").symbols.icons[...])', severity)
            def position():
                editor.lua('require("lualine").refresh({place={"statusline"}});vim.cmd("redraw!")')
                row = editor.lua('return vim.o.lines-vim.o.cmdheight-1')
                text = ''.join(editor.grid[row])
                if symbol in text:
                    return row, text.index(symbol)
            editor.wait(position, 'Diagnostic icon appears in status bar')
            editor.click(*position())

        click_diagnostic('error')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win:valid()'), 'Problems opens in bottom pane')
        problemwin = editor.lua('return require("config.problems").view.win.win')
        click_diagnostic('warn')
        assert editor.lua('local p=require("config.problems");return p.view and p.view.win.win==...', problemwin), 'Repeated status click keeps Problems open'
        assert editor.lua('local t=require("config.terminals");return not t.win and not t.list_win')
        assert editor.lua('local p=require("config.problems");local win=p.view.win.win;local m=require("config.ide").main_editor;'
                          'return vim.api.nvim_win_get_width(win)==vim.api.nvim_win_get_width(m) and vim.api.nvim_win_get_position(win)[2]==vim.api.nvim_win_get_position(m)[2]')

        def hide_problems():
            editor.lua('vim.cmd("redraw!")')
            win = editor.lua('return require("config.problems").view.win.win')
            position = editor.lua('local win=...;local p=vim.api.nvim_win_get_position(win);return {p[1],p[2],vim.api.nvim_win_get_width(win)}', win)
            row, left, width = position
            text = ''.join(editor.grid[row][left:left+width])
            assert 'Problems' in text and '[↓ Hide]' in text, text
            editor.click(row, left + text.index('[↓ Hide]') + 2)
            editor.wait(lambda: not editor.lua('return require("config.problems").view~=nil'), 'Hide closes Problems')

        hide_problems()
        editor.wait(lambda: editor.lua('local t=require("config.terminals");return t.win and t.list_win and vim.api.nvim_win_get_buf(t.win)==t.active'), 'Hide restores previously visible terminal')
        editor.lua('require("config.terminals").hide()')
        choose_menu('Problems')
        editor.wait(lambda: editor.lua('local p=require("config.problems");return p.view and p.view.win:valid()'), 'Problems also opens while terminal is hidden')
        hide_problems()
        assert editor.lua('local t=require("config.terminals");return not t.win and not t.list_win'), 'Hide preserves previously hidden terminal'
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages and 'Vim:E21' not in messages, messages
        print('PASS: six sidebar tabs, four titled Debug panes and live breakpoints; shared persistent debug console; Problems title/Hide and both terminal visibility states', flush=True)
    finally:
        editor.close()
