' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.DEFAULT_SERVER_URL = ""
    m.DEFAULT_USERNAME = ""
    m.DEFAULT_PASSWORD = ""
    sec = CreateObject("roRegistrySection", "settings")
    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = invalid or m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL
    m.USERNAME = sec.Read("username")
    if m.USERNAME = invalid or m.USERNAME = "" then m.USERNAME = m.DEFAULT_USERNAME
    m.PASSWORD = sec.Read("password")
    if m.PASSWORD = invalid or m.PASSWORD = "" then m.PASSWORD = m.DEFAULT_PASSWORD

    m.cameraList = m.top.findNode("cameraList")
    m.cameraListContent = m.top.findNode("cameraListContent")
    m.loadingLabel = m.top.findNode("loadingLabel")
    m.previewPosterA = m.top.findNode("previewPosterA")
    m.previewPosterB = m.top.findNode("previewPosterB")
    m.previewVideo = m.top.findNode("previewVideo")
    m.previewLabel = m.top.findNode("previewLabel")
    m.previewTimer = m.top.findNode("previewTimer")
    
    m.cameras = []
    m.currentCamera = -1
    m.posterFront = "a"
    m.fullscreen = false
    m.ptzActive = false

    m.previewPosterA.observeField("loadStatus", "onPosterLoadA")
    m.previewPosterB.observeField("loadStatus", "onPosterLoadB")
    m.previewVideo.observeField("state", "onVideoState")
    m.cameraList.observeField("itemFocused", "onCameraFocused")
    m.previewTimer.observeField("fire", "refreshPosterPreview")

    if not sec.Exists("serverUrl")
        showSettings()
    else
        fetchAllCameraInfo()
    end if
end sub

sub showSettings()
    m.settingsView = CreateObject("roSGNode", "SettingsView")
    m.settingsView.observeField("wasClosed", "onSettingsClose")
    m.top.appendChild(m.settingsView)
    m.settingsView.setFocus(true)
end sub

sub onSettingsClose()
    if m.settingsView <> invalid
        m.top.removeChild(m.settingsView)
        m.settingsView = invalid
    end if

    ' Refresh data in case settings changed
    sec = CreateObject("roRegistrySection", "settings")
    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = invalid or m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL
    m.USERNAME = sec.Read("username")
    if m.USERNAME = invalid or m.USERNAME = "" then m.USERNAME = m.DEFAULT_USERNAME
    m.PASSWORD = sec.Read("password")
    if m.PASSWORD = invalid or m.PASSWORD = "" then m.PASSWORD = m.DEFAULT_PASSWORD

    m.loadingLabel.text = "Loading cameras..."
    m.loadingLabel.visible = true
    m.cameraList.setFocus(true)
    fetchAllCameraInfo()
end sub

sub fetchAllCameraInfo()
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/all_info?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onAllInfoResponse")
    task.observeField("error", "onAllInfoError")
    task.request = { url: url, auth: { username: m.USERNAME, password: m.PASSWORD } }
    task.control = "run"
    m.fetchTask = task
end sub

sub onAllInfoError(event as object)
    errMsg = event.getData()
    if errMsg = invalid then errMsg = "Connection failed"
    m.loadingLabel.text = errMsg + ". Press * for Settings."
    m.loadingLabel.visible = true
end sub

sub onAllInfoResponse(event as object)
    text = event.getData()
    if text = invalid or text = ""
        m.loadingLabel.text = "Empty response. Press * for Settings."
        m.loadingLabel.visible = true
        return
    end if

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray"
        m.loadingLabel.text = "Could not parse camera list. Press * for Settings."
        m.loadingLabel.visible = true
        return
    end if

    m.loadingLabel.visible = false
    m.cameras = []
    m.cameraListContent.clear()

    ' Create separate entries for each type (jpg then hls), matching web UI order
    ' First pass: all snapshot (jpg) entries
    for each camInfo in json
        hasSnapshot = (camInfo.snapshot <> invalid and camInfo.snapshot <> "")
        if hasSnapshot
            item = m.cameraListContent.createChild("ContentNode")
            ptzStr = ""
            if camInfo.ptz = true then ptzStr = " + PTZ"
            item.title = camInfo.name
            item.description = "(jpg)" + ptzStr

            cam = {
                name: camInfo.name,
                mode: "jpg",
                hasSnapshot: true,
                stream: "",
                streamType: "",
                ptz: (camInfo.ptz = true)
            }
            m.cameras.push(cam)
        end if
    end for

    ' Second pass: all stream (hls) entries
    for each camInfo in json
        streamUrl = camInfo.stream
        if streamUrl <> invalid and streamUrl <> ""
            if Left(streamUrl, 1) = "/"
                streamUrl = m.SERVER_URL + streamUrl
            end if

            item = m.cameraListContent.createChild("ContentNode")
            ptzStr = ""
            if camInfo.ptz = true then ptzStr = " + PTZ"
            sType = camInfo.stream_type
            if sType = invalid or sType = "" then sType = "hls"
            item.title = camInfo.name
            item.description = "(" + sType + ")" + ptzStr

            cam = {
                name: camInfo.name,
                mode: "hls",
                hasSnapshot: false,
                stream: streamUrl,
                streamType: sType,
                ptz: (camInfo.ptz = true)
            }
            m.cameras.push(cam)
        end if
    end for

    if m.cameras.count() > 0
        m.cameraList.setFocus(true)
        startPreview(0)
    end if
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
    m.previewLabel.text = cam.name + " (" + cam.mode + ")"

    m.previewVideo.control = "stop"
    m.previewVideo.visible = false
    m.previewPosterA.visible = true
    m.previewPosterB.visible = true
    m.posterFront = "a"

    if cam.mode = "hls" and cam.stream <> ""
        m.previewTimer.control = "stop"
        content = CreateObject("roSGNode", "ContentNode")
        content.url = cam.stream
        content.streamFormat = "hls"
        m.previewVideo.content = content
        m.previewVideo.visible = true
        m.previewVideo.control = "play"
    else
        refreshPosterPreview()
        m.previewTimer.control = "start"
    end if
end sub

sub refreshPosterPreview()
    if m.currentCamera < 0 then return
    cam = m.cameras[m.currentCamera]
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + cam.name + "?t=" + ts.asSeconds().toStr()
    if m.posterFront = "a" then m.previewPosterB.uri = url else m.previewPosterA.uri = url
end sub

sub onPosterLoadA(event as object)
    if event.getData() = "ready"
        m.previewPosterA.opacity = 1.0
        m.previewPosterB.opacity = 0.0
        m.posterFront = "a"
    end if
end sub

sub onPosterLoadB(event as object)
    if event.getData() = "ready"
        m.previewPosterB.opacity = 1.0
        m.previewPosterA.opacity = 0.0
        m.posterFront = "b"
    end if
end sub

sub onVideoState(event as object)
    state = event.getData()
    if state = "error"
        print "Video playback error"
    end if
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    if key = "options"
        showSettings()
        return true
    end if
    ' Other key handling logic...
    return false
end function
' ... other functions (fullscreen, ptz, etc.) remain the same
