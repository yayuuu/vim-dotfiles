-- Move files without replacing their buffers or discarding unsaved edits.
local M = { renamed = {} }
local api = vim.api
api.nvim_create_autocmd({ "BufWritePost", "BufWipeout" }, {
  group = api.nvim_create_augroup("DesktopFileRename", { clear = true }),
  callback = function(event) M.renamed[event.buf] = nil end,
})

local function destination(path, from, to)
  if path == from then return to end
  if path:sub(1, #from + 1) == from .. "/" then return to .. path:sub(#from + 1) end
end

local function fail(message)
  vim.notify(message, vim.log.levels.ERROR, { title = "Rename" })
end

function M.write(buf)
  local moved = M.renamed[buf]
  if moved and api.nvim_buf_get_name(buf) ~= moved.path then
    M.renamed[buf], moved = nil, nil
  end
  if not moved then vim.cmd("write"); return end
  local stat = vim.uv.fs_stat(moved.path)
  if not stat or vim.bo[buf].readonly
    or stat.dev ~= moved.stat.dev or stat.ino ~= moved.stat.ino or stat.size ~= moved.stat.size
    or not vim.deep_equal(stat.mtime, moved.stat.mtime) then
    error("Renamed file is readonly or changed on disk; reload before saving", 0)
  end
  -- :file / nvim_buf_set_name sets the "not edited" flag. Temporarily allow
  -- writing this verified destination, preserving native readonly/write checks.
  local writeany = vim.o.writeany
  vim.o.writeany = true
  local ok, err = pcall(vim.cmd, "write")
  vim.o.writeany = writeany
  if not ok then error(err, 0) end
  M.renamed[buf] = nil
end

function M.move(from, to)
  if from == to then return end
  local diff = require("config.diff")
  diff.flush()
  local moves, entries = {}, {}
  for _, buf in ipairs(api.nvim_list_bufs()) do
    if vim.bo[buf].buftype == "" then
      local name = api.nvim_buf_get_name(buf)
      local target = destination(name, from, to)
      if target then moves[#moves + 1] = { buf = buf, from = name, to = target } end
    end
  end
  for _, entry in pairs(diff.entries) do
    local target = destination(entry.path, from, to)
    if target then
      entries[#entries + 1] = { entry = entry, from = entry.path, to = target }
      for _, item in ipairs({ { entry.buf, "ide-diff://" }, { entry.before, "git-before://" } }) do
        moves[#moves + 1] = { buf = item[1], from = api.nvim_buf_get_name(item[1]), to = item[2] .. target }
      end
    end
  end
  local function validate()
    if not vim.uv.fs_lstat(from) then fail("Path does not exist: " .. from); return false end
    if vim.uv.fs_lstat(to) then fail("Destination already exists: " .. to); return false end
    local parent = vim.uv.fs_stat(vim.fs.dirname(to))
    if not parent or parent.type ~= "directory" then fail("Destination directory does not exist"); return false end
    if to:sub(1, #from + 1) == from .. "/" then fail("Cannot move a directory inside itself"); return false end
    for _, move in ipairs(moves) do
      if not api.nvim_buf_is_valid(move.buf) or api.nvim_buf_get_name(move.buf) ~= move.from then
        fail("Document changed while renaming; try again"); return false
      end
      local existing = vim.fn.bufnr(move.to)
      if existing ~= -1 and existing ~= move.buf then
        fail("Destination is already open: " .. move.to); return false
      end
    end
    return true
  end
  if not validate() then return end
  Snacks.rename.on_rename_file(from, to, function()
    -- A language server may have taken time to respond. Recheck before moving.
    if not validate() then return end
    local ok, err = vim.uv.fs_rename(from, to)
    if not ok then fail("Cannot rename: " .. tostring(err)); return end
    local renamed = {}
    local updated, update_error = pcall(function()
      for _, move in ipairs(moves) do
        api.nvim_buf_set_name(move.buf, move.to)
        renamed[#renamed + 1] = move
      end
    end)
    if not updated then
      for index = #renamed, 1, -1 do pcall(api.nvim_buf_set_name, renamed[index].buf, renamed[index].from) end
      local restored, restore_error = vim.uv.fs_rename(to, from)
      fail("Cannot update document name: " .. tostring(update_error)
        .. (restored and "" or "; cannot restore file: " .. tostring(restore_error)))
      return
    end
    for _, item in ipairs(entries) do
      diff.paths[item.from], diff.paths[item.to] = nil, item.entry.buf
      item.entry.path = item.to
      vim.b[item.entry.buf].ide_diff_file = item.to
    end
    for _, move in ipairs(moves) do
      if vim.bo[move.buf].buftype == "" then
        local stat = vim.uv.fs_stat(move.to)
        if stat and stat.type == "file" then M.renamed[move.buf] = { path = move.to, stat = stat } end
      end
    end
    local projects = require("config.projects")
    if projects.last_file then projects.last_file = destination(projects.last_file, from, to) or projects.last_file end
    projects.save()
    require("neo-tree.sources.manager").refresh("filesystem")
    require("config.git").refresh()
    require("config.editor_tabs").refresh()
    vim.cmd("redrawstatus")
  end)
end

function M.prompt(state)
  if not state and vim.bo.filetype == "neo-tree" then
    state = require("neo-tree.sources.manager").get_state_for_window(api.nvim_get_current_win())
  end
  local path
  if state then
    local node = state.tree and state.tree:get_node()
    if state.name ~= "filesystem" or not node or (node.type ~= "file" and node.type ~= "directory") then return end
    path = node:get_id()
  else
    local buf = api.nvim_win_get_buf(require("config.ide").editor_window())
    if vim.bo[buf].buftype ~= "" and not vim.b[buf].ide_diff_file then return end
    path = vim.b[buf].ide_diff_file or api.nvim_buf_get_name(buf)
  end
  if not path or path == "" then return end
  path = vim.fs.normalize(vim.fn.fnamemodify(path, ":p")):gsub("/+$", "")
  local parent = vim.fs.dirname(path)
  vim.ui.input({ prompt = "Rename: ", default = vim.fs.basename(path), completion = "file" }, function(name)
    if not name or vim.trim(name) == "" then return end
    local target = vim.fs.normalize(name:sub(1, 1) == "/" and name or parent .. "/" .. name)
    M.move(path, target)
  end)
end

return M
