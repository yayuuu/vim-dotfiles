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
    local manager = require("neo-tree.sources.manager")
    local path_to_reveal = manager.get_path_to_reveal
    manager.get_path_to_reveal = function(...)
      -- Diff documents are named with URIs, not filesystem paths. Following
      -- those names makes Neo-tree scan nonexistent URI parent directories.
      local path = vim.b.ide_diff_file
      if path then return path end
      if vim.b.ide_diff_before then
        return api.nvim_buf_get_name(0):match("^git%-before://(.*)$")
      end
      return path_to_reveal(...)
    end
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
  if args.source ~= "search" and package.loaded["config.project_search"] then require("config.project_search").hide() end
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
    statuscolumn = "", wrap = false, list = false, winfixheight = true, winfixwidth = true, cursorline = true }) do
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

-- One row per commit, using LazyGit's parent-based lane routing and colors.
function M.paint_history()
  if not valid(M.history_win) or not M.history_rows or not api.nvim_buf_is_valid(M.history_buf) then return end
  local graph = require("config.git_graph")
  local selected
  if api.nvim_get_current_win() == M.history_win then
    local item = M.history_rows[api.nvim_win_get_cursor(M.history_win)[1]]
    selected = item and item.commit
  end
  local text, spans = {}, {}
  for row, item in ipairs(M.history_rows) do
    local chunks = graph.render(M.history_pipes[row], selected, row > 1 and M.history_rows[row - 1].commit or nil)
    local parts, marks, column = { " " }, {}, 1
    for _, chunk in ipairs(chunks) do
      parts[#parts + 1] = chunk[1]
      if chunk[2] and chunk[1] ~= " " then
        marks[#marks + 1] = { column, column + #chunk[1], chunk[2] }
      end
      column = column + #chunk[1]
    end
    parts[#parts + 1] = item.short .. item.refs .. " " .. item.msg
    marks[#marks + 1] = { column, column + #item.short, "Constant" }
    local head = item.refs:find("HEAD", 1, true)
    if head then marks[#marks + 1] = { column + #item.short + head - 1, column + #item.short + head + 3, "String" } end
    text[row], spans[row] = table.concat(parts), marks
  end
  if not vim.deep_equal(M.history_text, text) then lines(M.history_buf, text); M.history_text = text end
  local ns = api.nvim_create_namespace("DesktopCommitGraph")
  api.nvim_buf_clear_namespace(M.history_buf, ns, 0, -1)
  for row, marks in ipairs(spans) do
    for _, mark in ipairs(marks) do
      api.nvim_buf_set_extmark(M.history_buf, ns, row - 1, mark[1], { end_col = mark[2], hl_group = mark[3] })
    end
  end
end

function M.refresh_history()
  local state = M.state()
  if not state or state.name ~= "git_status" or not valid(M.history_win) then return end
  if not vim.b[M.history_buf].ide_commit_graph_tracking then
    vim.b[M.history_buf].ide_commit_graph_tracking = true
    api.nvim_create_autocmd({ "CursorMoved", "WinEnter", "WinLeave" }, { buffer = M.history_buf, callback = function()
      if M.history_paint_pending then return end
      M.history_paint_pending = true
      vim.schedule(function() M.history_paint_pending = false; M.paint_history() end)
    end })
  end
  M.history_generation = M.history_generation + 1
  local generation, root, buf = M.history_generation, require("config.ide").root(), M.history_buf
  vim.system({ "git", "-C", root, "log", "--topo-order", "--color=never", "--decorate=short",
    "--format=%H%x00%P%x00%an%x00%h%x00%d%x00%s", "-n", "300", "HEAD", "--" }, { text = true }, function(result)
    vim.schedule(function()
      if generation ~= M.history_generation or not api.nvim_buf_is_valid(buf)
        or root ~= require("config.ide").root() then return end
      local commits = {}
      if result.code == 0 then
        for _, row in ipairs(vim.split(result.stdout, "\n", { plain = true, trimempty = true })) do
          local fields = vim.split(row, "\0", { plain = true })
          if #fields == 6 then
            commits[#commits + 1] = { commit = fields[1], parents = vim.split(fields[2], " ", { trimempty = true }),
              author = fields[3], short = fields[4], refs = fields[5], text = fields[6], msg = fields[6], root = root }
          end
        end
      end
      M.commits, M.history_rows, M.history_text = commits, commits, nil
      M.history_pipes = require("config.git_graph").build(commits)
      if #commits > 0 then M.paint_history()
      else lines(buf, { result.code == 0 and " No commits yet" or " Cannot load commit history" }) end
    end)
  end)
end

function M.open_commit(row)
  vim.cmd("stopinsert")
  local item = type(row) == "table" and row or M.commits and M.commits[row or api.nvim_win_get_cursor(M.history_win)[1]]
  if item then return require("config.commit_preview").open(item) end
end

function M.history_menu(row)
  local item = M.commits and M.commits[row]
  if not item then return end
  return {
    { name = "View commit", cmd = function() M.open_commit(item) end },
    { name = "Copy commit hash", cmd = function() vim.fn.setreg("+", item.commit) end },
    { name = "separator" },
    { name = "Refresh commits", rtxt = "F5", cmd = M.refresh_history },
  }
end

local function history(tree)
  M.history_win, M.history_buf = list_window("ide_git_history",
    "%#NeoTreeRootName# Commits · HEAD%=%#NeoTreeTabActive#%@v:lua.DesktopGitHistoryRefresh@[⟳]%T", tree)
  local buf = M.history_buf
  M.commits, M.history_rows, M.history_text = {}, nil, nil
  local function open() M.open_commit() end
  vim.keymap.set("n", "<Left>", "<Nop>", { buffer = buf })
  vim.keymap.set("n", "<Right>", "<Nop>", { buffer = buf })
  vim.keymap.set({ "n", "i" }, "<CR>", open, { buffer = buf, desc = "View commit" })
  for _, key in ipairs({ "<LeftRelease>", "<2-LeftRelease>", "<3-LeftRelease>", "<4-LeftRelease>" }) do
    vim.keymap.set({ "n", "i" }, key, function()
      if require("config.mouse_capture").active() then return end
      local row = require("config.panel_mouse").row(vim.fn.getmousepos(), M.history_win)
      if not row then return end
      api.nvim_win_set_cursor(M.history_win, { row, 0 })
      open()
    end, { buffer = buf, desc = "View commit" })
  end
  vim.keymap.set("n", "<F5>", M.refresh_history, { buffer = buf })
  lines(buf, { " Loading commits…" })
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
    if api.nvim_win_get_width(tree) ~= width then api.nvim_win_set_width(tree, width) end
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
