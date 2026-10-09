local M = {
  name = "projects", display_name = "Projects",
  default_config = {
    renderers = { project = { { "project_name" } }, message = { { "project_name" } } },
    window = { mappings = {
      ["a"] = "none", ["A"] = "none", ["d"] = "none", ["r"] = "none",
      ["y"] = "none", ["x"] = "none", ["p"] = "none", ["c"] = "none", ["m"] = "none",
      ["s"] = "open", ["S"] = "open", ["t"] = "open", ["P"] = "none", ["<space>"] = "open",
    } },
  },
}
M.components = vim.tbl_extend("force", require("neo-tree.sources.common.components"), {
  project_name = function(_, node)
    return { text = " " .. node.name, highlight = node.type == "project" and "NeoTreeDirectoryName" or "Comment" }
  end,
})
M.commands = {
  open = function(state)
    local node = state.tree and state.tree:get_node()
    if node and node.type == "project" then require("config.ide").open_project(node.path) end
  end,
  refresh = function() require("neo-tree.sources.manager").refresh("projects") end,
}
require("neo-tree.sources.common.commands")._add_common_commands(M.commands)
function M.navigate(state, _, _, callback)
  local nodes = {}
  for _, project in ipairs(require("config.projects").list()) do
    nodes[#nodes + 1] = { id = project.path, path = project.path, name = vim.fn.fnamemodify(project.path, ":~"), type = "project" }
  end
  if #nodes == 0 then nodes[1] = { id = "empty", name = "No recent projects", type = "message" } end
  state.dirty = false
  require("neo-tree.ui.renderer").show_nodes(nodes, state, nil, callback)
end
function M.setup() end
return M
