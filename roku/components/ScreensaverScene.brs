' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/
'
' ============================================================
' 3 Bad Dogs Screensaver for Roku
' ============================================================
' Two modes (selectable via screensaver settings):
'   "photo"  - random photos with crossfade from server
'   "camera" - live camera snapshots (near-realtime via a_secure_password)
'
' Both modes share the floating clock overlay with rotating
' ticker items from /ticker endpoint (HA data + camera snapshots).
' ============================================================

sub init()
    ' -- Configuration --
    m.DEFAULT_SERVER_URL = ""
    m.PHOTO_W     = 1920
    m.PHOTO_H     = 1080
    m.PHOTO_FIT   = "scaleToFit"
    m.BLACKLIST   = ["camera-3"]

    ' Ticker items fetched from /ticker endpoint
    m.tickerItems = []
    m.tickerIdx = 0


    ' Read saved settings from registry
    sec = CreateObject("roRegistrySection", "settings")
    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = invalid or m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL
    ' Read screensaver mode from registry
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

    ' Clock style: "bounce" (default), "fade", or "off"
    m.clockStyle = sec.Read("clockStyle")
    if m.clockStyle <> "fade" and m.clockStyle <> "off" then m.clockStyle = "bounce"

    ' Clock opacity: 0 = fully opaque, 99 = nearly invisible. Default 40.
    opacityStr = sec.Read("clockOpacity")
    if opacityStr <> "" then m.clockOpacity = val(opacityStr) else m.clockOpacity = 40
    if m.clockOpacity < 0 then m.clockOpacity = 0
    if m.clockOpacity > 99 then m.clockOpacity = 99
    m.overlayMaxOpacity = (100 - m.clockOpacity) / 100.0

    ' Camera selection
    m.cameraName = "front-door"
    savedCamera = sec.Read("camera")
    if savedCamera <> "" then m.cameraName = savedCamera
    m.cycleMode = (m.cameraName = "cycle")
    m.cameraList = []
    m.cameraIndex = 0
    m.cycleCounter = 0

    ' Photo state
    m.photoFileCounter = 0
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
    m.photoInfoLabel = m.top.findNode("photoInfoLabel")
    m.dataImageRow = m.top.findNode("dataImageRow")
    m.dataImages = [
        m.top.findNode("dataImage0"),
        m.top.findNode("dataImage1"),
        m.top.findNode("dataImage2")
    ]

    ' Crossfade animation refs
    m.fadeInA  = m.top.findNode("fadeInA")
    m.fadeOutA = m.top.findNode("fadeOutA")
    m.fadeInB  = m.top.findNode("fadeInB")
    m.fadeOutB = m.top.findNode("fadeOutB")

    ' Overlay fade animation refs
    m.overlayFadeIn = m.top.findNode("overlayFadeIn")
    m.overlayFadeOut = m.top.findNode("overlayFadeOut")
    m.overlayFadeInInterp = m.top.findNode("overlayFadeInInterp")
    m.overlayFadeOutInterp = m.top.findNode("overlayFadeOutInterp")

    ' Set fade animation keyValues based on configured opacity
    m.overlayFadeInInterp.keyValue = [0.0, m.overlayMaxOpacity]
    m.overlayFadeOutInterp.keyValue = [m.overlayMaxOpacity, 0.0]

    ' Observe fade animation completion
    m.overlayFadeIn.observeField("state", "onOverlayFadeInDone")
    m.overlayFadeOut.observeField("state", "onOverlayFadeOutDone")

    ' Bounce state
    m.bx = 100.0 : m.by = 100.0
    m.bdx = 1.0  : m.bdy = 0.7
    m.overlayW = 420 : m.overlayH = 160

    m.pendingAnimation = ""

    ' Observe photo load status
    m.photoA.observeField("loadStatus", "onPhotoLoadA")
    m.photoB.observeField("loadStatus", "onPhotoLoadB")

    ' Timers
    m.photoTimer = m.top.findNode("photoTimer")
    if m.mode = "camera"
        m.photoTimer.duration = m.CAMERA_SEC
    else
        m.photoTimer.duration = m.PHOTO_SEC
    end if
    m.photoTimer.observeField("fire", "onPhotoTimer")
    m.photoTimer.control = "start"

    m.preloadSeconds = 5 ' Start loading next image 5s before it's displayed
    m.preloadTimer = m.top.findNode("preloadTimer")
    m.preloadTimer.observeField("fire", "onPreloadTimer")

    m.clockTimer = m.top.findNode("clockTimer")
    m.clockTimer.observeField("fire", "onClockTimer")
    if m.clockStyle <> "off" then m.clockTimer.control = "start"

    m.dataTimer = m.top.findNode("dataTimer")
    ' In bounce mode, rotate ticker every 15s. In fade mode, rotation is driven by fade cycle.
    if m.clockStyle = "fade"
        m.dataTimer.duration = m.DATA_SEC
    else
        m.dataTimer.duration = 15
    end if
    m.dataTimer.observeField("fire", "onDataTimer")
    if m.clockStyle <> "off" then m.dataTimer.control = "start"

    m.tickerRefreshTimer = m.top.findNode("tickerRefreshTimer")
    m.tickerRefreshTimer.observeField("fire", "onTickerRefresh")
    if m.clockStyle <> "off" then m.tickerRefreshTimer.control = "start"
    
    m.bounceTimer = m.top.findNode("bounceTimer")
    m.bounceTimer.observeField("fire", "onBounce")

    m.animationDelayTimer = m.top.findNode("animationDelayTimer")
    m.animationDelayTimer.observeField("fire", "onStartAnimation")

    m.fadeCycleTimer = m.top.findNode("fadeCycleTimer")
    m.fadeCycleTimer.observeField("fire", "onFadeCycleTimer")

    m.fadeStableTimer = m.top.findNode("fadeStableTimer")
    m.fadeStableTimer.observeField("fire", "onFadeStableTimer")

    ' Apply overlay opacity and start appropriate clock style
    if m.clockStyle = "off"
        m.overlay.visible = false
    else if m.clockStyle = "fade"
        m.overlay.opacity = 0.0
        startFadeCycle()
    else
        m.overlay.opacity = m.overlayMaxOpacity
        m.bounceTimer.control = "start"
    end if
    
    ' Camera mode setup
    if m.mode = "camera"
        m.photoA.opacity = 1.0
        m.photoB.opacity = 1.0
        if m.cycleMode then fetchCameraList()
    else
        ' Start pre-loading the second image immediately
        preloadDuration = m.PHOTO_SEC - m.preloadSeconds
        if preloadDuration < 1 then preloadDuration = 1
        m.preloadTimer.duration = preloadDuration
        m.preloadTimer.control = "start"
    end if

    ' Initial render
    if m.clockStyle <> "off" then updateClock()
    loadNextImage() ' Load the first image
    if m.clockStyle <> "off" then fetchTickerData()
end sub

' -- Image loading --

sub loadNextImage()
    ts = CreateObject("roDateTime")
    if m.mode = "camera"
        if m.cycleMode and m.cameraList.count() = 0 then return
        url = buildUrl(m.SERVER_URL, "/camera/" + m.cameraName + "?t=" + ts.asSeconds().toStr())
        m.photoB.uri = url
    else
        ' Use HttpTask to download image to tmp:/ so we can read X-Photo-Info header
        url = buildUrl(m.SERVER_URL, "/random?noexif=1&w=" + m.PHOTO_W.toStr() + "&h=" + m.PHOTO_H.toStr() + "&t=" + ts.asSeconds().toStr())

        ' Unique filename each time to bust Poster URI cache
        tmpFile = "tmp:/photo_" + m.photoFileCounter.toStr()
        ' Delete file from 2 cycles ago to keep tmp:/ clean (keep current + displayed)
        if m.photoFileCounter >= 2
            DeleteFile("tmp:/photo_" + (m.photoFileCounter - 2).toStr())
        end if
        m.photoFileCounter = m.photoFileCounter + 1

        task = CreateObject("roSGNode", "HttpTask")
        task.observeField("response", "onPhotoFetchResponse")
        task.request = {
            url: url,
            toFile: tmpFile
        }
        task.control = "run"
        m.photoFetchTask = task
    end if
end sub

sub onPhotoFetchResponse(event as object)
    filePath = event.getData()
    if filePath = invalid or filePath = "" then return

    task = event.getRoSGNode()
    if task = invalid then return

    ' Read X-Photo-Info header for geotag display
    headers = task.responseHeaders
    photoInfo = ""
    if headers <> invalid
        pi = headers["x-photo-info"]
        if pi <> invalid then photoInfo = pi
    end if
    m.photoInfoLabel.text = photoInfo
    m.photoInfoLabel.visible = (photoInfo <> "")

    ' Set the Poster URI to the downloaded file
    if m.front = "a"
        m.photoB.uri = filePath
    else
        m.photoA.uri = filePath
    end if

    resizeOverlay()
end sub

sub onPhotoLoadA(event as object)
    if event.getData() = "ready"
        if m.mode = "camera" then return
        m.pendingAnimation = "A"
        m.animationDelayTimer.control = "start"
    end if
end sub

sub onPhotoLoadB(event as object)
    if event.getData() = "ready"
        if m.mode = "camera"
            m.photoA.uri = m.photoB.uri
            return
        end if
        m.pendingAnimation = "B"
        m.animationDelayTimer.control = "start"
    end if
end sub

sub onStartAnimation()
    if m.pendingAnimation = "A"
        m.fadeInA.control = "start"
        m.fadeOutB.control = "start"
        m.front = "a"
    else if m.pendingAnimation = "B"
        m.fadeInB.control = "start"
        m.fadeOutA.control = "start"
        m.front = "b"
    end if
    m.pendingAnimation = ""
end sub

sub onPhotoTimer()
    ' This timer firing means it's time to SHOW the pre-loaded image.
    ' We now use this event to trigger the next pre-load.
    if m.mode = "camera"
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
    else
        ' The image that was pre-loading should be ready.
        ' Now, start the timer for the *next* preload.
        preloadDuration = m.PHOTO_SEC - m.preloadSeconds
        if preloadDuration < 1 then preloadDuration = 1
        m.preloadTimer.duration = preloadDuration
        m.preloadTimer.control = "start"
    end if
end sub

sub onPreloadTimer()
    ' It's time to start downloading the next image in the background
    loadNextImage()
end sub

' -- Camera list for cycle mode --

sub fetchCameraList()
    ts = CreateObject("roDateTime")
    url = buildUrl(m.SERVER_URL, "/camera/list?t=" + ts.asSeconds().toStr())
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

    filtered = []
    for each name in json
        skip = false
        for each bl in m.BLACKLIST
            if LCase(name) = LCase(bl) then skip = true
        end for
        if not skip then filtered.push(name)
    end for

    if filtered.count() = 0 then return

    m.cameraList = filtered
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

sub fetchTickerData()
    ts = CreateObject("roDateTime")
    url = buildUrl(m.SERVER_URL, "/ticker?t=" + ts.asSeconds().toStr())
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onTickerDataResponse")
    task.request = { url: url }
    task.control = "run"
    m.tickerTask = task
end sub

sub onTickerDataResponse(event as object)
    text = event.getData()
    if text = invalid or text = "" then return
    json = ParseJSON(text)
    if json = invalid or json.items = invalid then return
    m.tickerItems = json.items
    if m.tickerIdx >= m.tickerItems.count() then m.tickerIdx = 0
    showNextTickerItem()
end sub

sub showNextTickerItem()
    if m.tickerItems.count() = 0 then return
    item = m.tickerItems[m.tickerIdx]
    m.tickerIdx = (m.tickerIdx + 1) mod m.tickerItems.count()

    if item.type = "image" and item.url <> invalid and item.url <> ""
        ' Collect 3 camera images using circular queue over image items
        ts = CreateObject("roDateTime")
        imageUrls = []
        imageUrls.push(buildUrl(m.SERVER_URL, item.url + "&t=" + ts.asSeconds().toStr()))

        ' Gather 2 more images, wrapping around if needed
        scanIdx = m.tickerIdx
        scanned = 0
        while imageUrls.count() < 3 and scanned < m.tickerItems.count()
            scanItem = m.tickerItems[scanIdx]
            scanIdx = (scanIdx + 1) mod m.tickerItems.count()
            scanned = scanned + 1
            if scanItem.type = "image" and scanItem.url <> invalid and scanItem.url <> ""
                imageUrls.push(buildUrl(m.SERVER_URL, scanItem.url + "&t=" + ts.asSeconds().toStr()))
                m.tickerIdx = scanIdx
            end if
        end while

        m.dataChip.visible = false
        m.dataImageRow.visible = true
        for i = 0 to 2
            if i < imageUrls.count()
                m.dataImages[i].uri = imageUrls[i]
                m.dataImages[i].visible = true
            else
                m.dataImages[i].visible = false
            end if
        end for
    else
        ' Show text, hide image row
        m.dataImageRow.visible = false
        m.dataChip.visible = true
        if item.content <> invalid
            m.dataChip.text = item.content
        end if
    end if
    resizeOverlay()
end sub

sub onDataTimer()
    showNextTickerItem()
end sub

sub onTickerRefresh()
    fetchTickerData()
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

' -- Fade-style clock overlay --

sub startFadeCycle()
    ' Pick a random position within screen bounds
    rangeX = 1920 - m.overlayW - 80
    rangeY = 1080 - m.overlayH - 80
    if rangeX < 1 then rangeX = 1
    if rangeY < 1 then rangeY = 1
    m.bx = 40.0 + Rnd(rangeX)
    m.by = 40.0 + Rnd(rangeY)
    m.overlay.translation = [m.bx, m.by]

    ' Update content before fading in
    updateClock()
    showNextTickerItem()

    ' Start fade in
    m.overlayFadeIn.control = "start"
end sub

sub onOverlayFadeInDone(event as object)
    if event.getData() = "stopped"
        ' Fade in complete - hold stable for 3 seconds
        m.fadeStableTimer.control = "start"
    end if
end sub

sub onFadeStableTimer()
    ' Stable display period over - start fade out
    m.overlayFadeOut.control = "start"
end sub

sub onOverlayFadeOutDone(event as object)
    if event.getData() = "stopped"
        ' Fade out complete - wait 10 seconds invisible
        m.fadeCycleTimer.control = "start"
    end if
end sub

sub onFadeCycleTimer()
    ' Invisible wait period over - start new cycle
    startFadeCycle()
end sub
