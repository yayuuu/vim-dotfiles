"""Restoring a tall commit graph must leave Git status and its header visible."""
import json
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-panel-layout-') as directory:
    root = Path(directory)
    repo, state = root / 'project', root / 'state'
    repo.mkdir()
    layout = state / 'nvim' / 'desktop-ide-layout.json'
    layout.parent.mkdir(parents=True)
    layout.write_text(json.dumps({'version': 2, 'sizes': {'history': 70}, 'ratios': {}}))

    def git(*args):
        subprocess.run(['git', '-C', str(repo), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    git('init', '-b', 'main')
    tracked = repo / 'tracked.txt'
    tracked.write_text('Original\n')
    git('add', '.')
    git('-c', 'user.name=UI Test', '-c', 'user.email=ui@example.invalid', 'commit', '-m', 'Baseline')
    tracked.write_text('Changed\n')
    staged = repo / 'staged_with_a_very_long_name_requiring_a_scrollbar.txt'
    staged.write_text('Staged\n')
    git('add', staged.name)
    editor = Editor(repo, state)
    try:
        editor.lua('require("config.ide").open_file(...);'
                   'vim.api.nvim_buf_set_lines(0,0,1,false,{"Unsaved document"});'
                   'require("config.ide").git_explorer()', str(tracked))
        document = editor.lua('return vim.fn.bufnr(...)', str(tracked))

        def settled():
            return editor.lua('return not require("config.sidebar").changing and not require("config.layout").scaling')

        def assert_visible():
            editor.wait(settled, 'Git layout settles')
            editor.lua('vim.cmd("redraw!")')
            tree, history = editor.lua('return {require("config.sidebar").state().winid,require("config.sidebar").history_win}')
            height = editor.lua('return require("config.hscroll").content_height(...)', tree)
            minimum = editor.lua('return require("config.git_header").rows+4')
            assert height >= minimum, ('Git status must retain visible file rows', height, minimum)
            position = editor.call('nvim_win_get_position', tree)
            width = editor.call('nvim_win_get_width', tree)
            rows = [''.join(row[position[1]:position[1] + width])
                    for row in editor.grid[position[0]:position[0] + height + 2]]
            assert any('Staged Changes' in row for row in rows), rows
            assert any('Changes (' in row for row in rows if 'Staged' not in row), rows
            assert any('tracked.txt' in row for row in rows), rows
            assert editor.lua('return vim.api.nvim_win_is_valid(...)', history)
            assert editor.call('nvim_buf_get_lines', document, 0, 1, False) == ['Unsaved document']
            return tree, history

        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.name=="git_status" and '
                                      's.tree and s.tree:get_node(...)~=nil', str(tracked)), 'Changed file is listed')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and '
                                      'require("config.hscroll").bars[s.winid]~=nil'), 'Git status horizontal scrollbar')
        assert_visible()
        for width, height in ((200, 100), (128, 30), (160, 48)):
            editor.call('nvim_ui_try_resize', width, height)
            _, history = assert_visible()
            if height == 100:
                assert editor.call('nvim_win_get_height', history) == 70, 'Enlarging restores the chosen graph height'

        _, history = assert_visible()
        previous_ratio = editor.lua('return require("config.layout").ratios.history')
        editor.call('nvim_win_set_height', history, editor.call('nvim_win_get_height', history) + 5)
        editor.wait(lambda: editor.lua('return require("config.layout").ratios.history') != previous_ratio,
                    'Resizing the graph updates the preferred proportion')
        assert_visible()
        editor.lua('require("config.ide").explorer();require("config.ide").git_explorer()')
        assert_visible()
        print('PASS: oversized saved/resized commit graph preserves Git status, staged/working files and unsaved text; enlargement restores the preferred height and source switches retain the layout.')
    finally:
        editor.close()
