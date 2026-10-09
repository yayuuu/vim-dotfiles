-- Keep the shared source selector while the debugger owns the panes below it.
local M = { name = "debug", display_name = "Debug",
  default_config = { renderers = { message = { { "debug_status" } } } } }
M.components = vim.tbl_extend("force", require("neo-tree.sources.common.components"), {
  debug_status = function(_, node) return { text = " " .. node.name, highlight = "Comment" } end,
})
M.commands = { open = function() require("config.terminals").show_debug_console() end,
  refresh = function(state) M.navigate(state, state.path) end }
require("neo-tree.sources.common.commands")._add_common_commands(M.commands)
function M.navigate(state, path, _, callback)
  state.path, state.dirty = path or require("config.ide").root(), false
  local dap = package.loaded.dap
  local session = dap and dap.session()
  require("neo-tree.ui.renderer").show_nodes({ { id = "debug-status", type = "message",
    name = session and "Session: " .. (session.config.name or "Debugging") or "No active debug session" } }, state, nil, callback)
end
function M.setup() end
return M
