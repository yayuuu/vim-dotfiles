local M = { name = "git_status", display_name = "Git" }
M.default_config = {
  renderers = {
    directory = { { "git_directory" } }, git_section = { { "git_section" } },
    file = { { "git_file" } }, git_commit = { { "git_text" } }, git_commit_action = { { "git_text" } },
    git_header_spacer = { { "git_text" } },
  },
}
M.components = vim.tbl_extend("force", require("neo-tree.sources.git_status.components"), {
  git_directory = function(...) return require("config.git").directory(...) end,
  git_section = function(_, node)
    return { text = node.name, highlight = "NeoTreeRootName" }
  end,
  git_text = function(_, node) return { text = node.name, highlight = "Comment" } end,
  git_file = function(_, node)
    local status = node.extra.status
    local hl = (status == "?" or status == "A") and "GitSignsAdd" or status == "D" and "GitSignsDelete" or "GitSignsChange"
    return { text = status .. " " .. node.name, highlight = hl }
  end,
})
M.commands = vim.tbl_extend("force", require("neo-tree.sources.git_status.commands"), {
  open = function(state) require("config.git").open(state) end,
  refresh = function() require("config.git").refresh() end,
})

function M.parse(text, root)
  local records = vim.split(text, "\0", { plain = true, trimempty = true })
  local staged, changes, i = {}, {}, 1
  while i <= #records do
    local record = records[i]
    local x, y, relative = record:sub(1, 1), record:sub(2, 2), record:sub(4)
    local old
    if x == "R" or x == "C" or y == "R" or y == "C" then i = i + 1; old = records[i] end
    local function add(list, section, status)
      local path = root .. "/" .. relative
      list[#list + 1] = { id = section == "staged" and path .. "::staged" or path,
        path = path, name = relative, type = "file", ext = vim.fn.fnamemodify(relative, ":e"),
        extra = { section = section, status = status, original = old, relative = relative } }
    end
    if x ~= " " and x ~= "?" and x ~= "!" then add(staged, "staged", x) end
    if y ~= " " and y ~= "!" then add(changes, "changes", y) end
    i = i + 1
  end
  for _, list in ipairs({ staged, changes }) do table.sort(list, function(a, b) return a.name < b.name end) end
  return staged, changes
end

function M.navigate(state, path, reveal, callback)
  state.path = path or state.path or require("config.ide").root()
  state.dirty = false
  state.ide_scan = (state.ide_scan or 0) + 1
  local generation = state.ide_scan
  local repo = vim.system({ "git", "-C", state.path, "rev-parse", "--show-toplevel" }, { text = true }):wait()
  if repo.code ~= 0 then
    require("neo-tree.ui.renderer").show_nodes({ { id = "no-repository", type = "message", name = "Not a Git repository" } }, state)
    return
  end
  local root = vim.trim(repo.stdout)
  state.path = root
  vim.system({ "git", "-C", root, "status", "--porcelain=v1", "-z", "--untracked-files=all" }, function(result)
    vim.schedule(function()
      if state.ide_scan ~= generation then return end
      if result.code ~= 0 then vim.notify(result.stderr, vim.log.levels.ERROR); return end
      local staged, changes = M.parse(result.stdout, root)
      local index_id, working_id = root .. "::staged", root .. "::changes"
      local nodes = { { id = root, path = root, name = vim.fn.fnamemodify(root, ":~"), type = "directory", loaded = true,
        children = {
          { id = root .. "::message", path = root, name = "Commit message…", type = "git_commit" },
          { id = root .. "::commit", path = root, name = "[Commit staged changes]", type = "git_commit_action" },
          { id = root .. "::header-spacer", path = root, name = "", type = "git_header_spacer" },
          { id = index_id, path = root, name = "Staged Changes (" .. #staged .. ")", type = "git_section",
            extra = { section = "staged" }, children = staged },
          { id = working_id, path = root, name = "Changes (" .. #changes .. ")", type = "git_section",
            extra = { section = "changes" }, children = changes },
        } } }
      state.default_expanded_nodes = (not state.tree or not state.tree:get_node(root))
        and { root, index_id, working_id } or nil
      require("neo-tree.ui.renderer").show_nodes(nodes, state, nil, callback)
      if reveal then require("neo-tree.ui.renderer").focus_node(state, reveal) end
    end)
  end)
end
M.setup = require("neo-tree.sources.git_status").setup
return M
