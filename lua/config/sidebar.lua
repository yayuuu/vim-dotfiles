local M = { generation = 0, history_generation = 0 }
local api = vim.api
local function valid(win) return win and api.nvim_win_is_valid(win) end

function M.state()
  if not package.loaded["neo-tree.sources.manager"] then return end
  for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
    if vim.bo[api.nvim_win_get_buf(win)].filetype == "neo-tree" then
      return require("neo-tree.sources.manager").get_state_for_window(win), win
    end
  end
end

function M.symbols_enabled()
  local state = M.state()
  return state and state.name == "filesystem" or false
end

function M.prepare(args)
  if not M.renderer_guard then
    M.renderer_guard = true
    local function inactive(state)
      local requested = require("neo-tree.command")._last.source
      local position = state.current_position or state.window.position
      if position == "left" and requested and requested ~= state.name then
        state.dirty = true
        return true
      end
      return false
    end
    local renderer = require("neo-tree.ui.renderer")
    local show = renderer.show_nodes
    renderer.show_nodes = function(nodes, state, ...)
      -- A filesystem scan can finish after the user selects another source.
      -- Keep it dirty for the next visit instead of replacing the chosen tab.
      if inactive(state) then return end
      return show(nodes, state, ...)
    end
    local filesystem = require("neo-tree.sources.filesystem")
    local navigate = filesystem._navigate_internal
    filesystem._navigate_internal = function(state, ...)
      if inactive(state) then return end
      return navigate(state, ...)
    end
    local scan = require("neo-tree.sources.filesystem.lib.fs_scan")
    local get_items = scan.get_items
    scan.get_items = function(state, ...)
      if inactive(state) then return end
      return get_items(state, ...)
    end
  end
  if args.source == M.source then return end
  -- Save the old panel before Neo-tree replaces its buffer or Aerial applies
  -- default dimensions; those programmatic resizes aren't manual drags.
  if not M.changing then require("config.layout").save() end
  M.prepared, M.changing = true, true
  if args.source ~= "debug" and package.loaded["config.debugger"] then require("config.debugger").close() end
end

local function close_kind(filetype)
  for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
    if vim.bo[api.nvim_win_get_buf(win)].filetype == filetype then api.nvim_win_close(win, true) end
  end
end

local function list_window(filetype, title, tree)
  for _, win in ipairs(api.nvim_tabpage_list_wins(0)) do
    if vim.bo[api.nvim_win_get_buf(win)].filetype == filetype then return win, api.nvim_win_get_buf(win) end
  end
  local buf = api.nvim_create_buf(false, true)
  vim.bo[buf].buftype = "nofile"; vim.bo[buf].bufhidden = "wipe"
  vim.bo[buf].filetype = filetype; vim.bo[buf].swapfile = false
  local win = api.nvim_open_win(buf, false, { split = "below", win = tree,
    height = math.min(14, math.max(5, math.floor(vim.o.lines * 0.3))) })
  for key, value in pairs({ number = false, relativenumber = false, signcolumn = "no", foldcolumn = "0",
    statuscolumn = "", wrap = false, winfixheight = true, winfixwidth = true, cursorline = true }) do
    vim.wo[win][key] = value
  end
  vim.wo[win].winhighlight = "Normal:NeoTreeNormal,CursorLine:NeoTreeCursorLine,EndOfBuffer:NeoTreeEndOfBuffer"
  vim.wo[win].winbar = title
  return win, buf
end

local function lines(buf, text)
  vim.bo[buf].modifiable = true
  api.nvim_buf_set_lines(buf, 0, -1, false, text)
  vim.bo[buf].modifiable = false
end

-- Connections are north/east/south/west bits. Diagonals become three-cell
-- rounded turns, combining with vertical lanes instead of overwriting them.
local graph_symbols = { [1] = "│", [2] = "─", [3] = "╰", [4] = "│", [5] = "│", [6] = "╭", [7] = "├",
  [8] = "─", [9] = "╯", [10] = "─", [11] = "┴", [12] = "╮", [13] = "┤", [14] = "┬", [15] = "┼" }
local function graph_prefix(text)
  return (text:gsub("^([ *|/\\_%-]+)", function(prefix)
    local connections, nodes, width = {}, {}, #prefix
    local function connect(column, mask)
      if column < 1 then return end
      connections[column] = bit.bor(connections[column] or 0, mask)
      width = math.max(width, column)
    end
    for column = 1, #prefix do
      local char = prefix:sub(column, column)
      if char == "*" then nodes[column] = true
      elseif char == "|" then connect(column, 5)
      elseif char == "-" or char == "_" then connect(column, 10)
      elseif char == "\\" then
        connect(column - 1, 3); connect(column, 10); connect(column + 1, 12)
      elseif char == "/" then
        connect(column - 1, 6); connect(column, 10); connect(column + 1, 9)
      end
    end
    local cells = {}
    for column = 1, width do
      cells[column] = nodes[column] and "●" or graph_symbols[connections[column]] or " "
    end
    return table.concat(cells)
  end))
end

function M.refresh_history()
  local state = M.state()
  if not state or state.name ~= "git_status" or not valid(M.history_win) then return end
  M.history_generation = M.history_generation + 1
  local generation, root, buf = M.history_generation, require("config.ide").root(), M.history_buf
  vim.system({ "git", "-C", root, "log", "--graph", "--topo-order", "--color=never", "--decorate=short",
    "--format=%h%x09%d%x09%s%x09%H", "-n", "300", "HEAD", "--" }, { text = true }, function(result)
    vim.schedule(function()
      if generation ~= M.history_generation or not api.nvim_buf_is_valid(buf)
        or root ~= require("config.ide").root() then return end
      local text, commits = {}, {}
      if result.code == 0 then
        for _, row in ipairs(vim.split(vim.trim(result.stdout), "\n", { plain = true, trimempty = true })) do
          local prefix, refs, subject, hash = row:match("^(.-)\t(.-)\t(.-)\t(%x+)$")
          text[#text + 1] = prefix and (graph_prefix(prefix) .. refs .. " " .. subject) or graph_prefix(row)
          if hash then commits[#text] = { commit = hash, text = subject, msg = subject, root = root } end
        end
      else
        local repo = (result.stderr or ""):find("not a git repository", 1, true)
        text = { repo and "Not a Git repository" or "No commits yet" }
      end
      lines(buf, #text > 0 and text or { "No commits yet" })
      M.commits = commits
      local ns = api.nvim_create_namespace("DesktopCommitGraph")
      api.nvim_buf_clear_namespace(buf, ns, 0, -1)
      for row, commit in pairs(commits) do
        local first, last = text[row]:find("%x%x%x%x%x%x%x+")
        if first then api.nvim_buf_set_extmark(buf, ns, row - 1, first - 1,
          { end_col = last, hl_group = "Constant" }) end
        local head = text[row]:find("HEAD", 1, true)
        if head then api.nvim_buf_set_extmark(buf, ns, row - 1, head - 1,
          { end_col = head + 3, hl_group = "String" }) end
      end
    end)
  end)
end

local function history(tree)
  M.history_win, M.history_buf = list_window("ide_git_history",
    "%#NeoTreeRootName# Commits · HEAD%=%#NeoTreeTabActive#%@v:lua.DesktopGitHistoryRefresh@[⟳]%T", tree)
  local buf = M.history_buf
  M.commits = {}
  local function open()
    vim.cmd("stopinsert")
    local item = M.commits and M.commits[api.nvim_win_get_cursor(M.history_win)[1]]
    if item then Snacks.picker({ title = "Commit " .. item.commit:sub(1, 8), cwd = item.root,
      items = { item }, format = "git_log", preview = "git_show",
      on_change = function(picker)
        if picker.preview.win:valid() then require("config.vscroll").attach(picker.preview.win.win) end
      end,
      on_close = function(picker) require("config.vscroll").detach(picker.preview.win.win) end,
      confirm = function(picker) picker:close() end }) end
  end
  for _, key in ipairs({ "<CR>", "<LeftRelease>", "<2-LeftRelease>" }) do
    vim.keymap.set({ "n", "i" }, key, open, { buffer = buf, desc = "View commit" })
  end
  vim.keymap.set("n", "<F5>", M.refresh_history, { buffer = buf })
  lines(buf, { "Loading commits…" })
  M.refresh_history()
end

function M.update()
  if M.updating then return end
  local state, tree = M.state()
  if not state then return end
  local source = state.name
  local expected = source == "git_status" and "ide_git_history" or source == "filesystem" and "aerial"
    or source == "debug" and "debug" or nil
  if M.source == source and (not expected or (expected == "aerial" and require("aerial").is_open()
    or expected == "ide_git_history" and valid(M.history_win)
    or expected == "debug" and require("config.debugger").is_open())) then
    if M.prepared then
      M.prepared = false
      require("config.layout").reflow()
      local generation = M.generation
      vim.defer_fn(function() if generation == M.generation then M.changing = false end end, 100)
    end
    return
  end
  if not M.prepared then require("config.layout").save() end
  M.prepared = false
  M.updating, M.changing, M.source = true, true, source
  M.generation = M.generation + 1
  local generation, previous, width = M.generation, api.nvim_get_current_win(), api.nvim_win_get_width(tree)
  local ok, err = pcall(function()
    if expected ~= "aerial" then require("aerial.window").close_all() end
    if expected ~= "ide_git_history" then close_kind("ide_git_history") end
    if expected ~= "debug" and package.loaded["config.debugger"] then require("config.debugger").close() end
    if expected == "aerial" then require("config.ide").outline()
    elseif expected == "ide_git_history" then history(tree)
    elseif expected == "debug" then require("config.debugger").open(tree) end
    api.nvim_win_set_width(tree, width)
    require("config.layout").apply()
  end)
  if valid(previous) then api.nvim_set_current_win(previous) end
  M.updating = false
  -- Aerial/Neo-tree can apply their default widths after creating the split.
  -- Reflow reapplies the saved proportions after those callbacks finish.
  require("config.layout").reflow()
  vim.defer_fn(function() if generation == M.generation then M.changing = false end end, 100)
  if not ok then vim.notify(err, vim.log.levels.ERROR) end
end

function M.schedule()
  if M.pending then return end
  M.pending = true
  vim.schedule(function() M.pending = false; M.update() end)
end

function M.setup()
  _G.DesktopGitHistoryRefresh = function() vim.schedule(M.refresh_history) end
  local group = api.nvim_create_augroup("DesktopSidebarSections", { clear = true })
  api.nvim_create_autocmd({ "FocusGained", "TermLeave", "ShellCmdPost" }, { group = group,
    callback = function() vim.schedule(M.refresh_history) end })
end
return M
