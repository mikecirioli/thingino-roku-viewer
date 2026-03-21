' Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.

function GetCameras() as Object
    sec = CreateObject("roRegistrySection", "cameras")
    json = sec.Read("cameraList")
    if json = invalid or json = "" then return []
    list = ParseJSON(json)
    if list = invalid or type(list) <> "roArray" then return []
    return list
end function

sub SaveCameras(list as Object)
    if list = invalid or type(list) <> "roArray" then return
    sec = CreateObject("roRegistrySection", "cameras")
    sec.Write("cameraList", FormatJSON(list))
    sec.Flush()
end sub

sub AddCamera(cam as Object)
    list = GetCameras()
    list.push(cam)
    SaveCameras(list)
end sub

sub UpdateCamera(index as Integer, cam as Object)
    list = GetCameras()
    if index >= 0 and index < list.count()
        list[index] = cam
        SaveCameras(list)
    end if
end sub

sub DeleteCamera(index as Integer)
    list = GetCameras()
    if index >= 0 and index < list.count()
        list.delete(index)
        SaveCameras(list)
    end if
end sub
