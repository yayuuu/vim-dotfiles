"""Commit input focus must not change the editor tab separator color."""
from pathlib import Path
import json
import subprocess
import tempfile

from ui import Editor

# Exercise opaque separator colors; transparent palettes have blank separators.
module = Path(__file__).resolve().parents[1] / 'lua/config/settings.lua'
bootstrap = ('lua package.preload["config.settings"]=function() '
             f'local m=dofile({json.dumps(str(module))});m.color_palette="palette.json";return m end')


with tempfile.TemporaryDirectory(prefix='nvim-tab-focus-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-b', 'main', str(root)], check=True, stdout=subprocess.DEVNULL)
    editor = Editor(root, root / 'state', args=('--cmd', bootstrap))
    try:
        for index in range(4):
            file = root / f'document-{index}.txt'
            file.write_text('Document content\n')
            editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
        editor.lua('vim.g.ide_git_autofetch=false;require("config.ide").git_explorer()')
        editor.wait(lambda: editor.lua('local f=require("config.git").inputs[...];return f and f.win', str(root)), 'Commit input appears')
        editor.lua('vim.api.nvim_set_current_win(require("config.ide").editor_window());require("config.editor_tabs").draw()')
        background = editor.lua('return vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg')

        def check_colors():
            actual = editor.lua('local s=vim.api.nvim_get_hl(0,{name="DesktopTabSeparator",link=false});return {fg=s.fg,bg=s.bg}')
            assert actual == {'fg': background, 'bg': background}, (actual, background)

        field = editor.lua('local f=require("config.git").inputs[...];local p=vim.api.nvim_win_get_position(f.win);return {p[1],p[2]+1}', str(root))
        editor.click(*field)
        editor.wait(lambda: editor.lua('return vim.bo.filetype=="ide_git_message" and vim.fn.mode()=="i"'), 'Click focuses the commit input')
        editor.call('nvim_input', 'Draft message')
        editor.wait(lambda: editor.lua('return require("config.git").messages[...]', str(root)) == 'Draft message', 'Draft text is stored')
        editor.lua('require("config.editor_tabs").draw()')
        assert editor.lua('return vim.api.nvim_get_hl(0,{name="Normal",link=false}).bg') != background, 'Commit input uses its own background'
        check_colors()
        strip = editor.lua('return vim.api.nvim_win_get_position(require("config.editor_tabs").win)')
        for direction in ('down', 'up'):
            first = editor.lua('return require("config.editor_tabs").first')
            editor.call('nvim_input_mouse', 'wheel', direction, '', 0, strip[0], strip[1]+5)
            editor.wait(lambda: editor.lua('return require("config.editor_tabs").first') != first, 'Tab wheel redraw completes')
            check_colors()
            assert editor.lua('return vim.bo.filetype=="ide_git_message" and vim.fn.mode()=="i"'), 'Scrolling tabs preserves commit input focus'
        editor.lua('vim.cmd("stopinsert");vim.api.nvim_set_current_win(require("config.ide").editor_window());require("config.editor_tabs").draw()')
        check_colors()
        assert editor.lua('return require("config.git").messages[...]', str(root)) == 'Draft message'
        print('PASS: editor-colored tab separators stay stable during commit input typing, tab wheel redraws, and return to the editor; draft/focus preserved.')
    finally:
        editor.close()
