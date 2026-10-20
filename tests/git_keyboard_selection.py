"""Keyboard file ranges/toggles and context actions against a temporary Git index."""
from pathlib import Path
import subprocess
import tempfile
import time
from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-git-keyboard-selection-') as directory:
    root = Path(directory) / 'repo'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.STDOUT).decode().strip()
    git('init', '-b', 'main')
    git('config', 'user.name', 'UI Test')
    git('config', 'user.email', 'ui@example.invalid')
    changes = [root / f'change{i:02}.txt' for i in range(36)]
    staged = [root / f'staged{i:02}.txt' for i in range(6)]
    for path in changes + staged:
        path.write_text('baseline\n')
    git('add', '.')
    git('commit', '-m', 'Baseline')
    for path in changes + staged:
        path.write_text('modified\n')
    git('add', *(p.name for p in staged))
    # The same file in both groups must retain independent selection identities.
    staged[-1].write_text('partial working change\n')
    editor = Editor(root, Path(directory) / 'state')
    try:
        def key(keys):
            editor.call('nvim_input', keys)
            time.sleep(.1)
            editor.lua('vim.cmd("redraw!")')
        def ids(paths, suffix=''):
            return sorted(str(p) + suffix for p in paths)
        def selected():
            return sorted(editor.lua('return vim.tbl_keys(require("config.sidebar").state().ide_selected or {})'))
        def focus(id):
            editor.lua('local s=require("config.sidebar").state();local n,r=s.tree:get_node(...);'
                       'vim.api.nvim_set_current_win(s.winid);vim.cmd("stopinsert");'
                       'vim.api.nvim_win_set_cursor(s.winid,{r,0});require("config.git").select(s,n);'
                       'require("config.git").navigate_status(s,0)', id)
        def current():
            return editor.lua('return require("config.sidebar").state().tree:get_node():get_id()')
        def labels():
            return editor.lua('local b=require("config.ide").popup_buffer;return b and '
                              'vim.tbl_map(function(i)return i.name end,require("menu.state").bufs[b].items)')
        def context_action(label):
            before = selected()
            key('<S-F10>')
            editor.wait(labels, 'Keyboard context menu')
            assert selected() == before, 'Shift+F10 preserves all marked files'
            actions = [name for name in labels() if name != 'separator']
            key('<Down>' * (actions.index(label) + 1) + '<CR>')
        def index_names():
            return sorted(git('diff', '--cached', '--name-only').splitlines())
        editor.lua('require("config.ide").git_explorer();vim.cmd("stopinsert")')
        editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s.name=="git_status" '
                                       'and s.tree and s.tree:get_node(...)~=nil', str(changes[-1])), 'Git list loaded')
        status = editor.lua('return require("config.sidebar").state().winid')
        original_document = editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").main_editor)')
        terminal = editor.lua('return require("config.terminals").active')
        focus(str(changes[0]))
        key('<S-Down><S-Down>')
        assert selected() == ids(changes[:3]), selected()
        key('<S-Up>')
        assert selected() == ids(changes[:2]), selected()
        assert editor.lua('return vim.fn.mode()') == 'n'
        focus(str(changes[5]))
        key('<S-Up><S-Up>')
        assert selected() == ids(changes[3:6]), selected()
        key('<S-Down>')
        assert selected() == ids(changes[4:6]), 'Reverse range contracts at the original anchor'

        focus(str(changes[0]))
        key('<S-PageDown>')
        end = changes.index(Path(current()))
        assert end >= 2 and selected() == ids(changes[:end + 1]), selected()
        key('<S-PageUp>')
        assert selected() == ids(changes[:1]), 'PageUp contracts to the anchor'
        for _ in range(40):
            key('<S-PageDown>')
        assert selected() == ids(changes + [staged[-1]]), ('Page selection reaches the final file', current(), selected())
        point = editor.lua('local w=...;return vim.fn.screenpos(w,vim.api.nvim_win_get_cursor(w)[1],1).row', status)
        assert point > 0, 'Range endpoint scrolls into view'
        key('<Up>')
        assert not selected(), 'Plain movement clears a range'

        # Space supports disjoint marks while moving between them with arrows.
        focus(str(changes[0]))
        key('<Space><Down><Down><Space>')
        assert selected() == ids([changes[0], changes[2]]), selected()
        key('<Space>')
        assert selected() == ids(changes[:1]), 'Space removes only the focused file'
        key('<Up><Space>')
        assert selected() == ids(changes[:2]), selected()
        context_action('Stage Changes')
        editor.wait(lambda: index_names() == sorted(p.name for p in staged + changes[:2]), 'Stage processes all keyboard marks')
        assert git('show', ':' + changes[2].name) == 'baseline', 'Unselected file stays unstaged'
        editor.wait(lambda: editor.lua('return require("config.sidebar").state().tree:get_node(...)~=nil', str(changes[1]) + '::staged'), 'Index refresh')

        focus(str(staged[0]) + '::staged')
        key('<C-a>')
        assert selected() == ids(staged + changes[:2], '::staged'), 'Ctrl+A selects only Staged Changes'
        assert str(staged[-1]) not in selected(), 'Partially staged working row stays separate'
        context_action('Unstage Changes')
        editor.wait(lambda: not index_names(), 'Unstage processes the complete section selection')
        editor.wait(lambda: editor.lua('return require("config.sidebar").state().tree:get_node(...)~=nil', str(changes[0])), 'Working list refresh')

        focus(str(root) + '::changes')
        key('<C-a>')
        assert selected() == ids(changes + staged), 'Ctrl+A works on the Changes heading'
        key('<Down>')
        assert selected() == ids(changes + staged), 'Moving from heading preserves select-all'
        context_action('Stage Changes')
        editor.wait(lambda: index_names() == sorted(p.name for p in changes + staged), 'Stage processes Changes select-all')
        assert staged[-1].read_text() == 'partial working change\n'
        assert editor.lua('return vim.api.nvim_win_get_buf(require("config.ide").main_editor)') == original_document, 'Selection never opens a diff'
        assert editor.lua('return require("config.terminals").active') == terminal
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: Shift arrow/page ranges, contraction and scrolling; Space disjoint toggles; section-scoped Ctrl+A including heading/partial staging; Shift+F10 batch stage/unstage; documents and terminals preserved', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        raise
    finally:
        editor.close()
