' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

sub init()
    m.SERVER_URL = "http://192.168.1.245:8099"
    m.BLACKLIST = ["camera-3"]

    m.modeList = m.top.findNode("modeList")
    m.loading = m.top.findNode("loading")
    m.photoIntervalList = m.top.findNode("photoIntervalList")
    m.cycleIntervalList = m.top.findNode("cycleIntervalList")

    ' Photo interval values (must match XML order)
    m.photoIntervalValues = [15, 30, 60, 120]
    ' Cycle interval values
    m.cycleIntervalValues = [3, 5, 10, 15]

    ' Load saved settings
    sec = CreateObject("roRegistrySection", "settings")
    m.savedMode = sec.Read("mode")
    if m.savedMode <> "camera" then m.savedMode = "photo"
    m.savedCamera = sec.Read("camera")
    if m.savedCamera = "" then m.savedCamera = "cycle"

    ' Restore photo interval selection
    savedPhotoInt = sec.Read("photoInterval")
    if savedPhotoInt = "" then savedPhotoInt = "30"
    photoIdx = 1 ' default to 30s
    for i = 0 to m.photoIntervalValues.count() - 1
        if m.photoIntervalValues[i].toStr() = savedPhotoInt then photoIdx = i
    end for
    m.photoIntervalList.checkedItem = photoIdx

    ' Restore cycle interval selection
    savedCycleInt = sec.Read("cycleInterval")
    if savedCycleInt = "" then savedCycleInt = "5"
    cycleIdx = 1 ' default to 5s
    for i = 0 to m.cycleIntervalValues.count() - 1
        if m.cycleIntervalValues[i].toStr() = savedCycleInt then cycleIdx = i
    end for
    m.cycleIntervalList.checkedItem = cycleIdx

    ' Mode options map
    m.options = []
    m.options.push({ mode: "photo", camera: "" })
    m.options.push({ mode: "camera", camera: "cycle" })

    ' Set initial mode selection
    if m.savedMode = "photo"
        m.modeList.checkedItem = 0
    else if m.savedCamera = "cycle"
        m.modeList.checkedItem = 1
    else
        m.modeList.checkedItem = 1
    end if

    m.modeList.setFocus(true)
    m.modeList.observeField("checkedItem", "onModeChanged")
    m.photoIntervalList.observeField("checkedItem", "onPhotoIntervalChanged")
    m.cycleIntervalList.observeField("checkedItem", "onCycleIntervalChanged")

    ' Fetch camera list
    m.loading.visible = true
    fetchCameraList()
end sub

sub fetchCameraList()
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/list?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraListResponse")
    task.request = { url: url }
    task.control = "run"
    m.cameraListTask = task
end sub

sub onCameraListResponse(event as object)
    text = event.getData()
    m.loading.visible = false
    if text = invalid or text = "" then return

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" then return

    content = m.modeList.content
    savedIdx = -1

    for each name in json
        skip = false
        for each bl in m.BLACKLIST
            if LCase(name) = LCase(bl) then skip = true
        end for
        if skip then goto nextCam

        item = content.createChild("ContentNode")
        item.title = "Camera - " + name

        opt = { mode: "camera", camera: name }
        m.options.push(opt)

        if m.savedMode = "camera" and m.savedCamera = name
            savedIdx = m.options.count() - 1
        end if

        nextCam:
    end for

    if savedIdx >= 0
        m.modeList.checkedItem = savedIdx
    end if
end sub

sub onModeChanged()
    idx = m.modeList.checkedItem
    if idx < 0 or idx >= m.options.count() then return

    opt = m.options[idx]
    sec = CreateObject("roRegistrySection", "settings")
    sec.Write("mode", opt.mode)
    sec.Write("camera", opt.camera)
    sec.Flush()
end sub

sub onPhotoIntervalChanged()
    idx = m.photoIntervalList.checkedItem
    if idx < 0 or idx >= m.photoIntervalValues.count() then return
    sec = CreateObject("roRegistrySection", "settings")
    sec.Write("photoInterval", m.photoIntervalValues[idx].toStr())
    sec.Flush()
end sub

sub onCycleIntervalChanged()
    idx = m.cycleIntervalList.checkedItem
    if idx < 0 or idx >= m.cycleIntervalValues.count() then return
    sec = CreateObject("roRegistrySection", "settings")
    sec.Write("cycleInterval", m.cycleIntervalValues[idx].toStr())
    sec.Flush()
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    return false
end function
