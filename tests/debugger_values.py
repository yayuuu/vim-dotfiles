"""Inspect values only after Ctrl+click or the context action, using real debugpy."""
from pathlib import Path
import tempfile
from ui import Editor

adapter = Path.home() / '.local/share/nvim/mason/packages/debugpy/venv/bin/python'
with tempfile.TemporaryDirectory(prefix='nvim-debugger-values-') as directory:
    root = Path(directory)
    source = root / 'example.py'
    source.write_text('answer = 42\npayload = {"child": {"answer": 42}}\nanswer += 1\nprint(answer, payload["child"]["answer"])\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(source))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_get_current_buf()')
        original = editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', document)
        editor.lua('local dap=require("dap");local program,python=...;'
                   '_G.debug_evaluations={};dap.listeners.before.evaluate["inspect-test"]=function(_,_,_,args) '
                   '_G.debug_evaluations[#_G.debug_evaluations+1]=args.expression end;'
                   'dap.adapters.test_values={type="executable",command=python,args={"-m","debugpy.adapter"}};'
                   'require("dap.breakpoints").set({},vim.api.nvim_get_current_buf(),3);'
                   'dap.run({type="test_values",request="launch",name="Values test",program=program,pythonPath=python,console="internalConsole"})', str(source), str(adapter))
        def stopped(line):
            return editor.lua('local s=require("dap").session();return s and s.stopped_thread_id and s.current_frame and s.current_frame.line==...', line)
        def popup():
            return editor.lua('for _,w in ipairs(vim.api.nvim_list_wins()) do '
                              'if vim.api.nvim_win_get_config(w).relative~="" and vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="dapui_hover" then return w end end')
        def text():
            win = popup()
            return '' if not win else editor.lua('return table.concat(vim.api.nvim_buf_get_lines(vim.api.nvim_win_get_buf(...),0,-1,false),"\\n")', win)
        def location(line, column):
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert");vim.cmd("redraw!")', main)
            return editor.lua('local w,l,c=...;local p=vim.fn.screenpos(w,l,c);return {p.row-1,p.col-1}', main, line, column)
        def ctrl_click(line, column, release='C', insert=False):
            row, col = location(line, column)
            if insert:
                editor.lua('vim.cmd("startinsert")')
                editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Insert before Ctrl+click')
            editor.call('nvim_input_mouse', 'left', 'press', 'C', 0, row, col)
            editor.call('nvim_input_mouse', 'left', 'release', release, 0, row, col)
        editor.wait(lambda: stopped(3), 'Stopped at Python fixture')
        editor.wait(lambda: editor.lua('return require("config.debugger").is_open()'), 'Debugger mounted')
        assert not editor.lua('return package.loaded["nvim-dap-virtual-text"]~=nil'), 'Automatic annotations are not loaded'
        assert not popup()
        editor.click(*location(3, 2))
        editor.lua('vim.wait(100)')
        assert not popup(), 'Ordinary clicks keep native editing'
        assert editor.lua('return #_G.debug_evaluations') == 0, 'No background evaluations'

        # Drag cancellation and a release lost outside the host must not leave capture.
        row, col = location(3, 2)
        editor.call('nvim_input_mouse', 'left', 'press', 'C', 0, row, col)
        editor.call('nvim_input_mouse', 'left', 'drag', '', 0, row, col + 2)
        editor.call('nvim_input_mouse', 'left', 'release', '', 0, row, col + 2)
        editor.lua('vim.wait(50)')
        assert not popup()
        assert not editor.lua('return require("config.mouse_capture").active()')
        editor.call('nvim_input_mouse', 'left', 'press', 'C', 0, row, col)
        editor.click(row, col)
        assert not editor.lua('return require("config.mouse_capture").active()'), 'Fresh ordinary press recovers lost release'
        assert not popup()

        ctrl_click(3, 2)
        editor.wait(lambda: 'answer' in text() and '42' in text(), 'Ctrl+click evaluates the pointed variable')
        win = popup()
        dimensions = editor.lua('local c=vim.api.nvim_win_get_config(...);return {c.width,c.height}', win)
        assert dimensions[0] <= 78 and dimensions[1] <= 18, dimensions
        assert editor.lua('return vim.api.nvim_get_current_win()') == win
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: not popup(), 'Esc closes inspector')
        editor.wait(lambda: not editor.lua('return require("config.mouse_capture").active()'), 'Release clears capture')

        # Inspect nested expressions, not only the final word; generic releases work.
        ctrl_click(4, 18, release='', insert=True)
        editor.wait(lambda: 'payload["child"]["answer"]' in text() and '42' in text(), 'Nested expression popup')
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: not popup(), 'Nested popup closes')

        # The editor context menu shares the same action.
        row, col = location(3, 2)
        editor.call('nvim_input_mouse', 'right', 'press', '', 0, row, col)
        editor.call('nvim_input_mouse', 'right', 'release', '', 0, row, col)
        editor.wait(lambda: editor.lua('return vim.bo.filetype') == 'NvMenu', 'Code context menu opens')
        def inspect_item():
            editor.lua('vim.cmd("redraw!")')
            for row, cells in enumerate(editor.grid):
                line = ''.join(cells)
                if 'Inspect variable' in line:
                    return row, line.index('Inspect variable') + 2
        editor.wait(inspect_item, 'Inspect variable in context menu')
        editor.click(*inspect_item())
        editor.wait(lambda: 'answer' in text() and '42' in text(), 'Menu evaluates variable')
        editor.lua('require("dap").step_over()')
        editor.wait(lambda: stopped(4), 'Python steps to next line')
        editor.wait(lambda: not popup(), 'Stepping closes stale inspector')
        ctrl_click(4, 8)
        editor.wait(lambda: 'answer' in text() and '43' in text(), 'New click sees updated value')
        assert editor.lua('return vim.api.nvim_buf_get_lines(...,0,-1,false)', document) == original
        assert not editor.lua('return vim.bo[...].modified', document)
        editor.lua('require("dap").continue()')
        editor.wait(lambda: not popup(), 'Continue closes popup')
        editor.wait(lambda: not editor.lua('return require("dap").session()~=nil'), 'Fixture finishes')

        # Real PHP parser: retain $, nested properties and array keys.
        php = root / 'example.php'
        php.write_text('<?php\n$answer = 42;\necho $this->data["answer"];\n')
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(php))
        phpbuf = editor.lua('return vim.api.nvim_get_current_buf()')
        assert editor.lua('return require("config.debugger_inspect").expression(...,2,3)', phpbuf) == '$answer'
        assert editor.lua('return require("config.debugger_inspect").expression(...,3,8)', phpbuf) == '$this->data["answer"]'
        assert not editor.lua('return require("config.debugger_inspect").expression(...,2,8)', phpbuf), 'Whitespace is not evaluated'
        # A missing parser still permits simple PHP variables without stripping "$".
        assert editor.lua('local parser=vim.treesitter.get_node;vim.treesitter.get_node=function() error("missing parser") end;'
                          'local value=require("config.debugger_inspect").expression(...,2,3);vim.treesitter.get_node=parser;return value', phpbuf) == '$answer'
        assert not editor.lua('return vim.bo[...].modified', phpbuf)
        print('PASS: no automatic value plugin/evaluations; Ctrl+click and context menu open bounded popups; nested expressions, generic release, Esc/step/continue and PHP dollar names work; source unchanged', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print(editor.lua('return _G.debug_evaluations'), flush=True)
        raise
    finally:
        try:
            if editor.process.poll() is None:
                editor.lua('require("dap").terminate();vim.wait(200)')
        finally:
            editor.close()
