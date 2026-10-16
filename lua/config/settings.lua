-- User-facing switches live in settings.json; plugin integration stays in Lua.
local M = {}

function M.read(path)
  local defaults = { icons = true, ["color-palette"] = "palette.json" }
  if vim.fn.filereadable(path) == 0 then return defaults end
  local ok, settings = pcall(function()
    return vim.json.decode(table.concat(vim.fn.readfile(path), "\n"))
  end)
  if not ok or type(settings) ~= "table" then
    vim.schedule(function()
      vim.notify("Invalid settings.json. Using default settings.", vim.log.levels.WARN)
    end)
    return defaults
  end
  for key, fallback in pairs(defaults) do
    local value = settings[key]
    if value ~= nil then
      if type(value) == type(fallback) and (type(value) ~= "string" or vim.trim(value) ~= "") then
        defaults[key] = value
      else
        vim.schedule(function()
          vim.notify("Invalid settings.json: " .. key .. ". Using its default value.", vim.log.levels.WARN)
        end)
      end
    end
  end
  return defaults
end

local settings = M.read(vim.fn.stdpath("config") .. "/settings.json")
M.icons = settings.icons
M.color_palette = settings["color-palette"]
return M
