' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/
'
' ============================================================
' 3 Bad Dogs Screensaver for Roku
' ============================================================
' Three modes (selectable via screensaver settings):
'   "photo"  - random photos with crossfade from server
'   "camera" - live camera snapshots (near-realtime via a_secure_password)
'   "video"  - HLS live video from a single camera
'
' All modes share the floating clock overlay with rotating
' data chips (weather, calendar, thermostat, forecast).
' ============================================================

sub init()
    ' -- Configuration --
    m.DEFAULT_SERVER_URL = ""
    m.PHOTO_W     = 1920
    m.PHOTO_H     = 1080
    m.PHOTO_FIT   = "scaleToFit"

    m.dataSources = [
        "/ha/weather",
        "/ha/event",
        "/ha/thermostat",
        "/ha/forecast"
    ]

    ' Read saved settings from registry
    sec = CreateObject("roRegistrySection", "settings")
    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL

    m.mode = sec.Read("mode")
    if m.mode <> "camera" and m.mode <> "video" then m.mode = "photo"

    ' Timing from registry (with defaults)
    photoSec = sec.Read("photoInterval")
    if photoSec <> "" then m.PHOTO_SEC = val(photoSec) else m.PHOTO_SEC = 30
    if m.PHOTO_SEC < 5 then m.PHOTO_SEC = 30

    cameraSec = sec.Read("cameraRefresh")
    if cameraSec <> "" then m.CAMERA_SEC = val(cameraSec) else m.CAMERA_SEC = 1

    cycleSec = sec.Read("cycleInterval")
    if cycleSec <> "" then m.CYCLE_SEC = val(cycleSec) else m.CYCLE_SEC = 5
    if m.CYCLE_SEC < 1 then m.CYCLE_SEC = 5

    dataSec = sec.Read("dataInterval")
    if dataSec <> "" then m.DATA_SEC = val(dataSec) else m.DATA_SEC = 120

    ' Camera selection
    m.cameraName = "front-door"
    savedCamera = sec.Read("camera")
    if savedCamera <> "" then m.cameraName = savedCamera
    m.cycleMode = (m.cameraName = "cycle")
    m.cameraList = []
    m.cameraIndex = 0
    m.cycleCounter = 0

    ' Video player ref
    m.videoPlayer = m.top.findNode("videoPlayer")

    ' Photo state
    m.front = "a"
    m.photoA = m.top.findNode("photoA")
    m.photoB = m.top.findNode("photoB")
    m.photoA.loadDisplayMode = m.PHOTO_FIT
    m.photoB.loadDisplayMode = m.PHOTO_FIT

    ' Overlay refs
    m.overlay   = m.top.findNode("overlay")
    m.overlayBg = m.top.findNode("overlayBg")
    m.clock     = m.top.findNode("clock")
    m.dateLabel = m.top.findNode("dateLabel")
    m.dataChip  = m.top.findNode("dataChip")

    ' Crossfade animation refs
    m.fadeInA  = m.top.findNode("fadeInA")
    m.fadeOutA = m.top.findNode("fadeOutA")
    m.fadeInB  = m.top.findNode("fadeInB")
    m.fadeOutB = m.top.findNode("fadeOutB")

    ' Bounce state
    m.bx = 100.0 : m.by = 100.0
    m.bdx = 1.0  : m.bdy = 0.7
    m.overlayW = 420 : m.overlayH = 160

    ' Data chip rotation state
    m.dataIndex = 0

    ' Observe photo load status
    m.photoA.observeField("loadStatus", "onPhotoLoadA")
    m.photoB.observeField("loadStatus", "onPhotoLoadB")

    ' Timers
    m.photoTimer = m.top.findNode("photoTimer")
    m.clockTimer = m.top.findNode("clockTimer")
    m.dataTimer = m.top.findNode("dataTimer")
    m.bounceTimer = m.top.findNode("bounceTimer")

    m.clockTimer.observeField("fire", "onClockTimer")
    m.clockTimer.control = "start"
    m.dataTimer.duration = m.DATA_SEC
    m.dataTimer.observeField("fire", "onDataTimer")
    m.dataTimer.control = "start"
    m.bounceTimer.observeField("fire", "onBounce")
    m.bounceTimer.control = "start"

    if m.mode = "video"
        ' Video mode: fetch camera info to get stream URL, then start playback
        ' No photo timer needed — video plays continuously
        m.photoA.visible = false
        m.photoB.visible = false
        fetchVideoStreamInfo()
    else if m.mode = "camera"
        m.photoTimer.duration = m.CAMERA_SEC
        m.photoTimer.observeField("fire", "onPhotoTimer")
        m.photoTimer.control = "start"
        m.photoA.opacity = 1.0
        m.photoB.opacity = 1.0
        if m.cycleMode then fetchCameraList()
        loadNextImage()
    else
        m.photoTimer.duration = m.PHOTO_SEC
        m.photoTimer.observeField("fire", "onPhotoTimer")
        m.photoTimer.control = "start"
        loadNextImage()
    end if

    ' Initial render
    updateClock()
    fetchNextData()
end sub

' -- Image loading --

sub loadNextImage()
    ts = CreateObject("roDateTime")
    if m.mode = "camera"
        if m.cycleMode and m.cameraList.count() = 0 then return
        url = m.SERVER_URL + "/camera/" + m.cameraName + "?t=" + ts.asSeconds().toStr()
        m.photoB.uri = url
    else
        url = m.SERVER_URL + "/random?w=" + m.PHOTO_W.toStr() + "&h=" + m.PHOTO_H.toStr() + "&t=" + ts.asSeconds().toStr()
        if m.front = "a"
            m.photoB.uri = url
        else
            m.photoA.uri = url
        end if
    end if
end sub

sub onPhotoLoadA(event as object)
    if event.getData() = "ready"
        if m.mode = "camera" then return
        m.fadeInA.control = "start"
        m.fadeOutB.control = "start"
        m.front = "a"
    end if
end sub

sub onPhotoLoadB(event as object)
    if event.getData() = "ready"
        if m.mode = "camera"
            m.photoA.uri = m.photoB.uri
            return
        end if
        m.fadeInB.control = "start"
        m.fadeOutA.control = "start"
        m.front = "b"
    end if
end sub

sub onPhotoTimer()
    if m.cycleMode and m.cameraList.count() > 0
        m.cycleCounter = m.cycleCounter + 1
        cycleTicks = m.CYCLE_SEC / m.CAMERA_SEC
        if cycleTicks < 1 then cycleTicks = 1
        if m.cycleCounter >= cycleTicks
            m.cycleCounter = 0
            m.cameraIndex = (m.cameraIndex + 1) mod m.cameraList.count()
            m.cameraName = m.cameraList[m.cameraIndex]
        end if
    end if
    loadNextImage()
end sub

' -- Camera list for cycle mode --

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
    if text = invalid or text = "" then return

    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray" or json.count() = 0 then return

    m.cameraList = json
    m.cameraIndex = 0
    m.cameraName = m.cameraList[0]
    m.cycleCounter = 0
    loadNextImage()
end sub

' -- Clock overlay --

sub updateClock()
    dt = CreateObject("roDateTime")
    dt.toLocalTime()

    hours = dt.getHours()
    ampm = "AM"
    if hours >= 12 then ampm = "PM"
    if hours > 12 then hours = hours - 12
    if hours = 0 then hours = 12
    mins = dt.getMinutes()
    minStr = mins.toStr()
    if mins < 10 then minStr = "0" + minStr
    m.clock.text = hours.toStr() + ":" + minStr + " " + ampm

    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    dow = dt.getDayOfWeek()
    mon = dt.getMonth() - 1
    day = dt.getDayOfMonth()

    dayName = "Sunday"
    if dow >= 0 and dow < days.count() then dayName = days[dow]
    monName = "January"
    if mon >= 0 and mon < months.count() then monName = months[mon]

    m.dateLabel.text = dayName + ", " + monName + " " + day.toStr()
end sub

sub onClockTimer()
    updateClock()
end sub

' -- Rotating data chips --

sub fetchNextData()
    if m.dataSources.count() = 0 then return

    path = m.dataSources[m.dataIndex]
    m.dataIndex = (m.dataIndex + 1) mod m.dataSources.count()

    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + path + "?t=" + ts.asSeconds().toStr()

    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onDataResponse")
    task.request = { url: url }
    task.control = "run"
    m.dataTask = task
end sub

sub onDataResponse(event as object)
    text = event.getData()
    if text <> invalid and text <> ""
        m.dataChip.text = text
    end if
    resizeOverlay()
end sub

sub onDataTimer()
    fetchNextData()
end sub

' -- Overlay sizing --

sub resizeOverlay()
    content = m.top.findNode("overlayContent")
    rect = content.boundingRect()
    w = rect.width + 48
    h = rect.height + 32
    if w < 200 then w = 200
    if h < 100 then h = 100
    m.overlayBg.width = w
    m.overlayBg.height = h
    m.overlayW = w
    m.overlayH = h
end sub

' -- Video mode (HLS) --

sub fetchVideoStreamInfo()
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + m.cameraName + "/info?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onVideoInfoResponse")
    task.request = { url: url }
    task.control = "run"
    m.videoInfoTask = task
end sub

sub onVideoInfoResponse(event as object)
    text = event.getData()
    if text = invalid or text = "" then return

    info = ParseJSON(text)
    if info = invalid then return

    streamUrl = info.stream
    if streamUrl = invalid or streamUrl = "" then return

    ' Start HLS video playback (muted — screensaver should be silent)
    m.videoPlayer.visible = true
    m.videoPlayer.mute = true
    content = CreateObject("roSGNode", "ContentNode")
    content.url = streamUrl
    content.streamFormat = "hls"
    m.videoPlayer.content = content
    m.videoPlayer.control = "play"
end sub

' -- Anti-burn-in bounce --

sub onBounce()
    maxX = 1920 - m.overlayW - 20
    maxY = 1080 - m.overlayH - 20

    m.bx = m.bx + m.bdx
    m.by = m.by + m.bdy

    if m.bx <= 20 or m.bx >= maxX then m.bdx = -m.bdx
    if m.by <= 20 or m.by >= maxY then m.bdy = -m.bdy

    if m.bx < 20 then m.bx = 20
    if m.bx > maxX then m.bx = maxX
    if m.by < 20 then m.by = 20
    if m.by > maxY then m.by = maxY

    m.overlay.translation = [m.bx, m.by]
end sub
