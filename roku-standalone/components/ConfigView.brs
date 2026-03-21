' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.cameraList = m.top.findNode("cameraList")
    m.cameraListContent = m.top.findNode("cameraListContent")
    m.previewPoster = m.top.findNode("previewPoster")
    m.previewVideo = m.top.findNode("previewVideo")
    m.cameraNameLabel = m.top.findNode("cameraNameLabel")
    m.cameraUrlLabel = m.top.findNode("cameraUrlLabel")
    m.refreshTimer = m.top.findNode("refreshTimer")
    
    m.addBtn = m.top.findNode("addBtn")
    m.editBtn = m.top.findNode("editBtn")
    m.deleteBtn = m.top.findNode("deleteBtn")
    m.viewBtn = m.top.findNode("viewBtn")
    m.saverBtn = m.top.findNode("saverBtn")
    m.formContainer = m.top.findNode("formContainer")

    m.addBtn.observeField("buttonSelected", "onAdd")
    m.editBtn.observeField("buttonSelected", "onEdit")
    m.deleteBtn.observeField("buttonSelected", "onDelete")
    m.viewBtn.observeField("buttonSelected", "onLaunchViewer")
    m.saverBtn.observeField("buttonSelected", "onStartScreensaver")

    m.cameraList.observeField("itemFocused", "onCameraFocused")
    m.refreshTimer.observeField("fire", "refreshPreview")

    m.cameras = []
    m.editIndex = -1
    
    refreshList()
    m.cameraList.setFocus(true)
end sub

sub refreshList()
    m.cameras = GetCameras()
    m.cameraListContent.clear()
    for each cam in m.cameras
        item = m.cameraListContent.createChild("ContentNode")
        item.title = cam.name
        item.description = cam.snapshot
    end for
    
    if m.cameras.count() > 0
        onCameraFocused()
        m.refreshTimer.control = "start"
    else
        m.cameraNameLabel.text = "No cameras configured"
        m.cameraUrlLabel.text = "Click 'Add New' to get started"
        m.previewPoster.uri = ""
        m.refreshTimer.control = "stop"
    end if
end sub

sub onCameraFocused()
    idx = m.cameraList.itemFocused
    if idx < 0 or idx >= m.cameras.count() then return
    cam = m.cameras[idx]
    
    m.cameraNameLabel.text = cam.name
    m.cameraUrlLabel.text = cam.snapshot
    refreshPreview()
end sub

sub refreshPreview()
    idx = m.cameraList.itemFocused
    if idx < 0 or idx >= m.cameras.count() then return
    cam = m.cameras[idx]
    
    ' For preview, we try to fetch snapshot
    task = CreateObject("roSGNode", "HttpTask")
    task.authType = cam.authType
    task.request = {
        url: cam.snapshot,
        toFile: "tmp:/preview.jpg",
        auth: { username: cam.username, password: cam.password }
    }
    task.observeField("responseCode", "onPreviewDownloaded")
    task.control = "run"
end sub

sub onPreviewDownloaded(event as object)
    if event.getData() = 200
        m.previewPoster.uri = "tmp:/preview.jpg?t=" + CreateObject("roDateTime").asSeconds().toStr()
    end if
end sub

' -- CRUD --
sub onAdd()
    m.editIndex = -1
    showEditForm({
        name: "New Camera",
        snapshot: "http://",
        stream: "",
        authType: "none",
        username: "admin",
        password: "",
        onvifHost: ""
    })
end sub

sub onEdit()
    idx = m.cameraList.itemFocused
    if idx < 0 or idx >= m.cameras.count() then return
    m.editIndex = idx
    showEditForm(m.cameras[idx])
end sub

sub onDelete()
    idx = m.cameraList.itemFocused
    if idx < 0 or idx >= m.cameras.count() then return
    
    dialog = CreateObject("roSGNode", "MessageDialog")
    dialog.title = "Delete Camera"
    dialog.message = "Are you sure you want to delete '" + m.cameras[idx].name + "'?"
    dialog.buttons = ["Delete", "Cancel"]
    dialog.observeField("buttonSelected", "onDeleteConfirm")
    m.top.getScene().dialog = dialog
end sub

sub onDeleteConfirm(event as object)
    if event.getData() = 0
        DeleteCamera(m.cameraList.itemFocused)
        refreshList()
    end if
    m.top.getScene().dialog = invalid
    m.cameraList.setFocus(true)
end sub

' -- Form Handling --
sub showEditForm(data as object)
    m.editView = CreateObject("roSGNode", "CameraEditView")
    m.editView.cameraData = data
    m.editView.observeField("saveClicked", "onSaveCamera")
    m.editView.observeField("cancelClicked", "onCancelEdit")
    m.formContainer.appendChild(m.editView)
    m.formContainer.visible = true
    m.editView.setFocus(true)
end sub

sub onSaveCamera()
    if m.editIndex >= 0
        UpdateCamera(m.editIndex, m.editView.cameraData)
    else
        AddCamera(m.editView.cameraData)
    end if
    closeEditForm()
    refreshList()
end sub

sub onCancelEdit()
    closeEditForm()
end sub

sub closeEditForm()
    m.formContainer.removeChild(m.editView)
    m.editView = invalid
    m.formContainer.visible = false
    m.cameraList.setFocus(true)
end sub

' -- Navigation --
sub onLaunchViewer()
    m.top.launchViewer = true
end sub

sub onStartScreensaver()
    m.top.launchScreensaver = true
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    
    if key = "right" and m.cameraList.hasFocus()
        m.addBtn.setFocus(true)
        return true
    else if key = "left" and not m.cameraList.hasFocus()
        m.cameraList.setFocus(true)
        return true
    end if
    
    return false
end function
