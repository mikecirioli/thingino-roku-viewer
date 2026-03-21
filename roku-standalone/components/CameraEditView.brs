' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.nameLabel = m.top.findNode("nameLabel")
    m.snapshotLabel = m.top.findNode("snapshotLabel")
    m.streamLabel = m.top.findNode("streamLabel")
    m.authList = m.top.findNode("authList")
    m.userLabel = m.top.findNode("userLabel")
    m.passLabel = m.top.findNode("passLabel")
    m.onvifLabel = m.top.findNode("onvifLabel")
    m.testPoster = m.top.findNode("testPoster")

    m.editNameBtn = m.top.findNode("editNameBtn")
    m.editSnapshotBtn = m.top.findNode("editSnapshotBtn")
    m.editStreamBtn = m.top.findNode("editStreamBtn")
    m.editUserBtn = m.top.findNode("editUserBtn")
    m.editPassBtn = m.top.findNode("editPassBtn")
    m.editOnvifBtn = m.top.findNode("editOnvifBtn")
    m.testBtn = m.top.findNode("testBtn")
    m.saveBtn = m.top.findNode("saveBtn")
    m.cancelBtn = m.top.findNode("cancelBtn")

    m.editNameBtn.observeField("buttonSelected", "onEditName")
    m.editSnapshotBtn.observeField("buttonSelected", "onEditSnapshot")
    m.editStreamBtn.observeField("buttonSelected", "onEditStream")
    m.editUserBtn.observeField("buttonSelected", "onEditUser")
    m.editPassBtn.observeField("buttonSelected", "onEditPass")
    m.editOnvifBtn.observeField("buttonSelected", "onEditOnvif")
    m.testBtn.observeField("buttonSelected", "onTestSnapshot")
    m.saveBtn.observeField("buttonSelected", "onSave")
    m.cancelBtn.observeField("buttonSelected", "onCancel")

    m.top.observeField("cameraData", "onCameraDataChanged")
    
    m.focusGrid = [
        [m.editNameBtn, m.editUserBtn],
        [m.editSnapshotBtn, m.editPassBtn],
        [m.editStreamBtn, m.editOnvifBtn],
        [m.authList, m.testBtn],
        [m.saveBtn, m.cancelBtn]
    ]
    m.focusRow = 0
    m.focusCol = 0
    m.editNameBtn.setFocus(true)
end sub

sub onCameraDataChanged()
    data = m.top.cameraData
    if data = invalid then return
    
    if data.name <> invalid then m.nameLabel.text = data.name else m.nameLabel.text = ""
    if data.snapshot <> invalid then m.snapshotLabel.text = data.snapshot else m.snapshotLabel.text = ""
    if data.stream <> invalid then m.streamLabel.text = data.stream else m.streamLabel.text = ""
    
    authIdx = 0
    if data.authType = "basic" then authIdx = 1
    if data.authType = "thingino" then authIdx = 2
    m.authList.checkedItem = authIdx
    
    if data.username <> invalid then m.userLabel.text = data.username else m.userLabel.text = ""
    if data.password <> invalid and data.password <> "" then m.passLabel.text = String(data.password.len(), "*") else m.passLabel.text = ""
    if data.onvifHost <> invalid then m.onvifLabel.text = data.onvifHost else m.onvifLabel.text = ""
end sub

' -- Dialogs --
sub onEditName()
    openKeyboard("Enter Camera Name", m.nameLabel.text, "onNameEntered")
end sub
sub onNameEntered(event as object)
    if event.getData() = 0
        m.nameLabel.text = event.getNode().text
    end if
    closeDialog()
end sub

sub onEditSnapshot()
    openKeyboard("Enter Snapshot URL", m.snapshotLabel.text, "onSnapshotEntered")
end sub
sub onSnapshotEntered(event as object)
    if event.getData() = 0
        m.snapshotLabel.text = event.getNode().text
    end if
    closeDialog()
end sub

sub onEditStream()
    openKeyboard("Enter Stream URL", m.streamLabel.text, "onStreamEntered")
end sub
sub onStreamEntered(event as object)
    if event.getData() = 0
        m.streamLabel.text = event.getNode().text
    end if
    closeDialog()
end sub

sub onEditUser()
    openKeyboard("Enter Username", m.userLabel.text, "onUserEntered")
end sub
sub onUserEntered(event as object)
    if event.getData() = 0
        m.userLabel.text = event.getNode().text
    end if
    closeDialog()
end sub

sub onEditPass()
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = "Enter Password"
    dialog.text = m.top.cameraData.password
    dialog.isPassword = true
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", "onPassEntered")
    m.top.getScene().dialog = dialog
end sub
sub onPassEntered(event as object)
    if event.getData() = 0
        pass = event.getNode().text
        m.top.cameraData.password = pass
        if pass <> "" then m.passLabel.text = String(pass.len(), "*") else m.passLabel.text = ""
    end if
    closeDialog()
end sub

sub onEditOnvif()
    openKeyboard("Enter ONVIF Host", m.onvifLabel.text, "onOnvifEntered")
end sub
sub onOnvifEntered(event as object)
    if event.getData() = 0
        m.onvifLabel.text = event.getNode().text
    end if
    closeDialog()
end sub

sub openKeyboard(title as string, text as string, callback as string)
    dialog = CreateObject("roSGNode", "StandardKeyboardDialog")
    dialog.title = title
    dialog.text = text
    dialog.buttons = ["OK", "Cancel"]
    dialog.observeField("buttonSelected", callback)
    m.top.getScene().dialog = dialog
end sub

sub closeDialog()
    m.top.getScene().dialog = invalid
    m.focusGrid[m.focusRow][m.focusCol].setFocus(true)
end sub

' -- Actions --
sub onTestSnapshot()
    authType = "none"
    idx = m.authList.checkedItem
    if idx = 1 then authType = "basic"
    if idx = 2 then authType = "thingino"

    url = m.snapshotLabel.text
    if url = "" then return
    
    m.testBtn.text = "Testing..."
    m.testBtn.enabled = false
    
    task = CreateObject("roSGNode", "HttpTask")
    task.authType = authType
    task.request = {
        url: url,
        toFile: "tmp:/test.jpg",
        auth: { username: m.userLabel.text, password: m.top.cameraData.password }
    }
    task.observeField("responseCode", "onTestFinished")
    task.observeField("error", "onTestFinished")
    task.control = "run"
end sub

sub onTestFinished(event as object)
    m.testBtn.text = "Test Connection"
    m.testBtn.enabled = true
    
    task = event.getNode()
    if task.responseCode = 200
        m.testPoster.uri = "tmp:/test.jpg?t=" + CreateObject("roDateTime").asSeconds().toStr()
    else
        ' Show error somehow? maybe in subtitle
        print "Test failed: " + task.error
    end if
end sub

sub onSave()
    authType = "none"
    idx = m.authList.checkedItem
    if idx = 1 then authType = "basic"
    if idx = 2 then authType = "thingino"

    m.top.cameraData = {
        name: m.nameLabel.text,
        snapshot: m.snapshotLabel.text,
        stream: m.streamLabel.text,
        authType: authType,
        username: m.userLabel.text,
        password: m.top.cameraData.password,
        onvifHost: m.onvifLabel.text
    }
    m.top.saveClicked = true
end sub

sub onCancel()
    m.top.cancelClicked = true
end sub

' -- Key handling --
function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false

    if key = "back"
        onCancel()
        return true
    end if

    rows = m.focusGrid.count()
    newRow = m.focusRow
    newCol = m.focusCol

    if key = "down"
        newRow = (m.focusRow + 1) mod rows
    else if key = "up"
        newRow = (m.focusRow - 1 + rows) mod rows
    else if key = "right" and m.focusCol = 0
        newCol = 1
    else if key = "left" and m.focusCol = 1
        newCol = 0
    else
        return false
    end if

    if m.focusGrid[newRow][newCol] = invalid
        ' Skip invalid focus cells (e.g. empty left col in last row)
        if key = "down" or key = "up"
             newRow = (newRow + (if key = "down" then 1 else -1) + rows) mod rows
        end if
    end if

    if newRow <> m.focusRow or newCol <> m.focusCol
        m.focusRow = newRow
        m.focusCol = newCol
        m.focusGrid[newRow][newCol].setFocus(true)
        return true
    end if

    return false
end function
