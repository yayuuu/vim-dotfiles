-- User-facing switches live in settings.json; plugin integration stays in Lua.
local M = {}

function M.read(path)
  if vim.fn.filereadable(path) == 0 then return { icons = true } end
  local ok, settings = pcall(function()
    return vim.json.decode(table.concat(vim.fn.readfile(path), "\n"))
  end)
  if not ok or type(settings) ~= "table" or type(settings.icons) ~= "boolean" then
    vim.schedule(function()
      vim.notify("Invalid settings.json: icons must be true or false. Using icons.", vim.log.levels.WARN)
    end)
    return { icons = true }
  end
  return { icons = settings.icons }
end

M.icons = M.read(vim.fn.stdpath("config") .. "/settings.json").icons
return M
