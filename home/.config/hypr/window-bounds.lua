local M = {}

function M.fit(window)
    if not window or not window.mapped or window.hidden or not window.floating or window.fullscreen ~= 0 then return end
    local monitor = window.monitor
    if not monitor then return end
    local scale = monitor.scale
    local width, height = monitor.width / scale, monitor.height / scale
    if monitor.transform % 2 == 1 then width, height = height, width end
    local reserved = monitor.reserved
    local border = hl.get_config("general.border_size")
    local left = math.ceil(monitor.x + reserved.left + border)
    local top = math.ceil(monitor.y + reserved.top + border)
    local right = math.floor(monitor.x + width - reserved.right - border)
    local bottom = math.floor(monitor.y + height - reserved.bottom - border)
    local size = window.size
    local w, h = math.min(size.x, right - left), math.min(size.y, bottom - top)
    if w <= 0 or h <= 0 then return end
    if size.x <= w and size.y <= h then return end
    if size.x > w or size.y > h then
        hl.dispatch(hl.dsp.window.resize({ window = window, x = w, y = h }))
        size = window.size
        if size.x > w or size.y > h then
            hl.dispatch(hl.dsp.window.set_prop({ window = window, prop = "min_size", value = "1 1" }))
            hl.dispatch(hl.dsp.window.resize({ window = window, x = w, y = h }))
            size = window.size
        end
    end
    local at = window.at
    local x = math.max(left, math.min(at.x, right - size.x))
    local y = math.max(top, math.min(at.y, bottom - size.y))
    if x ~= at.x or y ~= at.y then
        hl.dispatch(hl.dsp.window.move({ window = window, x = x, y = y }))
    end
end

if #hl.get_monitors() == 0 then return M end

hl.on("window.open", function(window)
    M.fit(window)
    hl.timer(function() M.fit(window) end, { timeout = 100, type = "oneshot" })
end)
return M
