"""Files follows real nested paths when the editor displays diff URI buffers."""
from pathlib import Path
import subprocess
import tempfile

from ui import Editor


with tempfile.TemporaryDirectory(prefix='nvim-diff-tree-') as directory:
    root = Path(directory)
    subprocess.run(['git', 'init', '-b', 'main', directory], check=True, stdout=subprocess.DEVNULL)
    file = root / 'lua' / 'config' / 'example.lua'
    file.parent.mkdir(parents=True)
    file.write_text('local function example()\n  return true\nend\nreturn example()\n')
    editor = Editor(root, root / 'state')
    try:
        editor.lua('require("config.diff").open(...)', str(file))
        editor.wait(lambda: editor.lua('return require("config.diff").active~=nil'), 'Nested added-file diff opens')
        sides = editor.lua('local d=require("config.diff").active;return {d.right,d.left}')
        for win in sides:
            editor.lua('vim.api.nvim_set_current_win(...);vim.cmd("stopinsert");require("config.ide").explorer()', win)
            editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s and s.name=="filesystem" and s.tree and s.tree:get_node(...)~=nil', str(file)), 'Files reveals nested document from diff')
            editor.wait(lambda: editor.lua('return not require("config.sidebar").changing and not require("config.layout").scaling'), 'Files layout settles')
            # Explicit reveal exercises the same path lookup used by automatic
            # following, including expansion/scanning of all parent folders.
            editor.lua('vim.api.nvim_set_current_win(...);require("neo-tree.command").execute({action="show",source="filesystem",reveal=true})', win)
            editor.wait(lambda: editor.lua('local s=require("config.sidebar").state();return s.tree and s.tree:get_node(...)~=nil', str(file)), 'Reveal resolves actual path instead of URI directories')
            resolved = editor.lua('return vim.api.nvim_win_call(...,function()return require("neo-tree.sources.manager").get_path_to_reveal()end)', win)
            assert resolved == str(file), resolved
        messages = editor.lua('return vim.fn.execute("messages")')
        assert 'ENOENT' not in messages and 'Neo-tree ERROR' not in messages and 'Error executing' not in messages, messages
        assert file.read_text().startswith('local function example()')
        print('PASS: Files reveals both diff sides as the real nested file; no URI parent scans or ENOENT errors.')
    finally:
        editor.close()
