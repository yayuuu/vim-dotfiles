from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
import ui

with tempfile.TemporaryDirectory(prefix='nvim-picker-layout-') as directory:
    root = Path(directory)
    (root / 'example.txt').write_text('Example\n')
    (root / 'second.txt').write_text('Second example\n')
    editor = ui.Editor(root, root / 'state')
    try:
        for source in ('commands', 'files'):
            editor.lua('vim.cmd("stopinsert");Snacks.picker[... ]({cwd=select(2,...)})', source, str(root))
            editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.shown'), source+' opens')
            for width in (160, 140, 128, 160):
                editor.call('nvim_ui_try_resize', width, 48)
                editor.wait(lambda: editor.lua('local p=Snacks.picker.get()[1];return p and p.layout:valid() and require("config.popup_ui").buttons[p.layout.root.win]~=nil'), f'{source} gets close button at width {width}')
                # The close-button manager must preserve Snacks geometry and borders.
                errors = editor.lua('local p=Snacks.picker.get()[1];if not p then return {"Picker closed unexpectedly"} end;local wins={p.layout.root,p.input.win,p.list.win,p.preview.win};'
                                    'local errors={};for _,w in ipairs(wins) do if w:valid() then '
                                    'local actual=vim.api.nvim_win_get_config(w.win);local expected=w:win_opts();'
                                    'local borders={single={"┌","─","┐","│","┘","─","└","│"},rounded={"╭","─","╮","│","╯","─","╰","│"}};'
                                    'expected.border=borders[expected.border] or expected.border;'
                                    'for _,key in ipairs({"relative","row","col","width","height","border"}) do '
                                    'if not vim.deep_equal(actual[key],expected[key]) then '
                                    'errors[#errors+1]={window=w.win,key=key,actual=actual[key],expected=expected[key]} end end end end;return errors')
                assert not errors, (source, width, errors)
                editor.lua('vim.cmd("redraw!")')
                position = editor.lua('local p=Snacks.picker.get()[1];local b=require("config.popup_ui").buttons[p.layout.root.win];local pos=vim.api.nvim_win_get_position(b.win);return {pos[1],pos[2]+1}')
                assert editor.grid[position[0]][position[1]] == '×', (source, position)
            editor.click(*position)
            editor.wait(lambda: editor.lua('return #Snacks.picker.get()==0'), source+' cross closes all panes')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Error executing' not in messages, messages
        print('PASS: commands and configuration file pickers preserve native borders and pane geometry across resizing; close cross stays visible and closes the whole picker', flush=True)
    finally:
        editor.close()
