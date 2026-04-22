' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
' https://creativecommons.org/licenses/by-nc-sa/4.0/

sub init()
    m.urlLabel = m.top.findNode("urlLabel")
    m.editUrlBtn = m.top.findNode("editUrlBtn")
    m.authLabel = m.top.findNode("authLabel")
    m.editAuthBtn = m.top.findNode("editAuthBtn")
    m.loginBtn = m.top.findNode("loginBtn")
    m.loginStatus = m.top.findNode("loginStatus")
    m.modeList = m.top.findNode("modeList")
    m.loading = m.top.findNode("loading")
    m.photoIntervalList = m.top.findNode("photoIntervalList")
    m.cycleIntervalList = m.top.findNode("cycleIntervalList")

    m.clockStyleList = m.top.findNode("clockStyleList")
    m.clockOpacityList = m.top.findNode("clockOpacityList")

    ' Page navigation
    m.page1 = m.top.findNode("page1")
    m.page2 = m.top.findNode("page2")
    m.pageLabel = m.top.findNode("pageLabel")
    m.nextPageBtn1 = m.top.findNode("nextPageBtn1")
    m.prevPageBtn2 = m.top.findNode("prevPageBtn2")
    m.currentPage = 1

    m.nextPageBtn1.observeField("buttonSelected", "onNextPage")
    m.prevPageBtn2.observeField("buttonSelected", "onPrevPage")

    m.photoIntervalValues = [15, 30, 60, 120]
    m.cycleIntervalValues = [3, 5, 10, 15]
    m.clockOpacityValues = [0, 40, 60, 80]

    m.pendingInfoCount = 0
    m.cameraInfoMap = {}

    ' Load saved settings
    sec = CreateObject("roRegistrySection", "settings")

    m.SERVER_URL = sec.Read("serverUrl")
    if m.SERVER_URL = invalid or m.SERVER_URL = "" then m.SERVER_URL = ""
    m.urlLabel.text = m.SERVER_URL

    m.SERVER_AUTH = sec.Read("serverAuth")
    if m.SERVER_AUTH = invalid then m.SERVER_AUTH = ""
    m.authLabel.text = maskSecret(m.SERVER_AUTH)

    m.sessionCookie = sec.Read("sessionCookie")
    if m.sessionCookie = invalid then m.sessionCookie = ""
    updateLoginStatus()

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

    ' Restore clock style
    savedClockStyle = sec.Read("clockStyle")
    if savedClockStyle = "fade"
        m.clockStyleList.checkedItem = 1
    else if savedClockStyle = "off"
        m.clockStyleList.checkedItem = 2
    else
        m.clockStyleList.checkedItem = 0
    end if

    ' Restore clock opacity
    savedClockOpacity = sec.Read("clockOpacity")
    if savedClockOpacity = "" then savedClockOpacity = "40"
    opacityIdx = 1 ' default index (40%)
    for i = 0 to m.clockOpacityValues.count() - 1
        if m.clockOpacityValues[i].toStr() = savedClockOpacity then opacityIdx = i
    end for
    m.clockOpacityList.checkedItem = opacityIdx

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

    m.editUrlBtn.observeField("buttonSelected", "onEditUrl")
    m.editAuthBtn.observeField("buttonSelected", "onEditAuth")
    m.loginBtn.observeField("buttonSelected", "onLogin")
    m.modeList.observeField("checkedItem", "onModeChanged")
    m.photoIntervalList.observeField("checkedItem", "onPhotoIntervalChanged")
    m.cycleIntervalList.observeField("checkedItem", "onCycleIntervalChanged")
    m.clockStyleList.observeField("checkedItem", "onClockStyleChanged")
    m.clockOpacityList.observeField("checkedItem", "onClockOpacityChanged")

    ' Defer focus until scene is fully rendered
    m.top.observeField("visible", "onSceneVisible")

    ' Fetch camera list
    m.loading.visible = true
    fetchCameraList()
end sub

sub onSceneVisible()
    if m.top.visible then m.editUrlBtn.setFocus(true)
end sub

' -- Page navigation --

sub onNextPage()
    showPage(2)
end sub

sub onPrevPage()
    showPage(1)
end sub

sub showPage(pageNum as integer)
    m.currentPage = pageNum
    m.page1.visible = (pageNum = 1)
    m.page2.visible = (pageNum = 2)
    m.pageLabel.text = "Page " + pageNum.toStr() + " of 2"
    if pageNum = 1
        m.editUrlBtn.setFocus(true)
    else
        m.clockStyleList.setFocus(true)
    end if
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
        ' OK pressed - save the URL
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

sub onEditAuth()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Auth Secret (remote access)"
    dialog.text = m.SERVER_AUTH
    dialog.isPassword = true
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onAuthDialogButton")
    m.top.dialog = dialog
end sub

sub onAuthDialogButton(event as object)
    idx = event.getData()
    dialog = m.top.dialog
    if idx = 0
        newAuth = dialog.text
        if newAuth <> m.SERVER_AUTH
            m.SERVER_AUTH = newAuth
            m.authLabel.text = maskSecret(newAuth)
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("serverAuth", newAuth)
            sec.Flush()
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

' -- Authentication --

sub onLogin()
    dialog = CreateObject("roSGNode", "UsernamePasswordDialog")
    dialog.title = "Log In to Server"
    dialog.buttons = ["Login", "Cancel"]
    dialog.observeField("buttonSelected", "onLoginDialogButton")
    m.top.dialog = dialog
end sub

sub onLoginDialogButton(event as object)
    idx = event.getData()
    dialog = m.top.dialog
    if idx = 0
        user = dialog.username
        pass = dialog.password
        if user <> "" and pass <> ""
            m.loading.visible = true
            m.loading.text = "Authenticating..."
            authenticate(user, pass)
        end if
    end if
    m.top.dialog = invalid
end sub

sub authenticate(user as string, pass as string)
    url = buildUrl(m.SERVER_URL, "/api/login")
    jsonObj = { username: user, password: pass }
    body = FormatJSON(jsonObj)

    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onAuthResponse")
    task.request = { url: url, method: "POST", body: body }
    task.control = "run"
end sub

sub onAuthResponse(event as object)
    m.loading.visible = false
    text = event.getData()
    if text <> invalid and text <> ""
        json = ParseJSON(text)
        if json <> invalid and json.success = true and json.cookie <> invalid
            m.sessionCookie = json.cookie
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("sessionCookie", m.sessionCookie)
            sec.Flush()
            updateLoginStatus()
            fetchCameraList()
            return
        end if
    end if
    m.loginStatus.text = "Login Failed"
    m.loginStatus.color = "#FF6B6B"
end sub

' -- Camera list --

sub fetchCameraList()
    ts = CreateObject("roDateTime")
    url = buildUrl(m.SERVER_URL, "/camera/list?t=" + ts.asSeconds().toStr())
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraListResponse")
    task.request = { url: url, cookie: m.sessionCookie }
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
    url = buildUrl(m.SERVER_URL, "/camera/" + name + "/info?t=" + ts.asSeconds().toStr())
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraInfoResponse")
    task.request = { url: url, cookie: m.sessionCookie }
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

sub onClockStyleChanged()
    idx = m.clockStyleList.checkedItem
    sec = CreateObject("roRegistrySection", "settings")
    if idx = 1
        sec.Write("clockStyle", "fade")
    else if idx = 2
        sec.Write("clockStyle", "off")
    else
        sec.Write("clockStyle", "bounce")
    end if
    sec.Flush()
end sub

sub onClockOpacityChanged()
    idx = m.clockOpacityList.checkedItem
    if idx < 0 or idx >= m.clockOpacityValues.count() then return
    sec = CreateObject("roRegistrySection", "settings")
    sec.Write("clockOpacity", m.clockOpacityValues[idx].toStr())
    sec.Flush()
end sub

sub updateLoginStatus()
    if m.sessionCookie <> ""
        m.loginStatus.text = "Logged In"
        m.loginStatus.color = "#4CAF50"
    else
        m.loginStatus.text = "Not Logged In"
        m.loginStatus.color = "#FFAA00"
    end if
end sub

' -- Focus navigation (per-page) --

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false

    if m.currentPage = 1
        controls = [m.editUrlBtn, m.editAuthBtn, m.loginBtn, m.modeList, m.photoIntervalList, m.cycleIntervalList, m.nextPageBtn1]
    else
        controls = [m.clockStyleList, m.clockOpacityList, m.prevPageBtn2]
    end if

    n = controls.count()

    idx = -1
    for i = 0 to n - 1
        if controls[i].hasFocus() or controls[i].isInFocusChain() then idx = i
    end for
    ' Prefer exact hasFocus match
    for i = 0 to n - 1
        if controls[i].hasFocus() then idx = i
    end for

    if idx >= 0
        if key = "down" or key = "right"
            controls[(idx + 1) mod n].setFocus(true)
            return true
        else if key = "up" or key = "left"
            controls[(idx - 1 + n) mod n].setFocus(true)
            return true
        end if
    end if

    return false
end function
