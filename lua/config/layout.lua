local M = { ready = false, sizes = {}, ratios = {}, revision = 0, observed = {} }
local path = vim.fn.stdpath("state") .. "/desktop-ide-layout.json"
local roles = { ["neo-tree"] = "tree", aerial = "outline", snacks_terminal = "terminal", ide_terminal_empty = "terminal",
  ["dap-repl"] = "terminal", ide_git_history = "history", ide_terminal_list = "terminal_sessions" }

local function screen()
  local tabline = vim.o.showtabline == 2 or (vim.o.showtabline == 1 and #vim.api.nvim_list_tabpages() > 1)
  return { columns = vim.o.columns, lines = vim.o.lines,
    height = math.max(1, vim.o.lines - (tabline and 1 or 0) - (vim.o.laststatus == 3 and 1 or 0) - vim.o.cmdheight) }
end

local function same_screen()
  return M.screen and M.screen.columns == vim.o.columns and M.screen.lines == vim.o.lines
end

local function windows()
  local result = {}
  for _, win in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if vim.api.nvim_win_get_config(win).relative == "" then
      local role = roles[vim.bo[vim.api.nvim_win_get_buf(win)].filetype]
      if vim.b[vim.api.nvim_win_get_buf(win)].ide_problems then role = "terminal" end
      if role then result[role] = win end
    end
  end
  return result
end

local function history_limit(wins)
  if not wins.tree or not wins.history then return end
  -- Keep both sections and file entries below the pinned header, reserving
  -- the selector and a possible horizontal bar when restoring a tall graph.
  local info = vim.fn.getwininfo(wins.tree)[1]
  local minimum = require("config.git_header").rows + 5 + info.winbar
  return math.max(1, vim.api.nvim_win_get_height(wins.tree) + vim.api.nvim_win_get_height(wins.history) - minimum)
end

local function measure()
  local sizes = {}
  for role, win in pairs(windows()) do
    sizes[role] = (role == "tree" or role == "terminal_sessions") and vim.api.nvim_win_get_width(win) or vim.api.nvim_win_get_height(win)
  end
  return sizes
end

local function remember(initialize)
  local bounds = screen()
  for role, size in pairs(measure()) do
    M.sizes[role] = size
    if (initialize and not M.ratios[role]) or (not initialize and size ~= M.observed[role]) then
      M.ratios[role] = size / ((role == "tree" or role == "terminal_sessions") and bounds.columns or bounds.height)
    end
  end
  M.observed, M.screen = measure(), bounds
end

local function persist()
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local temporary = path .. "." .. vim.fn.getpid() .. ".tmp"
  local state = { version = 2, sizes = M.sizes, ratios = M.ratios }
  if vim.fn.writefile({ vim.json.encode(state) }, temporary) == 0 then vim.uv.fs_rename(temporary, path) end
end

function M.load()
  local ok, lines = pcall(vim.fn.readfile, path)
  if not ok then return end
  local decoded, state = pcall(vim.json.decode, table.concat(lines, "\n"))
  if not decoded or type(state) ~= "table" then return end
  -- The previous format stored cell counts directly. Keep those dimensions
  -- for the first launch, then derive proportions from the current screen.
  local sizes = type(state.sizes) == "table" and state.sizes or state
  local ratios = type(state.ratios) == "table" and state.ratios or {}
  for _, role in ipairs({ "tree", "outline", "terminal", "history", "terminal_sessions" }) do
    if type(sizes[role]) == "number" and sizes[role] >= 1 then M.sizes[role] = math.floor(sizes[role]) end
    if type(ratios[role]) == "number" and ratios[role] > 0 and ratios[role] < 1 then M.ratios[role] = ratios[role] end
  end
end

function M.apply(role)
  local wins = windows()
  local bounds = screen()
  -- Restore the sidebar first: changing its width can redistribute the bottom row.
  -- Apply the terminal list's width after that redistribution has finished.
  for _, name in ipairs({ "tree", "outline", "history", "terminal", "terminal_sessions" }) do
    local win = wins[name]
    local extent = (name == "tree" or name == "terminal_sessions") and bounds.columns or bounds.height
    local size = M.ratios[name] and math.floor(M.ratios[name] * extent + 0.5) or M.sizes[name]
    if win and size and (not role or name == role) then
      if name == "tree" or name == "terminal_sessions" then
        local width = math.max(1, math.min(math.max(18, size), extent - 10))
        if vim.api.nvim_win_get_width(win) ~= width then vim.api.nvim_win_set_width(win, width) end
      else
        local maximum = name == "history" and history_limit(wins) or extent - 4
        local height = math.max(1, math.min(math.max(4, size), maximum))
        if vim.api.nvim_win_get_height(win) ~= height then vim.api.nvim_win_set_height(win, height) end
      end
    end
  end
  -- Applying saved dimensions must not be mistaken for dragging a separator.
  M.observed = measure()
end

function M.save()
  if not M.ready then return end
  if not M.scaling and same_screen() and not vim.deep_equal(measure(), M.observed) then
    remember()
  end
  persist()
end

function M.restore()
  M.ready = false
  M.apply()
  -- Neo-tree/Aerial finish setting up their windows asynchronously. Let that
  -- settle before applying stored dimensions and accepting resize events.
  vim.defer_fn(function()
    M.apply()
    vim.schedule(function()
      remember(true)
      M.ready = true
      persist()
    end)
  end, 350)
end

function M.reflow()
  if not M.ready then M.apply(); return end
  M.scaling = true
  M.revision = M.revision + 1
  local revision = M.revision
  vim.schedule(function()
    if revision ~= M.revision then return end
    M.apply()
    M.screen = screen()
    -- Window constructors and resize callbacks can finish asynchronously.
    -- Their default dimensions must not replace the desired proportions.
    vim.defer_fn(function()
      if revision ~= M.revision then return end
      M.apply()
      M.screen = screen()
      M.scaling = false
      persist()
    end, 80)
  end)
end

function M.setup()
  M.load()
  local group = vim.api.nvim_create_augroup("DesktopIDELayout", { clear = true })
  vim.api.nvim_create_autocmd("WinResized", {
    group = group,
    callback = function()
      if not M.ready or M.scaling or not same_screen() or require("config.sidebar").changing then return end
      if vim.deep_equal(measure(), M.observed) then return end
      -- Record a manual drag now; debounce only the disk write, so a quick
      -- subsequent screen resize cannot lose the newly chosen proportions.
      remember()
      local wins = windows()
      local maximum = history_limit(wins)
      if maximum and vim.api.nvim_win_get_height(wins.history) > maximum then
        M.reflow()
        return
      end
      M.revision = M.revision + 1
      local revision = M.revision
      vim.defer_fn(function() if M.revision == revision then M.save() end end, 200)
    end,
  })
  vim.api.nvim_create_autocmd("VimResized", {
    group = group,
    callback = function()
      if M.ready then M.reflow() end
    end,
  })
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = M.save })
end

return M
