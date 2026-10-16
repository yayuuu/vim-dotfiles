-- One debounced blame annotation, including Insert mode and editable diff buffers.
local M = { generation = 0, cache = {} }
local api = vim.api
local namespace = api.nvim_create_namespace("DesktopGitLineBlame")

local function clear()
  M.generation = M.generation + 1
  if M.process then M.process:kill(15); M.process = nil end
  if M.buffer and api.nvim_buf_is_valid(M.buffer) then api.nvim_buf_clear_namespace(M.buffer, namespace, 0, -1) end
  M.buffer = nil
end

local function context()
  local win, buf = api.nvim_get_current_win(), api.nvim_get_current_buf()
  if api.nvim_win_get_config(win).relative ~= "" or vim.b[buf].ide_diff_before
    or (vim.bo[buf].buftype ~= "" and not vim.b[buf].ide_diff_file) then return end
  local path = vim.b[buf].ide_diff_file or api.nvim_buf_get_name(buf)
  if path == "" or path:find("://", 1, true) then return end
  return { win = win, buf = buf, path = path, row = api.nvim_win_get_cursor(win)[1],
    tick = api.nvim_buf_get_changedtick(buf) }
end

local function format(output)
  local hash = output:match("^(%x+) ")
  if not hash then return end
  if hash:match("^0+$") then return "  Uncommitted changes" end
  local author = output:match("\nauthor ([^\n]+)") or ""
  local timestamp = tonumber(output:match("\nauthor%-time (%d+)"))
  local sign, hours, minutes = output:match("\nauthor%-tz ([+-])(%d%d)(%d%d)")
  local offset = sign and (tonumber(hours) * 60 + tonumber(minutes)) * 60 * (sign == "-" and -1 or 1) or 0
  -- Keep the calendar date recorded by the author, regardless of local timezone.
  local date = timestamp and os.date("!%Y-%m-%d", timestamp + offset) or "Unknown date"
  local summary = output:match("\nsummary ([^\n]+)") or ""
  local short = vim.fn.strcharpart(summary, 0, 100)
  return ("  %s · %s · %s · %s%s"):format(author, date, hash:sub(1, 8), short, #short < #summary and "…" or ""):gsub("[%c]", " ")
end

local function display(ctx, text)
  if not text then return end
  api.nvim_buf_set_extmark(ctx.buf, namespace, ctx.row - 1, 0, {
    id = 1, virt_text = { { text, "GitSignsCurrentLineBlame" } }, virt_text_pos = "eol", hl_mode = "combine",
  })
  M.buffer = ctx.buf
end

function M.schedule()
  clear()
  local ctx = context()
  if not ctx then return end
  local generation = M.generation
  vim.defer_fn(function()
    if generation ~= M.generation or not api.nvim_buf_is_valid(ctx.buf) then return end
    local cached = M.cache[ctx.buf]
    if not cached or cached.tick ~= ctx.tick or cached.path ~= ctx.path or vim.uv.now() - cached.time > 3000 then
      cached = { tick = ctx.tick, path = ctx.path, time = vim.uv.now(), rows = {} }
      M.cache[ctx.buf] = cached
    end
    if cached.rows[ctx.row] ~= nil then display(ctx, cached.rows[ctx.row] or nil); return end
    -- Supply the actual buffer snapshot so unsaved edits are never attributed
    -- to an older commit. Query only the requested line, without parsing code.
    local contents = table.concat(api.nvim_buf_get_lines(ctx.buf, 0, -1, false), "\n")
      .. (vim.bo[ctx.buf].endofline and "\n" or "")
    M.process = vim.system({ "git", "-C", vim.fs.dirname(ctx.path), "blame", "--line-porcelain",
      "-L", ctx.row .. "," .. ctx.row, "--contents", "-", "--", vim.fs.basename(ctx.path) },
      { text = true, stdin = contents, timeout = 2500 }, function(result)
        vim.schedule(function()
          if generation ~= M.generation then return end
          M.process = nil
          local current = context()
          if not current or current.win ~= ctx.win or current.buf ~= ctx.buf or current.row ~= ctx.row
            or current.tick ~= ctx.tick or current.path ~= ctx.path then return end
          local text = result.code == 0 and format(result.stdout) or nil
          cached.rows[ctx.row] = text or false
          display(ctx, text)
        end)
      end)
  end, 400)
end

function M.setup()
  local group = api.nvim_create_augroup("DesktopGitLineBlame", { clear = true })
  api.nvim_create_autocmd({ "BufEnter", "WinEnter", "CursorMoved", "CursorMovedI", "InsertEnter", "InsertLeave",
    "TextChanged", "TextChangedI", "BufWritePost", "FocusGained" }, { group = group, callback = M.schedule })
  api.nvim_create_autocmd({ "BufLeave", "WinLeave", "FocusLost", "VimLeavePre" }, { group = group, callback = clear })
  api.nvim_create_autocmd("BufWipeout", { group = group, callback = function(event) M.cache[event.buf] = nil end })
  api.nvim_create_autocmd("User", { group = group, pattern = "GitSignsUpdate", callback = function()
    M.cache = {}
    M.schedule()
  end })
  M.schedule()
end

return M
