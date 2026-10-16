"""Rendered selected tabs inherit the terminal background; other cards retain fill."""
import json
from pathlib import Path
import tempfile

from ui import Editor

config = Path(__file__).resolve().parents[1]
module = config / 'lua/config/settings.lua'
palette = json.loads((config / 'palette.json').read_text())
palette['ui_background'] = 'NONE'

for main_background in ('NONE', '#102030'):
    palette['ui_background'] = main_background
    with tempfile.TemporaryDirectory(prefix='nvim-transparent-tabs-') as directory:
        root = Path(directory)
        colors = root / 'transparent.json'
        colors.write_text(json.dumps(palette))
        bootstrap = ('lua package.preload["config.settings"]=function() '
                     f'local m=dofile({json.dumps(str(module))});'
                     f'm.color_palette={json.dumps(str(colors))};return m end')
        editor = Editor(root, root / 'state', args=('--cmd', bootstrap))
        try:
            for index in range(3):
                file = root / f'document-{index}.txt'
                file.write_text('plain document\n')
                editor.lua('require("config.ide").open_file(...);vim.cmd("stopinsert")', str(file))
            modified = editor.lua('return vim.api.nvim_get_current_buf()')
            editor.lua('vim.api.nvim_buf_set_lines(0,-1,-1,false,{"unsaved change"});vim.diagnostic.set(vim.api.nvim_create_namespace("TransparentTabs"),'
                       'vim.api.nvim_get_current_buf(),{{lnum=0,col=0,severity=1,message="An error"},'
                       '{lnum=0,col=1,severity=2,message="A warning"}})')

            def check():
                editor.lua('require("config.editor_tabs").draw();vim.cmd("redraw!")')
                strip = editor.lua('local t=require("config.editor_tabs");return '
                                   '{pos=vim.api.nvim_win_get_position(t.win),width=vim.api.nvim_win_get_width(t.win),'
                                   'hits=t.hits,active=vim.api.nvim_win_get_buf(require("config.ide").editor_window())}')
                row, left = strip['pos']
                inactive = int(palette['ui_bar_background'][1:], 16)
                selected, other = 0, 0
                for hit in strip['hits']:
                    for column in range(hit['first'] - 1, hit['last']):
                        highlight = editor.highlights[editor.attributes[row][left + column]]
                        actual = highlight.get('background')
                        main = None if palette['ui_background'] == 'NONE' else int(palette['ui_background'][1:], 16)
                        expected = main if hit['id'] == strip['active'] else inactive
                        assert actual == expected, (hit, column, editor.grid[row][left + column], highlight)
                        selected += hit['id'] == strip['active']
                        other += hit['id'] != strip['active']
                assert selected and other
                covered = {column for hit in strip['hits'] for column in range(hit['first'] - 1, hit['last'])}
                end = min(max(hit['last'] for hit in strip['hits']) + 1, strip['width'])
                for column in set(range(end)) - covered:
                    actual = editor.highlights[editor.attributes[row][left + column]].get('background')
                    assert actual == main, ('Gap does not match the editor background', column, actual, main)
                last = left + strip['width'] - 1
                assert editor.highlights[editor.attributes[row][last]].get('background') == inactive, 'Unused strip remains filled'
                return strip

            strip = check()
            for _ in range(3):
                hit = next(hit for hit in strip['hits'] if hit['id'] != strip['active'])
                editor.click(strip['pos'][0], strip['pos'][1] + hit['first'] - 1)
                editor.wait(lambda: editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").editor_window())') == hit['id'], 'Clicked document is selected')
                strip = check()
            editor.call('nvim_ui_try_resize', 120, 40)
            strip = check()
            editor.lua('vim.cmd("colorscheme vscode")')
            check()
            assert editor.lua('return vim.bo[...].modified', modified)
            assert editor.lua('return vim.api.nvim_buf_get_lines(...,-2,-1,false)[1]', modified) == 'unsaved change'
            print('PASS: actual selected-tab cells and gaps match the editor background; inactive cards/fill remain opaque through clicks, resize and colorscheme reload.')
        finally:
            editor.close()
