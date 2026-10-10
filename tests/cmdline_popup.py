"""Command completion leaves input text inside one stable Noice frame."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-cmdline-popup-') as directory:
    root = Path(directory)
    editor = Editor(root, root / 'state')
    try:
        editor.lua('vim.cmd("stopinsert");require("noice");vim.cmd("redraw!")')
        editor.call('nvim_input', ':q')
        def input_view():
            return editor.lua('for _,v in ipairs(require("noice.view")._views) do '
                              'if v.opts.view=="cmdline_popup" and v.view._visible and v.view._nui then '
                              'local n=v.view._nui;local c=vim.api.nvim_win_get_config(n.winid);'
                              'return {win=n.winid,config=c,position=vim.api.nvim_win_get_position(n.winid),'
                              'border=n.border.winid,border_config=vim.api.nvim_win_get_config(n.border.winid),'
                              'border_ft=vim.bo[vim.api.nvim_win_get_buf(n.border.winid)].filetype,'
                              'text=vim.api.nvim_buf_get_lines(n.bufnr,0,-1,false)} end end')
        editor.wait(input_view, 'Command input opens')
        editor.wait(lambda:editor.lua('return not require("config.popup_ui").pending'), 'Popup decoration settles')
        before=input_view()
        # With padding Nui owns a separate border window. Adding another native
        # border to its content displaces the text from the original frame.
        assert before['border_config'].get('border','none')=='none', ('Nui frame must not gain another border',before)
        editor.call('nvim_input','<Tab>')
        editor.wait(lambda:editor.lua('return require("blink.cmp").is_menu_visible()'), 'Completion opens')
        editor.lua('vim.cmd("redraw!")')
        after=input_view()
        assert after['position']==before['position'], ('Input text jumps when completion opens',before,after)
        assert after['config']['height']==before['config']['height']==1, 'Input retains one content row'
        assert after['border_config'].get('border','none')=='none', ('Completion must not add another border',after)
        menu=editor.lua('for _,w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do if vim.bo[vim.api.nvim_win_get_buf(w)].filetype=="blink-cmp-menu" then return {position=vim.api.nvim_win_get_position(w),height=vim.api.nvim_win_get_height(w)} end end')
        assert menu['position'][0]>after['position'][0], 'Completion list remains below the input text'
        button=editor.lua('local b=require("config.popup_ui").buttons[...];local p=vim.api.nvim_win_get_position(b.win);'
                          'return {position=p,col=p[2]+1,row=vim.api.nvim_win_get_config(b.win).row}',after['border'])
        assert button['row']==0, 'Close cross stays on the rendered Nui top border'
        editor.click(button['position'][0],button['col'])
        editor.wait(lambda:editor.lua('return vim.fn.getcmdtype()==""'), 'Close cross cancels the command')
        editor.call('nvim_input',':q')
        editor.wait(input_view, 'Command input reopens')
        editor.call('nvim_input','<C-c>')
        editor.wait(lambda:editor.lua('return vim.fn.getcmdtype()==""'), 'Keyboard cancellation works')
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: command completion keeps text in a stable single frame and below-input list; cancellation works.')
    finally:
        editor.close()
