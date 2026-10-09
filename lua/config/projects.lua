local M = { restoring = true }
M.path = vim.fn.stdpath("state") .. "/desktop-ide-projects.json"

function M.normalize(path)
  if type(path) ~= "string" or path == "" then return end
  path = vim.fs.normalize(vim.fn.fnamemodify(vim.fn.expand(path), ":p"))
  path = vim.uv.fs_realpath(path) or path
  return path == "/" and path or path:gsub("/+$", "")
end

local function read()
  local ok, lines = pcall(vim.fn.readfile, M.path)
  if not ok then return { version = 1, projects = {} } end
  local valid, data = pcall(vim.json.decode, table.concat(lines, "\n"))
  if valid and type(data) == "table" and type(data.projects) == "table" then return data end
  return { version = 1, projects = {} }
end

local function write(data)
  vim.fn.mkdir(vim.fs.dirname(M.path), "p")
  local temporary = M.path .. "." .. vim.fn.getpid() .. ".tmp"
  local ok, err = pcall(function()
    assert(vim.fn.writefile({ vim.json.encode(data) }, temporary) == 0)
    assert(vim.uv.fs_rename(temporary, M.path))
  end)
  if not ok then vim.notify("Cannot save project history: " .. tostring(err), vim.log.levels.ERROR) end
  return ok
end

function M.list()
  local result, seen = {}, {}
  local home = M.normalize(vim.env.HOME)
  for _, project in ipairs(read().projects) do
    if type(project) == "table" then
      local path = M.normalize(project.path)
      if path and path ~= home and not seen[path] then
        project.path = path
        result[#result + 1], seen[path] = project, true
      end
    end
  end
  return result
end

function M.record(path)
  path = M.normalize(path)
  if not path or path == M.normalize(vim.env.HOME) or vim.fn.isdirectory(path) == 0 then return end
  local entries, chosen, others = M.list(), nil, {}
  for _, project in ipairs(entries) do
    if project.path == path then chosen = project else others[#others + 1] = project end
  end
  table.insert(others, 1, chosen or { path = path })
  write({ version = 1, projects = others })
end

local function file_buffer(buf)
  return vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].buflisted and vim.bo[buf].buftype == ""
    and vim.api.nvim_buf_get_name(buf) ~= "" and vim.fn.isdirectory(vim.api.nvim_buf_get_name(buf)) == 0
end

local function ordered_buffers()
  local buffers, seen = {}, {}
  if package.loaded.bufferline then
    for _, item in ipairs(require("bufferline").get_elements().elements) do
      if file_buffer(item.id) then buffers[#buffers + 1], seen[item.id] = item.id, true end
    end
  end
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if file_buffer(buf) and not seen[buf] then buffers[#buffers + 1] = buf end
  end
  return buffers
end

function M.save()
  if M.restoring or not M.active or M.active == M.normalize(vim.env.HOME) then return end
  local files, active = {}, M.last_file
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local buf = vim.api.nvim_win_get_buf(win)
    if file_buffer(buf) then vim.b[buf].ide_project_cursor = vim.api.nvim_win_get_cursor(win) end
  end
  for _, buf in ipairs(ordered_buffers()) do
    local owner = vim.b[buf].ide_project_owner
    if not owner then owner = M.active; vim.b[buf].ide_project_owner = owner end
    if owner == M.active then
      local path = M.normalize(vim.api.nvim_buf_get_name(buf))
      files[#files + 1] = { path = path, cursor = vim.b[buf].ide_project_cursor or { 1, 0 } }
      if buf == vim.api.nvim_get_current_buf() then active = path end
    end
  end
  local data = { version = 1, projects = M.list() }
  for _, project in ipairs(data.projects) do
    if project.path == M.active then
      project.session = { files = files, active = active }
      write(data)
      return
    end
  end
end

function M.begin(path)
  M.save()
  M.restoring = true
  -- Keep modified buffers listed and loaded so switching never loses edits.
  -- Clean tabs from the previous project remain in memory, but leave the strip.
  for _, buf in ipairs(ordered_buffers()) do
    if not vim.bo[buf].modified then vim.bo[buf].buflisted = false end
  end
  M.active, M.last_file = M.normalize(path), nil
  M.record(M.active)
end

function M.restore(editor, preferred)
  M.restoring = true
  local session
  for _, project in ipairs(M.list()) do
    if project.path == M.active then session = project.session; break end
  end
  local selected, ranks, rank = nil, {}, 0
  if type(session) == "table" and type(session.files) == "table" then
    for _, file in ipairs(session.files) do
      if type(file) == "table" and type(file.path) == "string" then
        local stat = vim.uv.fs_stat(file.path)
        if stat and stat.type == "file" then
          local buf = vim.fn.bufadd(file.path)
          vim.fn.bufload(buf)
          vim.bo[buf].buflisted = true
          vim.b[buf].ide_project_owner = M.active
          rank = rank + 1
          ranks[buf] = rank
          if type(file.cursor) == "table" then vim.b[buf].ide_project_cursor = file.cursor end
          selected = selected or buf
          if file.path == session.active then selected = buf end
        end
      end
    end
  end
  if preferred and file_buffer(preferred) then selected = preferred end
  require("config.tabs").restore(ranks)
  if selected then
    vim.api.nvim_set_current_win(editor)
    require("config.ide").open_file(nil, selected)
    local cursor = vim.b[selected].ide_project_cursor
    if type(cursor) == "table" and type(cursor[1]) == "number" and type(cursor[2]) == "number" then
      local line = math.max(1, math.min(cursor[1], vim.api.nvim_buf_line_count(selected)))
      local text = vim.api.nvim_buf_get_lines(selected, line - 1, line, false)[1] or ""
      vim.api.nvim_win_set_cursor(editor, { line, math.max(0, math.min(cursor[2], #text)) })
    end
    M.last_file = M.normalize(vim.api.nvim_buf_get_name(selected))
  end
  if _G.nvim_bufferline then pcall(_G.nvim_bufferline) end
  -- Hiding a terminal or changing sidebar source can briefly refocus the
  -- old editor, whose BufEnter handler lists its file again.
  for _, buf in ipairs(ordered_buffers()) do
    if vim.b[buf].ide_project_owner and vim.b[buf].ide_project_owner ~= M.active
      and not vim.bo[buf].modified then vim.bo[buf].buflisted = false end
  end
  M.restoring = false
  require("config.ide").discard_empty_buffers()
end

function M.setup()
  local argument = vim.fn.argv(0)
  M.start_dir = M.normalize(type(argument) == "string" and vim.fn.isdirectory(argument) == 1 and argument or vim.fn.getcwd())
  M.active = M.start_dir
  M.record(M.active)
  local group = vim.api.nvim_create_augroup("DesktopIDEProjects", { clear = true })
  local generation = 0
  vim.api.nvim_create_autocmd({ "BufEnter", "BufLeave", "BufAdd", "BufDelete", "BufFilePost" }, {
    group = group,
    callback = function(event)
      if M.restoring then return end
      if file_buffer(event.buf) then
        if not vim.b[event.buf].ide_project_owner then vim.b[event.buf].ide_project_owner = M.active end
        if vim.api.nvim_get_current_buf() == event.buf then
          vim.b[event.buf].ide_project_cursor = vim.api.nvim_win_get_cursor(0)
          if vim.b[event.buf].ide_project_owner == M.active then M.last_file = M.normalize(vim.api.nvim_buf_get_name(event.buf)) end
        end
      end
      generation = generation + 1
      local current = generation
      vim.defer_fn(function() if current == generation then M.save() end end, 150)
    end,
  })
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = M.save })
end

return M
