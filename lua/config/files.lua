-- File actions keep keyboard focus in Files while displaying the document.
local M = {}
local api, uv = vim.api, vim.uv

local function selected(state)
  local node = state and state.name == "filesystem" and state.tree and state.tree:get_node()
  if node and (node.type == "file" or node.type == "directory") then return node end
end

local function focus(state)
  if state.winid and api.nvim_win_is_valid(state.winid)
    and api.nvim_win_get_buf(state.winid) == state.bufnr then
    api.nvim_set_current_win(state.winid)
    vim.cmd("stopinsert")
  end
end

function M.open(state)
  if not selected(state) then return end
  require("neo-tree.sources.filesystem.commands").open(state)
  focus(state)
end

function M.copy(state)
  if not selected(state) then return end
  local commands = require("neo-tree.sources.filesystem.commands")
  -- Ctrl+C replaces the file clipboard; pressing it twice still copies.
  commands.clear_clipboard(state)
  commands.copy_to_clipboard(state)
end

function M.paste(state)
  local node = selected(state)
  if not node then return end
  local folder = node.type == "directory" and node.path or vim.fs.dirname(node.path)
  local actions = require("neo-tree.sources.filesystem.lib.fs_actions")
  for _, item in pairs(state.clipboard or {}) do
    -- Preserve Neo-tree's existing cut/move behavior for its native mappings.
    if item.action ~= "copy" then
      require("neo-tree.sources.filesystem.commands").paste_from_clipboard(state)
      return
    end
  end
  for _, item in pairs(state.clipboard or {}) do
    local source, name = item.node.path, item.node.name
    local source_stat = uv.fs_stat(source)
    if not source_stat then
      vim.notify("Copied file no longer exists: " .. source, vim.log.levels.ERROR)
      return
    end
    local real_source, real_folder = uv.fs_realpath(source), uv.fs_realpath(folder)
    if source_stat.type == "directory" and real_source and real_folder
      and (real_folder == real_source or real_folder:sub(1, #real_source + 1) == real_source .. "/") then
      vim.notify("Cannot copy a directory into itself", vim.log.levels.ERROR)
      return
    end
    local target = vim.fs.joinpath(folder, name)
    if uv.fs_lstat(target) then
      target = vim.fs.joinpath(folder, "Copy of " .. name)
      local number = 2
      while uv.fs_lstat(target) do
        target = vim.fs.joinpath(folder, "Copy (" .. number .. ") of " .. name)
        number = number + 1
      end
    end
    actions.copy_node(source, target, function(_, destination)
      require("neo-tree.sources.filesystem").show_new_children(state, destination)
    end, folder)
  end
end

function M.delete(state)
  local node = selected(state)
  if not node then return end
  for _, buf in ipairs(api.nvim_list_bufs()) do
    local path = vim.b[buf].ide_diff_file or api.nvim_buf_get_name(buf)
    if vim.bo[buf].modified and (path == node.path
      or node.type == "directory" and path:sub(1, #node.path + 1) == node.path .. "/") then
      vim.notify("Save or close modified documents before deleting: " .. node.path, vim.log.levels.WARN)
      return
    end
  end
  require("neo-tree.sources.filesystem.commands").delete(state)
end

return M
