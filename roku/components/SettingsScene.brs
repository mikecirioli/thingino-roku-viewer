' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

sub init()
    m.DEFAULT_SERVER_URL = ""

    m.urlLabel = m.top.findNode("urlLabel")
    m.editUrlBtn = m.top.findNode("editUrlBtn")
    m.modeList = m.top.findNode("modeList")
    m.loading = m.top.findNode("loading")
    m.photoIntervalList = m.top.findNode("photoIntervalList")
    m.cycleIntervalList = m.top.findNode("cycleIntervalList")

    m.photoIntervalValues = [15, 30, 60, 120]
    m.cycleIntervalValues = [3, 5, 10, 15]

    m.pendingInfoCount = 0
    m.cameraInfoMap = {}

    ' Load saved settings
    sec = CreateObject("roRegistrySection", "settings")

    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL
    m.urlLabel.text = m.SERVER_URL

    m.savedMode = sec.Read("mode")
    if m.savedMode <> "camera" and m.savedMode <> "video" then m.savedMode = "photo"
    m.savedCamera = sec.Read("camera")
    if m.savedCamera = "" then m.savedCamera = "cycle"

    ' Restore photo interval
    savedPhotoInt = sec.Read("photoInterval")
    if savedPhotoInt = "" then savedPhotoInt = "30"
    photoIdx = 1
    for i = 0 to m.photoIntervalValues.count() - 1
        if m.photoIntervalValues[i].toStr() = savedPhotoInt then photoIdx = i
    end for
    m.photoIntervalList.checkedItem = photoIdx

    ' Restore cycle interval
    savedCycleInt = sec.Read("cycleInterval")
    if savedCycleInt = "" then savedCycleInt = "5"
    cycleIdx = 1
    for i = 0 to m.cycleIntervalValues.count() - 1
        if m.cycleIntervalValues[i].toStr() = savedCycleInt then cycleIdx = i
    end for
    m.cycleIntervalList.checkedItem = cycleIdx

    ' Mode options
    m.options = []
    m.options.push({ mode: "photo", camera: "" })
    m.options.push({ mode: "camera", camera: "cycle" })

    if m.savedMode = "photo"
        m.modeList.checkedItem = 0
    else if m.savedCamera = "cycle"
        m.modeList.checkedItem = 1
    else
        m.modeList.checkedItem = 1
    end if

    m.editUrlBtn.setFocus(true)
    m.editUrlBtn.observeField("buttonSelected", "onEditUrl")
    m.modeList.observeField("checkedItem", "onModeChanged")
    m.photoIntervalList.observeField("checkedItem", "onPhotoIntervalChanged")
    m.cycleIntervalList.observeField("checkedItem", "onCycleIntervalChanged")

    ' Fetch camera list
    m.loading.visible = true
    fetchCameraList()
end sub

' -- Server URL editing --

sub onEditUrl()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Server URL"
    dialog.text = m.SERVER_URL
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onUrlDialogButton")
    m.top.dialog = dialog
end sub

sub onUrlDialogButton(event as object)
    idx = event.getData()
    dialog = m.top.dialog
    if idx = 0
        ' OK pressed — save the URL
        newUrl = dialog.text
        if newUrl <> "" and newUrl <> m.SERVER_URL
            m.SERVER_URL = newUrl
            m.urlLabel.text = newUrl
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("serverUrl", newUrl)
            sec.Flush()
            ' Re-fetch camera list with new URL
            m.loading.visible = true
            m.loading.text = "Loading cameras..."
            clearCameraOptions()
            fetchCameraList()
        end if
    end if
    m.top.dialog = invalid
end sub

sub clearCameraOptions()
    ' Reset mode list to just the two base options
    content = m.modeList.content
    while content.getChildCount() > 2
        content.removeChildIndex(content.getChildCount() - 1)
    end while
    m.options = []
    m.options.push({ mode: "photo", camera: "" })
    m.options.push({ mode: "camera", camera: "cycle" })
    m.filteredCamNames = []
    m.cameraInfoMap = {}
end sub

' -- Camera list --

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
        m.loading.text = "Could not reach server"
        m.loading.visible = true
        return
    end if

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" then
        m.loading.visible = false
        return
    end if

    m.filteredCamNames = []
    for each name in json
        m.filteredCamNames.push(name)
    end for

    ' Add snapshot camera options
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

' -- Setting changes --

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
