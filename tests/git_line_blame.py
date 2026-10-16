"""Only the current line shows accurate authorship, including Insert and unsaved diffs."""
from pathlib import Path
import subprocess
import tempfile
from ui import Editor

with tempfile.TemporaryDirectory(prefix='nvim-line-blame-') as directory:
    root = Path(directory)
    repo = root / 'repo'
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT).decode().strip()
    git('init', '-b', 'main')
    git('config', 'user.name', 'Alice Example')
    git('config', 'user.email', 'alice@example.invalid')
    source = repo / 'sample file.txt'
    source.write_text('alpha\nbeta\n')
    git('add', '.')
    git('commit', '--date=2024-01-02T00:30:00+1400', '-m', 'Initial lines')
    alice = git('rev-parse', '--short=8', 'HEAD')
    source.write_text('alpha\nsecond line\n')
    git('-c', 'user.name=Bob Example', '-c', 'user.email=bob@example.invalid', 'commit', '--date=2025-03-04T23:30:00-1200', '-am', 'Update second line')
    bob = git('rev-parse', '--short=8', 'HEAD')
    editor = Editor(repo, root / 'state')
    try:
        editor.lua('require("config.ide").open_file(...)', str(source))
        main = editor.lua('return require("config.ide").main_editor')
        document = editor.lua('return vim.api.nvim_win_get_buf(...)', main)
        def marks(buf=document):
            return editor.lua('local ns=vim.api.nvim_get_namespaces().DesktopGitLineBlame;'
                              'return ns and vim.api.nvim_buf_get_extmarks(...,ns,0,-1,{details=true}) or {}', buf)
        def text(buf=document):
            return ''.join(chunk[0] for mark in marks(buf) for chunk in mark[3].get('virt_text', []))
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'i', 'Default Insert mode')
        editor.wait(lambda: alice in text() and 'Alice Example' in text() and 'Initial lines' in text(), 'First line author and commit visible in Insert mode')
        assert '2024-01-02' in text(), 'Author date uses the timezone recorded in the commit'
        assert len(marks()) == 1 and marks()[0][1] == 0
        editor.lua('vim.api.nvim_win_set_cursor(...,{2,0})', main)
        editor.wait(lambda: bob in text() and 'Bob Example' in text() and 'Update second line' in text(), 'Blame follows cursor in Insert mode')
        assert '2025-03-04' in text(), 'Date follows the blamed commit, including negative timezone offsets'
        assert len(marks()) == 1 and marks()[0][1] == 1
        editor.call('nvim_input', '<Esc>')
        editor.wait(lambda: editor.lua('return vim.fn.mode()') == 'n', 'Normal mode')
        editor.lua('vim.api.nvim_win_set_cursor(...,{1,0})', main)
        editor.wait(lambda: alice in text(), 'Blame in Normal mode')

        # Fast cursor movement must not start a new Git process for every step.
        editor.lua('_G.line_blame_queries=0;local system=vim.system;vim.system=function(command,...) '
                   'if command[1]=="git" and command[4]=="blame" then _G.line_blame_queries=_G.line_blame_queries+1 end;'
                   'return system(command,...) end;'
                   'for i=1,20 do vim.api.nvim_win_set_cursor(...,{i%2+1,0});vim.cmd("redraw!");vim.wait(10) end', main)
        assert editor.lua('return _G.line_blame_queries') == 0, 'Queries wait until cursor stops'
        editor.wait(lambda: alice in text() and marks()[0][1] == 0, 'Only latest cursor position annotated')
        editor.call('nvim_input', 'iLOCAL ')
        editor.wait(lambda: 'Uncommitted changes' in text(), 'Unsaved line is not attributed to historical author')
        assert editor.lua('return vim.bo[...].modified', document)
        assert source.read_text() == 'alpha\nsecond line\n', 'Blame does not save edits'
        assert git('status', '--porcelain') == '', 'Index and working tree unchanged'

        editor.lua('require("config.diff").open(...)', str(source))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Editable diff opens')
        proxy = editor.lua('return require("config.diff").active.buf')
        right = editor.lua('return require("config.diff").active.right')
        editor.lua('local w=...;vim.api.nvim_set_current_win(w);vim.api.nvim_win_set_cursor(w,{1,0})', right)
        editor.wait(lambda: 'Uncommitted changes' in text(proxy), 'Diff uses real file path and unsaved proxy contents')
        editor.lua('vim.api.nvim_win_set_cursor(...,{2,0})', right)
        editor.wait(lambda: bob in text(proxy), 'Unchanged diff line retains correct commit')
        editor.lua('require("config.ide").git_explorer()')
        editor.wait(lambda: not marks(proxy), 'Tool focus clears editor annotation')
        assert editor.lua('return vim.bo[...].modified', document)
        assert 'Error executing' not in editor.lua('return vim.fn.execute("messages")')
        print('PASS: current-line author/date/hash/subject in Insert and Normal; original author timezones preserved; cursor moves debounced; unsaved edits and diffs attributed correctly; files/index preserved', flush=True)
    except Exception:
        print(editor.lua('return vim.fn.execute("messages")'), flush=True)
        print(text(), flush=True)
        raise
    finally:
        editor.close()
