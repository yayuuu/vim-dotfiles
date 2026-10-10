"""Opening Symbols tolerates the previously focused dialog closing mid-call."""
from pathlib import Path
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-outline-focus-') as directory:
    root = Path(directory)
    file = root / 'example.lua'
    file.write_text('local function example()\n  return true\nend\nreturn example()\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        editor.wait(lambda: editor.lua('return require("aerial").is_open()'), 'Initial Symbols panel is open')
        main = editor.lua('return require("config.ide").editor_window()')
        editor.lua('local ide=require("config.ide");local aerial=require("aerial");'
                   'require("aerial.window").close_all();'
                   'local buf=vim.api.nvim_create_buf(false,true);vim.bo[buf].bufhidden="wipe";'
                   'local dialog=vim.api.nvim_open_win(buf,true,{relative="editor",row=5,col=10,width=20,height=2,style="minimal"});'
                   'local original=aerial.open;aerial.open=function(opts) '
                   'if vim.api.nvim_win_is_valid(dialog) then vim.api.nvim_win_close(dialog,true) end;return original(opts) end;'
                   'ide.outline();aerial.open=original')
        editor.wait(lambda: editor.lua('return require("aerial").is_open()'), 'Symbols opens after dialog closes')
        assert editor.lua('return require("config.ide").editor_window()') == main
        assert not editor.lua('return require("config.ide").outline_busy')
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'Invalid window id' not in messages, messages
        assert editor.lua('return vim.api.nvim_get_current_win()') == main
        print('PASS: Symbols creation tolerates a dialog closing during Aerial.open, preserves the editor, and releases the outline guard.')
    finally:
        editor.close()
