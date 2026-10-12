"""Keep bundled parsers visible and avoid duplicate Mason installations."""
from pathlib import Path
import tempfile
import time
from ui import Editor

with tempfile.TemporaryDirectory(prefix="nvim-bootstrap-") as directory:
    root = Path(directory)
    source = root / "sample.lua"
    source.write_text("local function example()\n  return true\nend\nreturn example()\n")
    editor = Editor(root, root / "state")
    try:
        tools = editor.lua('local p=require("lazy.core.config").plugins["mason.nvim"]; '
                           'return require("lazy.core.plugin").values(p,"opts",false).ensure_installed')
        assert len(tools) == len(set(tools)), tools
        assert {"lua-language-server", "debugpy", "codelldb"}.issubset(tools), tools
        paths = editor.lua('return require("lazy.core.config").options.performance.rtp.paths')
        for path in paths:
            assert editor.lua('return vim.tbl_contains(vim.opt.rtp:get(), ...)', path), path
        editor.lua('require("config.ide").open_file(...)', str(source))
        assert editor.lua('return vim.treesitter.get_parser(vim.fn.bufnr(...), "lua"):parse()[1]:root():has_error()',
                          str(source)) is False
        time.sleep(.3)
        messages = editor.lua('return vim.fn.execute("messages")')
        assert "Parser could not be created" not in messages, messages
        assert "Package is already installing" not in messages, messages
    finally:
        editor.close()
    print("PASS: unique Mason tools, preserved native parser paths, Lua file opens and parses")
