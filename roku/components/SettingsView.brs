' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.DEFAULT_SERVER_URL = ""
    m.DEFAULT_USERNAME = ""
    m.DEFAULT_PASSWORD = ""

    m.urlLabel = m.top.findNode("urlLabel")
    m.editUrlBtn = m.top.findNode("editUrlBtn")
    m.userLabel = m.top.findNode("userLabel")
    m.editUserBtn = m.top.findNode("editUserBtn")
    m.passLabel = m.top.findNode("passLabel")
    m.editPassBtn = m.top.findNode("editPassBtn")
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
    if m.SERVER_URL = invalid or m.SERVER_URL = "" then m.SERVER_URL = m.DEFAULT_SERVER_URL
    m.urlLabel.text = m.SERVER_URL

    m.USERNAME = sec.Read("username")
    if m.USERNAME = invalid or m.USERNAME = "" then m.USERNAME = m.DEFAULT_USERNAME
    m.userLabel.text = m.USERNAME

    m.PASSWORD = sec.Read("password")
    if m.PASSWORD = invalid or m.PASSWORD = "" then m.PASSWORD = m.DEFAULT_PASSWORD
    if m.PASSWORD <> "" then m.passLabel.text = String(m.PASSWORD.len(), "*")

    m.savedMode = sec.Read("mode")
    if m.savedMode <> "camera" and m.savedMode <> "video" then m.savedMode = "photo"
    m.savedCamera = sec.Read("camera")
    if m.savedCamera = "" then m.savedCamera = "cycle"

    savedPhotoInt = sec.Read("photoInterval")
    if savedPhotoInt = "" then savedPhotoInt = "30"
    photoIdx = 1
    for i = 0 to m.photoIntervalValues.count() - 1
        if m.photoIntervalValues[i].toStr() = savedPhotoInt then photoIdx = i
    end for
    m.photoIntervalList.checkedItem = photoIdx

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
    m.editUserBtn.observeField("buttonSelected", "onEditUsername")
    m.editPassBtn.observeField("buttonSelected", "onEditPassword")
    m.modeList.observeField("checkedItem", "onModeChanged")
    m.photoIntervalList.observeField("checkedItem", "onPhotoIntervalChanged")
    m.cycleIntervalList.observeField("checkedItem", "onCycleIntervalChanged")
    m.clockStyleList.observeField("checkedItem", "onClockStyleChanged")
    m.clockOpacityList.observeField("checkedItem", "onClockOpacityChanged")

    m.loading.visible = true
    fetchCameraList()

    ' Redirect focus from the Group to the first button.
    m.top.observeField("focusedChild", "onFocusChanged")
end sub

sub onFocusChanged()
    if m.top.hasFocus()
        if m.currentPage = 1
            m.editUrlBtn.setFocus(true)
        else
            m.clockStyleList.setFocus(true)
        end if
    end if
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

' -- Dialogs --
sub onEditUrl()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Server URL"
    dialog.text = m.SERVER_URL
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onUrlDialogButton")
    m.top.getScene().dialog = dialog
end sub

sub onUrlDialogButton(event as object)
    dialog = m.top.getScene().dialog
    if event.getData() = 0
        newUrl = dialog.text
        if newUrl <> "" and newUrl <> m.SERVER_URL
            m.SERVER_URL = newUrl
            m.urlLabel.text = newUrl
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("serverUrl", newUrl)
            sec.Flush()
            refreshCameraList()
        end if
    end if
    m.top.getScene().dialog = invalid
    m.editUrlBtn.setFocus(true)
end sub

sub onEditUsername()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Username"
    dialog.text = m.USERNAME
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onUsernameDialogButton")
    m.top.getScene().dialog = dialog
end sub

sub onUsernameDialogButton(event as object)
    dialog = m.top.getScene().dialog
    if event.getData() = 0
        newUser = dialog.text
        if newUser <> m.USERNAME
            m.USERNAME = newUser
            m.userLabel.text = newUser
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("username", newUser)
            sec.Flush()
            refreshCameraList()
        end if
    end if
    m.top.getScene().dialog = invalid
    m.editUrlBtn.setFocus(true)
end sub

sub onEditPassword()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Password"
    dialog.text = m.PASSWORD
    dialog.isPassword = true
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onPasswordDialogButton")
    m.top.getScene().dialog = dialog
end sub

sub onPasswordDialogButton(event as object)
    dialog = m.top.getScene().dialog
    if event.getData() = 0
        newPass = dialog.text
        if newPass <> m.PASSWORD
            m.PASSWORD = newPass
            if newPass = ""
                m.passLabel.text = ""
            else
                m.passLabel.text = String(newPass.len(), "*")
            end if
            sec = CreateObject("roRegistrySection", "settings")
            sec.Write("password", newPass)
            sec.Flush()
            refreshCameraList()
        end if
    end if
    m.top.getScene().dialog = invalid
    m.editUrlBtn.setFocus(true)
end sub

sub refreshCameraList()
    m.loading.visible = true
    m.loading.text = "Loading cameras..."
    clearCameraOptions()
    fetchCameraList()
end sub

' -- Camera list handling (for settings options) --
sub clearCameraOptions()
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

sub fetchCameraList()
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/list?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraListResponse")
    task.observeField("error", "onCameraListError")
    task.request = { url: url, auth: { username: m.USERNAME, password: m.PASSWORD } }
    task.control = "run"
end sub

sub onCameraListError(event as object)
    errMsg = event.getData()
    if errMsg <> invalid and errMsg <> ""
        m.loading.text = "Error: " + errMsg
    else
        m.loading.text = "Could not reach server"
    end if
end sub

sub onCameraListResponse(event as object)
    text = event.getData()
    if text = invalid or text = ""
        m.loading.text = "Could not reach server"
        return
    end if
    json = ParseJSON(text)
    if json = invalid or type(json) <> "roArray"
        m.loading.text = "Auth Failed or Bad Response"
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
        if m.savedMode = "camera" and m.savedCamera = name then savedIdx = m.options.count() - 1
    end for
    if savedIdx >= 0 then m.modeList.checkedItem = savedIdx

    m.loading.text = "Checking streams..."
    m.pendingInfoCount = m.filteredCamNames.count()
    if m.pendingInfoCount = 0 then m.loading.visible = false
    for each name in m.filteredCamNames
        fetchCameraInfo(name)
    end for
end sub

sub fetchCameraInfo(name as string)
    ts = CreateObject("roDateTime")
    url = m.SERVER_URL + "/camera/" + name + "/info?t=" + ts.asSeconds().toStr()
    task = CreateObject("roSGNode", "HttpTask")
    task.observeField("response", "onCameraInfoResponse")
    task.observeField("error", "onCameraInfoError")
    task.request = { url: url, auth: { username: m.USERNAME, password: m.PASSWORD } }
    task.control = "run"
end sub

sub onCameraInfoError(event as object)
    m.pendingInfoCount = m.pendingInfoCount - 1
    if m.pendingInfoCount <= 0
        m.loading.visible = false
        addVideoOptions()
    end if
end sub

sub onCameraInfoResponse(event as object)
    m.pendingInfoCount = m.pendingInfoCount - 1
    text = event.getData()
    if text <> invalid and text <> ""
        info = ParseJSON(text)
        if info <> invalid and info.stream <> invalid and info.stream <> ""
            m.cameraInfoMap[info.name] = { stream: info.stream, streamType: info.stream_type }
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
            if m.savedMode = "video" and m.savedCamera = name then savedIdx = m.options.count() - 1
        end if
    end for
    if savedIdx >= 0 then m.modeList.checkedItem = savedIdx
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

' -- Key handling --
function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false

    if key = "back"
        sec = CreateObject("roRegistrySection", "settings")
        sec.Write("serverUrl", m.SERVER_URL)
        sec.Write("username", m.USERNAME)
        sec.Write("password", m.PASSWORD)
        sec.Flush()

        if m.currentPage = 2
            ' Go back to page 1 instead of closing
            showPage(1)
            return true
        end if

        m.top.visible = false
        m.top.wasClosed = true
        return true
    end if

    if m.currentPage = 1
        ' Page 1: two-column navigation
        buttons = [m.editUrlBtn, m.editUserBtn, m.editPassBtn, m.nextPageBtn1]
        lists = [m.modeList, m.photoIntervalList, m.cycleIntervalList]

        btnIdx = -1
        for i = 0 to buttons.count() - 1
            if buttons[i].hasFocus() then btnIdx = i
        end for

        listIdx = -1
        for i = 0 to lists.count() - 1
            if lists[i].hasFocus() or lists[i].isInFocusChain() then listIdx = i
        end for
        if btnIdx >= 0 then listIdx = -1

        nBtn = buttons.count()
        nList = lists.count()

        if btnIdx >= 0
            if key = "down"
                buttons[(btnIdx + 1) mod nBtn].setFocus(true)
                return true
            else if key = "up"
                buttons[(btnIdx - 1 + nBtn) mod nBtn].setFocus(true)
                return true
            else if key = "right"
                target = btnIdx
                if target >= nList then target = nList - 1
                lists[target].setFocus(true)
                return true
            end if
        else if listIdx >= 0
            if key = "left"
                target = listIdx
                if target >= nBtn then target = nBtn - 1
                buttons[target].setFocus(true)
                return true
            else if key = "down"
                lists[(listIdx + 1) mod nList].setFocus(true)
                return true
            else if key = "up"
                lists[(listIdx - 1 + nList) mod nList].setFocus(true)
                return true
            end if
        end if
    else
        ' Page 2: single-column navigation
        controls = [m.clockStyleList, m.clockOpacityList, m.prevPageBtn2]
        n = controls.count()

        idx = -1
        for i = 0 to n - 1
            if controls[i].hasFocus() or controls[i].isInFocusChain() then idx = i
        end for
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
    end if

    return false
end function
