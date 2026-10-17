-- Project search shares Neo-tree's source selector and result-list window.
local M = { name = "search", display_name = "Search", default_config = {
  renderers = { search_file = { { "search_file" } }, search_match = { { "search_match" } },
    message = { { "search_message" } } },
  window = { mappings = { ["/"] = "search_input", ["i"] = "search_input", ["<F5>"] = "refresh",
    ["<Up>"] = "select_previous", ["<Down>"] = "select_next", ["<S-Tab>"] = "toggle_mode",
    ["<Left>"] = function() end, ["<Right>"] = function() end,
    ["a"] = "none", ["A"] = "none", ["d"] = "none", ["r"] = "none", ["m"] = "none",
    ["y"] = "none", ["x"] = "none", ["p"] = "none", ["c"] = "none", ["s"] = "open",
    ["S"] = "open", ["t"] = "open", ["P"] = "none", ["<space>"] = "open" } },
} }
M.components = vim.tbl_extend("force", require("neo-tree.sources.common.components"), {
  search_file = function(_, node)
    local icon, hl = require("mini.icons").get("file", node.path)
    return { { text = icon .. " ", highlight = hl },
      { text = node.name, highlight = "NeoTreeRootName" } }
  end,
  search_match = function(_, node)
    local item = node.extra
    return { { text = "   " .. item.line .. ": ", highlight = "LineNr" },
      { text = item.before, highlight = "NeoTreeFileName" },
      { text = item.match, highlight = "Search" },
      { text = item.after, highlight = "NeoTreeFileName" } }
  end,
  search_message = function(_, node) return { text = node.name, highlight = "Comment" } end,
})
M.commands = {
  open = function(state) require("config.project_search").open(state.tree and state.tree:get_node()) end,
  refresh = function() require("config.project_search").refresh() end,
  search_input = function() require("config.project_search").focus() end,
  select_previous = function() require("config.project_search").navigate_results(-1) end,
  select_next = function() require("config.project_search").navigate_results(1) end,
  toggle_mode = function() require("config.project_search").toggle_mode() end,
}
require("neo-tree.sources.common.commands")._add_common_commands(M.commands)
function M.navigate(state, path, _, callback)
  require("config.project_search").navigate(state, path, callback)
end
function M.setup() require("config.project_search").setup() end
return M
