-- Most recently selected documents come first, including comparison cards.
local M = { clock = 0, recent = {} }
function M.compare(a, b)
  local x, y = M.recent[a.id] or 0, M.recent[b.id] or 0
  return x == y and a.id < b.id or x > y
end
function M.activate(buf)
  if not vim.api.nvim_buf_is_valid(buf) or not vim.bo[buf].buflisted then return end
  if vim.bo[buf].buftype ~= "" and not vim.b[buf].ide_diff_file then return end
  M.clock = M.clock + 1; M.recent[buf] = M.clock
  if package.loaded["bufferline.state"] then require("bufferline.state").set({ custom_sort = vim.NIL }) end
  local strip = require("config.editor_tabs")
  strip.first = 1; strip.refresh()
  vim.cmd("redrawstatus")
end
function M.restore(ranks)
  local ordered = {}
  for buf, rank in pairs(ranks) do ordered[#ordered + 1] = { id = buf, rank = rank } end
  table.sort(ordered, function(a,b) return a.rank > b.rank end)
  for _, item in ipairs(ordered) do M.clock = M.clock + 1; M.recent[item.id] = M.clock end
end
function M.setup()
  vim.api.nvim_create_autocmd("BufEnter", { group = vim.api.nvim_create_augroup("DesktopRecentTabs", { clear = true }),
    callback = function(args)
      local diff, scroll = require("config.diff"), require("config.hscroll")
      if diff.busy or scroll.running or vim.api.nvim_win_get_config(0).relative ~= "" then return end
      if vim.b[args.buf].ide_diff_before or vim.w.snacks_picker_preview then return end
      M.activate(args.buf)
    end })
end
return M
