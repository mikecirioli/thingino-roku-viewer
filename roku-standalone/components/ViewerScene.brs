' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.posterA = m.top.findNode("posterA")
    m.posterB = m.top.findNode("posterB")
    m.video = m.top.findNode("video")
    m.nameLabel = m.top.findNode("nameLabel")
    m.refreshTimer = m.top.findNode("refreshTimer")
    
    m.posterA.observeField("loadStatus", "onPosterLoadA")
    m.posterB.observeField("loadStatus", "onPosterLoadB")
    m.refreshTimer.observeField("fire", "refreshSnapshot")

    m.cameras = GetCameras()
    m.currentIdx = 0
    m.frontPoster = "a"
    m.pendingBuffer = ""
    
    if m.cameras.count() > 0
        startCamera(0)
    else
        m.nameLabel.text = "No cameras"
    end if
end sub

sub startCamera(idx as integer)
    if idx < 0 or idx >= m.cameras.count() then return
    m.currentIdx = idx
    cam = m.cameras[idx]
    
    m.nameLabel.text = cam.name
    m.video.control = "stop"
    m.video.visible = false
    m.refreshTimer.control = "stop"
    
    if cam.stream <> ""
        content = CreateObject("roSGNode", "ContentNode")
        content.url = cam.stream
        content.streamFormat = "hls"
        m.video.content = content
        m.video.visible = true
        m.video.control = "play"
    else
        m.posterA.visible = true
        m.posterB.visible = true
        refreshSnapshot()
        m.refreshTimer.control = "start"
    end if
end sub

sub refreshSnapshot()
    cam = m.cameras[m.currentIdx]
    m.pendingBuffer = if m.frontPoster = "a" then "tmp:/viewer_b.jpg" else "tmp:/viewer_a.jpg"
    
    task = CreateObject("roSGNode", "HttpTask")
    task.authType = cam.authType
    task.request = {
        url: cam.snapshot,
        toFile: m.pendingBuffer,
        auth: { username: cam.username, password: cam.password }
    }
    task.observeField("responseCode", "onSnapshotDownloaded")
    task.control = "run"
end sub

sub onSnapshotDownloaded(event as object)
    if event.getData() = 200
        uri = m.pendingBuffer + "?t=" + CreateObject("roDateTime").asSeconds().toStr()
        if m.frontPoster = "a"
            m.posterB.uri = uri
        else
            m.posterA.uri = uri
        end if
    end if
end sub

sub onPosterLoadA(event as object)
    if event.getData() = "ready" and m.frontPoster = "b"
        m.posterA.opacity = 1.0
        m.posterB.opacity = 0.0
        m.frontPoster = "a"
    end if
end sub

sub onPosterLoadB(event as object)
    if event.getData() = "ready" and m.frontPoster = "a"
        m.posterB.opacity = 1.0
        m.posterA.opacity = 0.0
        m.frontPoster = "b"
    end if
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    
    if key = "back"
        m.top.getScene().backToConfig = true
        return false ' let main.brs handle it or Scene handle it
    else if key = "up"
        startCamera((m.currentIdx - 1 + m.cameras.count()) mod m.cameras.count())
        return true
    else if key = "down"
        startCamera((m.currentIdx + 1) mod m.cameras.count())
        return true
    end if
    
    return false
end function
