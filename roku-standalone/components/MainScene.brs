' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

sub init()
    m.viewContainer = m.top.findNode("viewContainer")
    showConfigView()
end sub

sub showConfigView()
    m.viewContainer.clear()
    m.configView = CreateObject("roSGNode", "ConfigView")
    m.configView.observeField("launchViewer", "onLaunchViewer")
    m.configView.observeField("launchScreensaver", "onLaunchScreensaver")
    m.viewContainer.appendChild(m.configView)
    m.configView.setFocus(true)
end sub

sub onLaunchViewer()
    m.viewContainer.clear()
    m.viewerScene = CreateObject("roSGNode", "ViewerScene")
    m.viewerScene.observeField("backToConfig", "onBackToConfig")
    m.viewContainer.appendChild(m.viewerScene)
    m.viewerScene.setFocus(true)
end sub

sub onLaunchScreensaver()
    m.viewContainer.clear()
    m.screensaverScene = CreateObject("roSGNode", "ScreensaverScene")
    m.screensaverScene.observeField("backToConfig", "onBackToConfig")
    m.viewContainer.appendChild(m.screensaverScene)
    m.screensaverScene.setFocus(true)
end sub

sub onBackToConfig()
    showConfigView()
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    
    ' Back button from sub-scenes should return to config
    if key = "back"
        if m.viewerScene <> invalid or m.screensaverScene <> invalid
            onBackToConfig()
            return true
        end if
    end if
    
    return false
end function
