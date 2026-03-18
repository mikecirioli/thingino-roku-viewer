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

    ' Track pending camera info requests
    m.pendingInfoCount = 0
    m.cameraInfoMap = {}  ' name -> {stream, streamType}

    ' Load saved settings
    sec = CreateObject("roRegistrySection", "settings")
    m.savedMode = sec.Read("mode")
    if m.savedMode <> "camera" and m.savedMode <> "video" then m.savedMode = "photo"
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
    if text = invalid or text = "" then
        m.loading.visible = false
        return
    end if

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" then
        m.loading.visible = false
        return
    end if

    ' Build filtered camera name list
    m.filteredCamNames = []
    for each name in json
        skip = false
        for each bl in m.BLACKLIST
            if LCase(name) = LCase(bl) then skip = true
        end for
        if not skip then m.filteredCamNames.push(name)
    end for

    ' Add snapshot camera options immediately
    content = m.modeList.content
    savedIdx = -1

    for each name in m.filteredCamNames
        item = content.createChild("ContentNode")
        item.title = "Camera - " + name

        opt = { mode: "camera", camera: name }
        m.options.push(opt)

        if m.savedMode = "camera" and m.savedCamera = name
            savedIdx = m.options.count() - 1
        end if
    end for

    if savedIdx >= 0
        m.modeList.checkedItem = savedIdx
    end if

    ' Fetch info for each camera to discover HLS streams
    m.loading.text = "Checking streams..."
    m.pendingInfoCount = m.filteredCamNames.count()
    if m.pendingInfoCount = 0 then
        m.loading.visible = false
        return
    end if

    for each name in m.filteredCamNames
        fetchCameraInfo(name)
    end for
end sub

sub fetchCameraInfo(name as string)
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + name + "/info?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraInfoResponse")
    task.request = { url: url }
    task.control = "run"
end sub

sub onCameraInfoResponse(event as object)
    text = event.getData()
    m.pendingInfoCount = m.pendingInfoCount - 1

    if text <> invalid and text <> ""
        info = ParseJSON(text)
        if info <> invalid and info.stream <> invalid and info.stream <> ""
            m.cameraInfoMap[info.name] = {
                stream: info.stream,
                streamType: info.stream_type
            }
        end if
    end if

    ' Once all info responses are back, add Live Video options
    if m.pendingInfoCount <= 0
        m.loading.visible = false
        addVideoOptions()
    end if
end sub

sub addVideoOptions()
    content = m.modeList.content
    savedIdx = -1

    for each name in m.filteredCamNames
        camInfo = m.cameraInfoMap[name]
        if camInfo <> invalid
            item = content.createChild("ContentNode")
            item.title = "Live Video - " + name

            opt = { mode: "video", camera: name }
            m.options.push(opt)

            if m.savedMode = "video" and m.savedCamera = name
                savedIdx = m.options.count() - 1
            end if
        end if
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
