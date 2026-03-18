' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/
'
' ============================================================
' 3 Bad Dogs — Main App Scene
' ============================================================
' Camera browser with live preview.
' Left: camera list. Right: live preview (HLS video or poster refresh).
' OK = fullscreen, * = screensaver settings, Back = exit.
' ============================================================

sub init()
    m.SERVER_URL = "http://192.168.1.245:8099"
    m.BLACKLIST = ["camera-3"]

    m.cameraList = m.top.findNode("cameraList")
    m.cameraListContent = m.top.findNode("cameraListContent")
    m.loadingLabel = m.top.findNode("loadingLabel")
    m.previewPoster = m.top.findNode("previewPoster")
    m.previewVideo = m.top.findNode("previewVideo")
    m.previewLabel = m.top.findNode("previewLabel")
    m.previewTimer = m.top.findNode("previewTimer")

    m.ptzOverlay = m.top.findNode("ptzOverlay")
    m.ptzBadge = m.top.findNode("ptzBadge")

    ' Camera data: array of {name, hasSnapshot, stream, streamType, ptz}
    m.cameras = []
    m.currentCamera = -1
    m.previewMode = "poster" ' "poster" or "video"

    ' Fullscreen state
    m.fullscreen = false
    m.ptzActive = false  ' true if current fullscreen camera has PTZ

    m.cameraList.observeField("itemFocused", "onCameraFocused")
    m.previewTimer.observeField("fire", "onPreviewRefresh")

    ' Fetch camera list
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
    if text = invalid or text = "" then return

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" then return

    for each name in json
        skip = false
        for each bl in m.BLACKLIST
            if LCase(name) = LCase(bl) then skip = true
        end for
        if skip then goto nextCam

        ' Add to list UI
        item = m.cameraListContent.createChild("ContentNode")
        item.title = name

        ' Store camera data (info will be fetched on focus)
        cam = { name: name, hasSnapshot: true, stream: "", streamType: "", ptz: false }
        m.cameras.push(cam)

        nextCam:
    end for

    if m.cameras.count() > 0
        m.cameraList.setFocus(true)
        ' Fetch info for all cameras
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

    ' Find which camera this is for by name
    for i = 0 to m.cameras.count() - 1
        if m.cameras[i].name = info.name
            m.cameras[i].hasSnapshot = info.snapshot
            m.cameras[i].stream = info.stream
            m.cameras[i].streamType = info.stream_type
            m.cameras[i].ptz = (info.ptz = true)

            ' Update list item description
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

            ' If this is the currently focused camera, update preview
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
    m.previewPoster.visible = true

    ' Decide preview mode based on camera capabilities
    if cam.stream <> ""
        ' Has HLS stream — use Video node
        m.previewMode = "video"
        m.previewTimer.control = "stop"
        m.previewPoster.visible = false
        m.previewVideo.visible = true

        content = CreateObject("roSGNode", "ContentNode")
        content.url = cam.stream
        content.streamFormat = "hls"
        m.previewVideo.content = content
        m.previewVideo.control = "play"
    else
        ' Snapshot only — use poster with refresh timer
        m.previewMode = "poster"
        m.previewVideo.visible = false
        m.previewPoster.visible = true
        refreshPosterPreview()
        m.previewTimer.control = "start"
    end if
end sub

sub refreshPosterPreview()
    if m.currentCamera < 0 or m.currentCamera >= m.cameras.count() then return
    cam = m.cameras[m.currentCamera]
    ts = CreateObject("roDateTime")
    m.previewPoster.uri = m.SERVER_URL + "/camera/" + cam.name + "?t=" + ts.asSeconds().toStr()
end sub

sub onPreviewRefresh()
    if m.previewMode = "poster" then refreshPosterPreview()
end sub

sub enterFullscreen()
    if m.currentCamera < 0 then return
    m.fullscreen = true
    cam = m.cameras[m.currentCamera]

    ' Hide UI elements
    m.cameraList.visible = false
    m.top.findNode("appTitle").visible = false
    m.top.findNode("appSubtitle").visible = false
    m.top.findNode("hintBar").visible = false

    ' Expand preview to fullscreen
    previewGroup = m.top.findNode("previewGroup")
    previewGroup.translation = [0, 0]
    m.previewPoster.width = 1920
    m.previewPoster.height = 1080
    m.previewVideo.width = 1920
    m.previewVideo.height = 1080

    ' Show PTZ overlay if camera supports it
    m.ptzActive = cam.ptz
    m.ptzOverlay.visible = cam.ptz
end sub

sub exitFullscreen()
    m.fullscreen = false

    ' Stop any PTZ movement
    if m.ptzActive then sendPtzCommand("stop", "")
    m.ptzActive = false
    m.ptzOverlay.visible = false

    ' Restore UI
    m.cameraList.visible = true
    m.top.findNode("appTitle").visible = true
    m.top.findNode("appSubtitle").visible = true
    m.top.findNode("hintBar").visible = true

    ' Restore preview position
    previewGroup = m.top.findNode("previewGroup")
    previewGroup.translation = [520, 140]
    m.previewPoster.width = 1340
    m.previewPoster.height = 754
    m.previewVideo.width = 1340
    m.previewVideo.height = 754

    m.cameraList.setFocus(true)
end sub

sub sendPtzCommand(action as string, direction as string)
    if m.currentCamera < 0 then return
    cam = m.cameras[m.currentCamera]
    body = ""
    if action = "move"
        body = FormatJSON({ action: "move", direction: direction, speed: 0.5 })
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
    ' Fire-and-forget — no response observer needed
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
    ' -- Fullscreen mode with PTZ --
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

    ' -- Fullscreen mode without PTZ --
    if m.fullscreen
        if key = "back" and press
            exitFullscreen()
            return true
        end if
        return false
    end if

    ' -- Normal (list) mode --
    if not press then return false

    if key = "OK"
        enterFullscreen()
        return true
    end if

    if key = "options"
        return true
    end if

    return false
end function
