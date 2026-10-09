-- The Tabs source contains document tabs only; terminals have their own list.
local M = { name = "buffers", display_name = "Tabs",
  default_config = { renderers = { document = { { "document" } }, message = { { "document" } } } } }
M.components = vim.tbl_extend("force", require("neo-tree.sources.common.components"), {
  document = function(_, node)
    return { text = " " .. node.name, highlight = node.type == "message" and "Comment" or "NeoTreeFileName" }
  end,
})
M.commands = {
  open = function(state)
    local node = state.tree and state.tree:get_node()
    if node and node.extra and node.extra.bufnr then require("config.ide").open_file(nil, node.extra.bufnr) end
  end,
  buffer_delete = function(state)
    local node = state.tree and state.tree:get_node()
    if node and node.extra and node.extra.bufnr then require("config.ide").close_buffer(node.extra.bufnr) end
  end,
  refresh = function() require("neo-tree.sources.manager").refresh("buffers") end,
}
require("neo-tree.sources.common.commands")._add_common_commands(M.commands)
function M.navigate(state, path, _, callback)
  state.path, state.dirty = path or require("config.ide").root(), false
  local buffers, nodes = {}, {}
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[buf].buflisted and (vim.bo[buf].buftype == "" or vim.b[buf].ide_diff_file)
      and not vim.b[buf].ide_diff_before then buffers[#buffers + 1] = buf end
  end
  table.sort(buffers, function(a,b) return require("config.tabs").compare({ id = a }, { id = b }) end)
  for _, buf in ipairs(buffers) do
    local path = vim.b[buf].ide_diff_file or vim.api.nvim_buf_get_name(buf)
    local name = path == "" and "Untitled" or vim.fn.fnamemodify(path, ":~:.")
    if vim.b[buf].ide_diff_file then name = name .. " (diff)" end
    if vim.bo[buf].modified then name = name .. " ●" end
    nodes[#nodes + 1] = { id = tostring(buf), name = name, type = "document", extra = { bufnr = buf } }
  end
  if #nodes == 0 then nodes[1] = { id = "empty", name = "No open documents", type = "message" } end
  require("neo-tree.ui.renderer").show_nodes(nodes, state, nil, callback)
end
function M.setup()
  local group = vim.api.nvim_create_augroup("DesktopDocumentList", { clear = true })
  local pending = false
  vim.api.nvim_create_autocmd({ "BufAdd", "BufDelete", "BufEnter", "BufModifiedSet", "BufFilePost" }, {
    group = group, callback = function()
      if pending then return end
      pending = true
      vim.defer_fn(function()
        pending = false
        local state = require("neo-tree.sources.manager").get_state("buffers")
        if state.winid and vim.api.nvim_win_is_valid(state.winid)
          and vim.api.nvim_win_get_buf(state.winid) == state.bufnr then M.navigate(state) end
      end, 80)
    end,
  })
end
return M
