--[[
PackageKit Lua 模块
===================
为 Noctalia QML 插件提供 PackageKit 查询接口。
封装 PackageKitGlib 的 Lua 绑定，暴露搜索、解析和更新查询功能。

用法:
    local pkg = require("scripts.pkg")
    local results = pkg.search("python")
    local details = pkg.resolve({"bash", "coreutils"})
    local updates = pkg.list_updates()
--]]

local lgi = require('lgi')
local PK = lgi.PackageKitGlib
local Client = PK.Client
local GLib = lgi.GLib

--- 创建一个新的 PackageKit 客户端实例
-- @return PK.Client 实例
local function new_client()
    return Client()
end

--- 将 Pk.Package 对象转为 Lua table
-- 使用 GObject 完整 getter 方法名（LGI 不自动映射缩写）
-- @param pkg Pk.Package 对象
-- @param extra table|nil 额外字段
-- @return table
local function pkg_to_table(pkg, extra)
    local t = {
        id = pkg:get_id(),
        name = pkg:get_name(),
        version = pkg:get_version(),
        arch = pkg:get_arch(),
        summary = pkg:get_summary() or "",
    }
    if extra then
        for k, v in pairs(extra) do
            t[k] = v
        end
    end
    return t
end

--- 通用的 PackageKit 异步操作封装
-- @param async_fn function(client, on_progress, on_done) 发起异步调用的函数
-- @param timeout number 超时秒数，默认 30
-- @return table 结果列表
local function collect_sync(async_fn, timeout)
    timeout = timeout or 30
    local client = new_client()
    local results = {}
    local loop = GLib.MainLoop()
    local timed_out = false

    local timeout_id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeout * 1000, function()
        timed_out = true
        pcall(function() client:cancel() end)
        loop:quit()
        return false
    end)

    local function on_done(client, result)
        if not timed_out then
            GLib.source_remove(timeout_id)
        end
        local ok, res = pcall(function()
            return client:generic_finish(result)
        end)
        if ok then
            local packages = res:get_package_array()
            for _, pkg in ipairs(packages or {}) do
                table.insert(results, pkg_to_table(pkg))
            end
        end
        loop:quit()
    end

    async_fn(client, function() end, on_done)
    loop:run()
    return results
end

--- 搜索软件包
-- @param keyword string 搜索关键词
-- @param filter string|nil 过滤条件
-- @return table 搜索结果列表
function search(keyword, filter)
    filter = filter or "none"
    return collect_sync(function(client, on_progress, on_done)
        client:search_names_async(
            PK.filter_bitfield_from_string(filter),
            {keyword},
            nil,
            on_progress,
            on_done
        )
    end)
end

--- 解析包名获取详细信息
-- @param names table 包名列表
-- @return table 包详细信息列表
function resolve(names)
    return collect_sync(function(client, on_progress, on_done)
        client:resolve_async(
            0,
            names,
            nil,
            on_progress,
            on_done
        )
    end)
end

--- 查询可用更新
-- @param filter string|nil 过滤条件
-- @return table 可用更新列表
function list_updates(filter)
    filter = filter or "none"
    return collect_sync(function(client, on_progress, on_done)
        client:get_updates_async(
            PK.filter_bitfield_from_string(filter),
            nil,
            on_progress,
            on_done
        )
    end)
end

return {
    search = search,
    resolve = resolve,
    list_updates = list_updates,
}