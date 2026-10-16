"""Console clicks and Normal-mode Enter execute real REPL input at a breakpoint."""
from pathlib import Path
import tempfile
from ui import Editor

adapter = Path.home() / '.local/share/nvim/mason/packages/debugpy/venv/bin/python'
with tempfile.TemporaryDirectory(prefix='nvim-debug-console-') as directory:
    root = Path(directory)
    source = root / 'example.py'
    source.write_text('tracking_data = {"history": []}\ncheckpoint = 0\nprint(tracking_data)\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(source))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        editor.lua('local dap=require("dap");local program,python=...;_G.console_results={};'
                   'dap.listeners.after.evaluate["console-input-test"]=function(_,err,result,args) '
                   '_G.console_results[#_G.console_results+1]={error=err and tostring(err),result=result and result.result,expression=args.expression,context=args.context,frame=args.frameId} end;'
                   'dap.adapters.test_console={type="executable",command=python,args={"-m","debugpy.adapter"}};'
                   'require("dap.breakpoints").set({},vim.api.nvim_get_current_buf(),3);'
                   'dap.run({type="test_console",request="launch",name="Console test",program=program,pythonPath=python,console="internalConsole"})', str(source), str(adapter))
        editor.wait(lambda: editor.lua('local s=require("dap").session();return s and s.stopped_thread_id and s.current_frame and s.current_frame.line==3'), 'Fixture stops at breakpoint')
        editor.lua('require("config.terminals").show_debug_console()')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Console starts accepting input')
        console = editor.lua('return require("config.terminals").console_buf')
        win = editor.lua('return require("config.terminals").win')
        def results():
            return editor.lua('return _G.console_results')
        def stopped():
            return editor.lua('local s=require("dap").session();return s and s.stopped_thread_id and s.current_frame.line==3')
        def escape():
            editor.call('nvim_input', '<Esc>')
            editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Console Normal mode')
        def body_click():
            editor.lua('vim.cmd("redraw!")')
            row, col = editor.lua('local w=...;local p=vim.api.nvim_win_get_position(w);return {p[1]+vim.api.nvim_win_get_height(w)-2,p[2]+8}', win)
            editor.click(row, col)
            editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_win()') == win and editor.lua('return vim.fn.mode()') == 'i', 'Console body click resumes prompt input')
        # Previously Normal-mode Enter tried opening a result and reported
        # "No action possible on dap> ..." instead of submitting the prompt.
        assignment = 'tracking_data["history"] = ["DOR"]'
        editor.call('nvim_input', assignment)
        escape()
        editor.call('nvim_input', '<CR>')
        editor.wait(lambda: any(r['expression'] == assignment for r in results()), 'Normal Enter submits assignment')
        evaluation = next(r for r in results() if r['expression'] == assignment)
        assert not evaluation.get('error'), evaluation
        assert evaluation['context'] == 'repl' and evaluation['frame'], evaluation
        assert stopped(), 'Evaluation does not continue or terminate the program'
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Prompt stays editable after Enter')
        editor.call('nvim_input', 'tracking_data["history"]<CR>')
        editor.wait(lambda: any(r['expression'] == 'tracking_data["history"]' for r in results()), 'Typed query evaluates')
        result = next(r for r in results() if r['expression'] == 'tracking_data["history"]')
        assert 'DOR' in result['result'], result

        escape()
        body_click()  # Same window, including blank space below the prompt.
        editor.call('nvim_input', '40 + 2<CR>')
        editor.wait(lambda: any(r['expression'] == '40 + 2' and r.get('result') == '42' for r in results()), 'Repeated console click and expression')
        editor.lua('vim.cmd("redraw!")')
        position = editor.lua('local w=...;local p=vim.fn.screenpos(w,1,1);return {p.row-1,p.col-1}', main)
        editor.click(*position)
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Editor input before returning to console')
        body_click()
        editor.call('nvim_input', '<Up>')
        editor.wait(lambda: editor.lua('return vim.api.nvim_get_current_line()').endswith('40 + 2'), 'Native REPL command history retained')
        editor.call('nvim_input', '<C-u>6 * 7<CR>')
        editor.wait(lambda: any(r['expression'] == '6 * 7' and r.get('result') == '42' for r in results()), 'History replacement executes')
        assert editor.lua('return vim.api.nvim_win_get_buf(...)', main) == document
        assert not editor.lua('return vim.bo[...].modified', document)
        assert stopped()
        print('PASS: console click/reclick accepts input; Normal Enter submits assignment through native REPL callback; selected frame/context, typed evaluation and history work; paused session and editor preserved', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print(editor.lua('local t=require("config.terminals");return {mode=vim.fn.mode(),lines=t.console_buf and vim.api.nvim_buf_get_lines(t.console_buf,0,-1,false),results=_G.console_results}'), flush=True)
        raise
    finally:
        try:
            if editor.process.poll() is None:
                editor.lua('require("dap").terminate();vim.wait(200)')
        finally:
            editor.close()
