-- A pinned search field and mode switch above grouped, asynchronous rg results.
local M = { sessions = {}, rows = 4, limit = 1000 }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopProjectSearch")
local function valid(win) return win and api.nvim_win_is_valid(win) end
local function visible(session)
  local state = session.state
  return state and state.path == session.root and valid(state.winid) and api.nvim_win_get_buf(state.winid) == state.bufnr
    and require("config.sidebar").state() == state
end

local function keep_cursor_below_header(state)
  if api.nvim_get_current_win() ~= state.winid or not valid(state.winid)
    or api.nvim_win_get_buf(state.winid) ~= state.bufnr then return end
  local cursor = api.nvim_win_get_cursor(state.winid)
  local first = math.min(api.nvim_buf_line_count(state.bufnr), vim.fn.line("w0") + M.rows)
  if cursor[1] < first then api.nvim_win_set_cursor(state.winid, { first, cursor[2] }) end
end

local function session(root)
  if not M.sessions[root] then
    M.sessions[root] = { root = root, query = "", mode = "content", files = {}, count = 0, generation = 0, dirty = false }
  end
  return M.sessions[root]
end

local function cancel(s)
  s.generation = s.generation + 1
  if s.process then s.process:kill(15); s.process = nil end
end

function M.hide()
  local header = M.header
  M.header = nil
  if not header then return end
  for _, win in ipairs({ header.input, header.win }) do if valid(win) then api.nvim_win_close(win, true) end end
  local s = M.sessions[header.root]
  if s and s.busy then cancel(s); s.busy, s.dirty = false, true end
end

local function draw(s, callback)
  if not visible(s) then return end
  local nodes = {}
  s.state.default_expanded_nodes = {}
  for row = 1, M.rows do nodes[#nodes + 1] = { id = "search-header-" .. row, name = " ", type = "message" } end
  local status = s.status or (s.query == "" and " Type to search project files" or " No matches")
  nodes[#nodes + 1] = { id = "search-summary", name = vim.trim(status), type = "message" }
  for _, file in ipairs(s.files) do
    s.state.default_expanded_nodes[#s.state.default_expanded_nodes + 1] = file.path
    local children = s.mode == "content" and file.matches or nil
    nodes[#nodes + 1] = { id = file.path, path = file.path, type = "search_file",
      name = file.relative:gsub("[\r\n]", " ") .. (children and " (" .. #children .. ")" or ""),
      extra = file.first, children = children, _is_expanded = true }
  end
  require("neo-tree.ui.renderer").show_nodes(nodes, s.state, nil, callback)
end

local function clean(text)
  return text:gsub("\r", ""):gsub("\n", " "):gsub("%z", "^@"):gsub("\t", "  ")
end

local function decoded(value)
  return value.text or (value.bytes and vim.base64.decode(value.bytes)) or ""
end

local function add_file(s, relative)
  relative = relative:gsub("^%./", "")
  local file = s.index[relative]
  if not file then
    file = { relative = relative, path = vim.fs.joinpath(s.root, relative), matches = {}, first = { line = 1, column = 1 } }
    s.index[relative] = file
    s.files[#s.files + 1] = file
  end
  return file
end

local function consume(s, record)
  if s.limited then return end
  if s.mode == "files" then
    if not vim.fn.tolower(record):find(vim.fn.tolower(s.query), 1, true) then return end
    add_file(s, record)
    s.count = s.count + 1
  else
    local ok, event = pcall(vim.json.decode, record)
    if not ok or event.type ~= "match" then return end
    local data = event.data
    local file = add_file(s, decoded(data.path))
    local match = data.submatches[1]
    if not match then return end
    local line = decoded(data.lines):gsub("[\r\n]+$", "")
    -- Keep a useful excerpt around a match even in very long/minified lines.
    local prefix = line:sub(1, match.start)
    local before = vim.fn.strcharpart(prefix, math.max(0, vim.fn.strchars(prefix) - 80))
    local selected = vim.fn.strcharpart(line:sub(match.start + 1, match["end"]), 0, 200)
    local after = vim.fn.strcharpart(line:sub(match["end"] + 1), 0, 200)
    local item = { line = data.line_number, column = match.start + 1,
      before = clean(before), match = clean(selected), after = clean(after) }
    if #file.matches == 0 then file.first = item end
    file.matches[#file.matches + 1] = { id = file.path .. "::" .. item.line, path = file.path,
      name = item.line .. ": " .. item.before .. item.match .. item.after, type = "search_match", extra = item }
    s.count = s.count + 1
  end
  if s.count >= M.limit then
    s.limited = true
    if s.process then s.process:kill(15) end
  end
end

local function run(s)
  cancel(s)
  s.files, s.index, s.count, s.limited, s.status, s.dirty, s.busy = {}, {}, 0, false, nil, false, false
  if s.query == "" then s.busy = false; draw(s); return end
  if vim.fn.executable("rg") ~= 1 then s.status = " ripgrep (rg) is required"; draw(s); return end
  local generation = s.generation
  local command = { "rg", "--hidden", "--glob", "!.git" }
  if s.mode == "files" then vim.list_extend(command, { "--files", "--null" })
  else vim.list_extend(command, { "--json", "--smart-case", "--fixed-strings", "--", s.query, "." }) end
  s.busy, s.status = true, " Searching…"
  draw(s)
  local tail, errors = "", ""
  local separator = s.mode == "files" and "\0" or "\n"
  s.process = vim.system(command, { cwd = s.root,
    stdout = function(_, chunk)
      if not chunk then return end
      vim.schedule(function()
        if generation ~= s.generation or s.limited then return end
        tail = tail .. chunk
        while true do
          local last = tail:find(separator, 1, true)
          if not last then break end
          consume(s, tail:sub(1, last - 1))
          tail = tail:sub(last + 1)
          if s.limited then tail = ""; break end
        end
      end)
    end,
    stderr = function(_, chunk) if chunk then errors = (errors .. chunk):sub(1, 4096) end end,
  }, function(result)
    vim.schedule(function()
      if generation ~= s.generation then return end
      s.process, s.busy = nil, false
      if tail ~= "" then consume(s, tail) end
      table.sort(s.files, function(a, b) return a.relative < b.relative end)
      if result.code ~= 0 and result.code ~= 1 and not s.limited then
        s.status = " Search failed: " .. clean(vim.trim(errors))
      elseif s.count == 0 then s.status = " No matches"
      elseif s.mode == "files" then s.status = (" %d%s files"):format(s.count, s.limited and "+" or "")
      else s.status = (" %d%s matching lines in %d files"):format(s.count, s.limited and "+" or "", #s.files) end
      draw(s)
    end)
  end)
end

local function update(s, value)
  if s.query == value then return end
  cancel(s)
  s.query, s.dirty = value, true
  local generation = s.generation
  vim.defer_fn(function() if s.generation == generation and visible(s) then run(s) end end, 200)
end

function M.sync(state)
  if state.name ~= "search" then return end
  local s = session(state.path)
  if not visible(s) then return end
  if M.header and (M.header.source ~= state.winid or M.header.source_buf ~= state.bufnr or M.header.root ~= s.root) then M.hide() end
  local width = api.nvim_win_get_width(state.winid)
  local config = { relative = "win", win = state.winid, row = 0, col = 0,
    width = width, height = M.rows, style = "minimal", border = "none",
    focusable = false, mouse = true, zindex = 22, noautocmd = true }
  local header = M.header
  if not header then
    local buf = api.nvim_create_buf(false, true)
    vim.bo[buf].bufhidden = "wipe"; vim.bo[buf].filetype = "ide_search_header"
    vim.b[buf].ide_panel_header = true
    header = { root = s.root, source = state.winid, source_buf = state.bufnr, buf = buf,
      win = api.nvim_open_win(buf, false, config) }
    vim.wo[header.win].winhighlight = "Normal:DesktopSearchLabel,EndOfBuffer:DesktopSearchLabel"
    M.header = header
    if not s.input_buf or not api.nvim_buf_is_valid(s.input_buf) then
      s.input_buf = api.nvim_create_buf(false, true)
      vim.bo[s.input_buf].buftype = "nofile"; vim.bo[s.input_buf].bufhidden = "hide"
      vim.bo[s.input_buf].filetype = "ide_search_input"
      vim.b[s.input_buf].ide_panel_header, vim.b[s.input_buf].ide_search_input = true, true
      vim.b[s.input_buf].completion = false
      api.nvim_buf_set_lines(s.input_buf, 0, -1, false, { s.query })
      api.nvim_buf_attach(s.input_buf, false, { on_lines = function()
        vim.schedule(function()
          if api.nvim_buf_is_valid(s.input_buf) then update(s, table.concat(api.nvim_buf_get_lines(s.input_buf, 0, -1, false), " ")) end
        end)
      end })
      vim.keymap.set({ "n", "i" }, "<CR>", function()
        vim.cmd("stopinsert")
        s.query = table.concat(api.nvim_buf_get_lines(s.input_buf, 0, -1, false), " ")
        run(s)
      end, { buffer = s.input_buf })
      vim.keymap.set("n", "<Esc>", function()
        if visible(s) then api.nvim_set_current_win(s.state.winid); keep_cursor_below_header(s.state) end
      end, { buffer = s.input_buf })
    end
    header.input = api.nvim_open_win(s.input_buf, false, { relative = "win", win = state.winid,
      row = 1, col = 1, width = math.max(1, width - 3), height = 1,
      border = "rounded", style = "minimal", zindex = 25, noautocmd = true })
    vim.wo[header.win].winbar, vim.wo[header.input].winbar = "", ""
    vim.wo[header.input].winhighlight = "Normal:NeoTreeNormal,EndOfBuffer:NeoTreeNormal,FloatBorder:FloatBorder"
  else
    api.nvim_win_set_config(header.win, config)
    api.nvim_win_set_config(header.input, { relative = "win", win = state.winid, row = 1, col = 1, width = math.max(1, width - 3) })
  end
  vim.b[state.bufnr].ide_fixed_header = M.rows
  keep_cursor_below_header(state)
  local prefix, mode = " Find in ", s.mode == "content" and "content" or "file names"
  local label = prefix .. mode .. " ⇄"
  header.toggle_first, header.toggle_last = #prefix + 1, vim.fn.strdisplaywidth(label)
  vim.bo[header.buf].modifiable = true
  local header_lines = { label }
  for _ = 2, M.rows do header_lines[#header_lines + 1] = "" end
  api.nvim_buf_set_lines(header.buf, 0, -1, false, header_lines)
  vim.bo[header.buf].modifiable = false
  api.nvim_buf_clear_namespace(header.buf, namespace, 0, -1)
  api.nvim_buf_set_extmark(header.buf, namespace, 0, #prefix, { end_col = #prefix + #mode, hl_group = "DesktopSearchMode" })
  api.nvim_buf_clear_namespace(s.input_buf, namespace, 0, -1)
  if s.query == "" then api.nvim_buf_set_extmark(s.input_buf, namespace, 0, 0,
    { virt_text = { { "Search project…", "Comment" } }, virt_text_pos = "overlay" }) end
end

function M.navigate(state, path, callback)
  state.path, state.dirty = path or require("config.ide").root(), false
  local s = session(state.path)
  s.state = state
  -- Neo-tree has not installed the source buffer until show_nodes runs.
  local nodes = {}
  for row = 1, M.rows do nodes[#nodes + 1] = { id = "search-header-" .. row, type = "message", name = " " } end
  nodes[#nodes + 1] = { id = "search-summary", type = "message", name = "Type to search project files" }
  require("neo-tree.ui.renderer").show_nodes(nodes, state, nil, function()
    if s.dirty then run(s) else draw(s, callback) end
  end)
end

function M.focus()
  if M.header and valid(M.header.input) then
    api.nvim_set_current_win(M.header.input)
    vim.cmd("startinsert!")
  end
end

function M.show()
  vim.cmd("stopinsert")
  local ide = require("config.ide")
  if ide.is_tool_tab() and valid(ide.main_editor) then api.nvim_set_current_win(ide.main_editor) end
  require("neo-tree.command").execute({ source = "search", action = "focus", dir = ide.root() })
  vim.schedule(M.focus)
end

function M.refresh()
  local state = require("config.sidebar").state()
  if state and state.name == "search" then run(session(state.path)) end
end

function M.open(node)
  if not node or (node.type ~= "search_file" and node.type ~= "search_match") then return end
  local item = node.extra
  require("config.ide").open_file(node.path)
  local win = require("config.ide").editor_window()
  local buf = api.nvim_win_get_buf(win)
  local row = math.max(1, math.min(item.line, api.nvim_buf_line_count(buf)))
  local line = api.nvim_buf_get_lines(buf, row - 1, row, false)[1] or ""
  api.nvim_win_set_cursor(win, { row, math.min(item.column - 1, #line) })
  vim.defer_fn(function()
    if valid(win) and api.nvim_get_current_win() == win and api.nvim_win_get_buf(win) == buf
      and vim.bo[buf].modifiable and not vim.bo[buf].readonly and vim.fn.mode() == "n" then
      -- Focus handlers can start Insert before queued input is consumed.
      -- A mode-independent command remains safe when that happens.
      api.nvim_feedkeys(vim.keycode("<Cmd>startinsert<CR>"), "n", false)
    end
  end, 20)
end

function M.setup()
  if M.ready then return end
  M.ready = true
  local group = api.nvim_create_augroup("DesktopProjectSearch", { clear = true })
  api.nvim_create_autocmd({ "BufWinEnter", "WinClosed", "WinResized", "VimResized" }, { group = group, callback = function()
    vim.schedule(function()
      local header = M.header
      if header and (not valid(header.source) or api.nvim_win_get_buf(header.source) ~= header.source_buf
        or not valid(header.win) or not valid(header.input)) then M.hide() end
      if M.header then M.sync(session(M.header.root).state) end
    end)
  end })
  api.nvim_create_autocmd({ "CursorMoved", "WinEnter" }, { group = group, callback = function()
    local header = M.header
    if header then keep_cursor_below_header(session(header.root).state) end
  end })
  local events = {}
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do events[vim.keycode("<" .. prefix .. "Left" .. kind .. ">")] = kind end
  end
  local dragged = false
  vim.on_key(function(key, typed)
    if require("config.mouse_capture").blocked(key, typed) then return end
    local kind = events[typed] or events[key]
    local header = M.header
    if not kind or not header then return end
    if kind == "Mouse" then dragged = false elseif kind == "Drag" then dragged = true end
    local mouse = vim.fn.getmousepos()
    if mouse.winid == header.win then
      if kind == "Release" and not dragged and mouse.winrow == 1
        and mouse.wincol >= header.toggle_first and mouse.wincol <= header.toggle_last then
        local s = session(header.root)
        s.mode = s.mode == "content" and "files" or "content"
        vim.schedule(function() if M.header == header then M.sync(s.state); run(s) end end)
      end
      return ""
    end
    if mouse.winid == header.input and kind == "Release" and not dragged then
      vim.schedule(function()
        if M.header ~= header or not valid(header.input) or vim.fn.mode():match("^[vVsS\22\19]") then return end
        api.nvim_set_current_win(header.input)
        local line = api.nvim_buf_get_lines(session(header.root).input_buf, 0, 1, false)[1] or ""
        api.nvim_win_set_cursor(header.input, { 1, math.min(math.max(0, mouse.column - 1), #line) })
        vim.cmd(mouse.column > #line and "startinsert!" or "startinsert")
      end)
    end
  end, namespace)
end

return M
