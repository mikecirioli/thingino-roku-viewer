' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/
'
' ============================================================
' 3 Bad Dogs — Main App Scene
' ============================================================
' Camera browser with live preview.
' Left: camera list. Right: live preview (HLS video or poster refresh).
' OK = fullscreen, Back = exit.
' D-pad = PTZ in fullscreen (for cameras with ONVIF).
' ============================================================

sub init()
    m.DEFAULT_SERVER_URL = ""

    ' Read server URL from registry (set in SettingsScene)
    sec = CreateObject("roRegistrySection", "settings")
    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL

    m.cameraList = m.top.findNode("cameraList")
    m.cameraListContent = m.top.findNode("cameraListContent")
    m.loadingLabel = m.top.findNode("loadingLabel")
    m.previewPosterA = m.top.findNode("previewPosterA")
    m.previewPosterB = m.top.findNode("previewPosterB")
    m.previewVideo = m.top.findNode("previewVideo")
    m.previewLabel = m.top.findNode("previewLabel")
    m.previewLabelGroup = m.top.findNode("previewLabelGroup")
    m.previewTimer = m.top.findNode("previewTimer")
    m.previewBg = m.top.findNode("previewBg")

    m.ptzOverlay = m.top.findNode("ptzOverlay")
    m.ptzBadge = m.top.findNode("ptzBadge")
    m.focusTrap = m.top.findNode("focusTrap")

    ' Camera data: array of {name, hasSnapshot, stream, streamType, ptz}
    m.cameras = []
    m.currentCamera = -1
    m.previewMode = "poster"

    ' Double-buffer state for poster preview
    m.posterFront = "a"

    ' Fullscreen state
    m.fullscreen = false
    m.ptzActive = false

    ' Observe poster load status for double-buffer swap
    m.previewPosterA.observeField("loadStatus", "onPosterLoadA")
    m.previewPosterB.observeField("loadStatus", "onPosterLoadB")

    ' Observe video state for buffering feedback
    m.previewVideo.observeField("state", "onVideoState")

    m.cameraList.observeField("itemFocused", "onCameraFocused")
    m.previewTimer.observeField("fire", "onPreviewRefresh")

    fetchCameraList()
end sub

sub fetchCameraList()
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/list?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraListResponse")
    task.request = { url: url }
    task.control = "run"
    m.listTask = task
end sub

sub onCameraListResponse(event as object)
    text = event.getData()
    m.loadingLabel.visible = false
    if text = invalid or text = "" then
        m.loadingLabel.text = "Could not reach server at " + m.SERVER_URL
        m.loadingLabel.visible = true
        return
    end if

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" then return

    for each name in json
        item = m.cameraListContent.createChild("ContentNode")
        item.title = name

        cam = { name: name, hasSnapshot: true, stream: "", streamType: "", ptz: false }
        m.cameras.push(cam)
    end for

    if m.cameras.count() > 0
        m.cameraList.setFocus(true)
        for i = 0 to m.cameras.count() - 1
            fetchCameraInfo(i)
        end for
    end if
end sub

sub fetchCameraInfo(idx as integer)
    cam = m.cameras[idx]
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + cam.name + "/info?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.addField("camIndex", "integer", false)
    task.camIndex = idx
    task.observeField("response", "onCameraInfoResponse")
    task.request = { url: url }
    task.control = "run"
end sub

sub onCameraInfoResponse(event as object)
    text = event.getData()
    if text = invalid or text = "" then return

    info = ParseJSON(text)
    if info = invalid then return

    for i = 0 to m.cameras.count() - 1
        if m.cameras[i].name = info.name
            m.cameras[i].hasSnapshot = info.snapshot
            m.cameras[i].stream = info.stream
            m.cameras[i].streamType = info.stream_type
            m.cameras[i].ptz = (info.ptz = true)

            content = m.cameraListContent.getChild(i)
            if content <> invalid
                desc = ""
                if info.stream <> "" and info.snapshot
                    desc = "snapshot + " + info.stream_type
                else if info.stream <> ""
                    desc = info.stream_type + " stream"
                else
                    desc = "snapshot"
                end if
                if info.ptz = true then desc = desc + " + PTZ"
                content.description = desc
            end if

            if i = m.currentCamera then startPreview(i)
            exit for
        end if
    end for
end sub

sub onCameraFocused()
    idx = m.cameraList.itemFocused
    if idx < 0 or idx >= m.cameras.count() then return
    if idx = m.currentCamera then return
    startPreview(idx)
end sub

sub startPreview(idx as integer)
    m.currentCamera = idx
    cam = m.cameras[idx]
    m.previewLabel.text = cam.name

    ' Stop any existing video
    m.previewVideo.control = "stop"
    m.previewVideo.visible = false
    m.previewPosterA.visible = true
    m.previewPosterB.visible = true
    m.previewPosterA.opacity = 1.0
    m.previewPosterB.opacity = 0.0
    m.posterFront = "a"

    if cam.stream <> ""
        ' HLS stream — use Video node
        m.previewMode = "video"
        m.previewTimer.control = "stop"
        m.previewPosterA.visible = false
        m.previewPosterB.visible = false
        m.previewPosterA.opacity = 0.0
        m.previewPosterB.opacity = 0.0
        m.previewVideo.visible = true

        content = CreateObject("roSGNode", "ContentNode")
        content.url = cam.stream
        content.streamFormat = "hls"
        m.previewVideo.content = content
        m.previewVideo.control = "play"
    else
        ' Snapshot — double-buffered poster refresh
        m.previewMode = "poster"
        m.previewVideo.visible = false
        m.previewPosterA.visible = true
        m.previewPosterB.visible = true
        refreshPosterPreview()
        m.previewTimer.control = "start"
    end if
end sub

' -- Double-buffered poster preview --

sub refreshPosterPreview()
    if m.currentCamera < 0 or m.currentCamera >= m.cameras.count() then return
    cam = m.cameras[m.currentCamera]
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + cam.name + "?t=" + ts.asSeconds().toStr()

    if m.posterFront = "a"
        m.previewPosterB.uri = url
    else
        m.previewPosterA.uri = url
    end if
end sub

sub onPosterLoadA(event as object)
    status = event.getData()
    if status = "ready" and m.previewMode = "poster"
        m.previewPosterA.opacity = 1.0
        m.previewPosterB.opacity = 0.0
        m.posterFront = "a"
    end if
end sub

sub onPosterLoadB(event as object)
    status = event.getData()
    if status = "ready" and m.previewMode = "poster"
        m.previewPosterB.opacity = 1.0
        m.previewPosterA.opacity = 0.0
        m.posterFront = "b"
    end if
end sub

sub onPreviewRefresh()
    if m.previewMode = "poster" then refreshPosterPreview()
end sub

sub onVideoState(event as object)
    state = event.getData()
    if m.currentCamera < 0 then return
    camName = m.cameras[m.currentCamera].name
    if state = "buffering"
        m.previewLabel.text = camName + " (buffering...)"
    else if state = "playing"
        m.previewLabel.text = camName
    else if state = "error"
        m.previewLabel.text = camName + " (stream error)"
        ' Fall back to snapshot
        m.previewVideo.control = "stop"
        m.previewVideo.visible = false
        m.previewPosterA.visible = true
        m.previewPosterB.visible = true
        m.previewMode = "poster"
        refreshPosterPreview()
        m.previewTimer.control = "start"
    end if
end sub

' -- Fullscreen --

sub enterFullscreen()
    if m.currentCamera < 0 then return
    m.fullscreen = true
    cam = m.cameras[m.currentCamera]

    m.cameraList.visible = false
    m.top.findNode("appTitle").visible = false
    m.top.findNode("appSubtitle").visible = false
    m.top.findNode("hintBar").visible = false

    ' Move focus to trap so D-pad reaches onKeyEvent
    m.focusTrap.setFocus(true)

    ' Expand to fullscreen
    previewGroup = m.top.findNode("previewGroup")
    previewGroup.translation = [0, 0]
    m.previewBg.width = 1920
    m.previewBg.height = 1080
    m.previewPosterA.width = 1920
    m.previewPosterA.height = 1080
    m.previewPosterB.width = 1920
    m.previewPosterB.height = 1080
    m.previewVideo.width = 1920
    m.previewVideo.height = 1080
    m.previewLabelGroup.translation = [20, 1020]

    ' PTZ for any fullscreen camera that supports it
    m.ptzActive = cam.ptz
    m.ptzOverlay.visible = cam.ptz
end sub

sub exitFullscreen()
    m.fullscreen = false

    if m.ptzActive then sendPtzCommand("stop", "")
    m.ptzActive = false
    m.ptzOverlay.visible = false

    m.cameraList.visible = true
    m.top.findNode("appTitle").visible = true
    m.top.findNode("appSubtitle").visible = true
    m.top.findNode("hintBar").visible = true

    previewGroup = m.top.findNode("previewGroup")
    previewGroup.translation = [520, 140]
    m.previewBg.width = 1340
    m.previewBg.height = 754
    m.previewPosterA.width = 1340
    m.previewPosterA.height = 754
    m.previewPosterB.width = 1340
    m.previewPosterB.height = 754
    m.previewVideo.width = 1340
    m.previewVideo.height = 754
    m.previewLabelGroup.translation = [20, 700]

    m.cameraList.setFocus(true)
end sub

' -- PTZ --

sub sendPtzCommand(action as string, direction as string)
    if m.currentCamera < 0 then return
    cam = m.cameras[m.currentCamera]
    body = ""
    if action = "move"
        body = FormatJSON({ action: "move", direction: direction, speed: 1.0 })
    else
        body = FormatJSON({ action: "stop" })
    end if

    task = CreateObject("roSGNode", "HttpTask")
    task.request = {
        url: m.SERVER_URL + "/camera/" + cam.name + "/ptz",
        method: "POST",
        body: body
    }
    task.control = "run"
end sub

sub highlightPtzArrow(direction as string, on as boolean)
    color = "#FFFFFF44"
    if on then color = "#44FF44FF"
    if direction = "up" then m.top.findNode("ptzUp").color = color
    if direction = "down" then m.top.findNode("ptzDown").color = color
    if direction = "left" then m.top.findNode("ptzLeft").color = color
    if direction = "right" then m.top.findNode("ptzRight").color = color
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    ' -- Fullscreen with PTZ --
    if m.fullscreen and m.ptzActive
        ptzDirection = ""
        if key = "up" then ptzDirection = "up"
        if key = "down" then ptzDirection = "down"
        if key = "left" then ptzDirection = "left"
        if key = "right" then ptzDirection = "right"
        if key = "fastforward" then ptzDirection = "zoomIn"
        if key = "rewind" then ptzDirection = "zoomOut"

        if ptzDirection <> ""
            if press
                sendPtzCommand("move", ptzDirection)
                highlightPtzArrow(ptzDirection, true)
            else
                sendPtzCommand("stop", "")
                highlightPtzArrow(ptzDirection, false)
            end if
            return true
        end if

        if key = "back"
            if press then exitFullscreen()
            return true
        end if
        return false
    end if

    ' -- Fullscreen without PTZ --
    if m.fullscreen
        if key = "back" and press
            exitFullscreen()
            return true
        end if
        return false
    end if

    ' -- Normal list mode --
    if not press then return false

    if key = "OK"
        enterFullscreen()
        return true
    end if

    return false
end function
