-- Keep a dragged widget's mouse events from activating controls underneath it.
local M = {}
local events = {}
for _, modifier in ipairs({ "", "S-", "C-", "A-" }) do
  for _, prefix in ipairs({ "", "2-", "3-", "4-" }) do
    for _, kind in ipairs({ "Mouse", "Drag", "Release" }) do
      events[vim.keycode("<" .. modifier .. prefix .. "Left" .. kind .. ">")] = true
    end
  end
end

function M.active() return M.owner ~= nil end
function M.blocked(key, typed) return M.active() and (events[key] or events[typed]) end
function M.claim(owner) M.owner = owner end
function M.cancel(owner)
  if M.owner == owner then M.owner = nil end
end
function M.release(owner)
  -- All on_key listeners and buffer-local release mappings must still see
  -- the capture during this event, regardless of their registration order.
  vim.schedule(function() if M.owner == owner then M.owner = nil end end)
end

return M
